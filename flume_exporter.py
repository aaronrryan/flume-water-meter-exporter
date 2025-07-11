#!/usr/bin/env python3
"""
Flume Water Prometheus Exporter

This script collects data from the Flume Water API and exposes it as Prometheus metrics.
It handles authentication, data collection, and metric formatting for monitoring water usage.
"""

import os
import time
import logging
import requests
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from prometheus_client import start_http_server, Gauge, Counter, Histogram, Info
from flask import Flask, Response
import threading

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FlumeAPI:
    """Client for interacting with the Flume Water API"""
    
    BASE_URL = "https://api.flumewater.com"
    
    def __init__(self, client_id: str, client_secret: str, username: str, password: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.access_token = None
        self.token_expires_at = None
        self.session = requests.Session()
    
    def authenticate(self) -> bool:
        """Authenticate with the Flume API using OAuth2"""
        try:
            auth_url = f"{self.BASE_URL}/oauth2/token"
            auth_data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'password',
                'username': self.username,
                'password': self.password
            }
            
            response = self.session.post(auth_url, data=auth_data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.token_expires_at = datetime.now() + timedelta(seconds=token_data['expires_in'])
            
            logger.info("Successfully authenticated with Flume API")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        if not self.access_token or (self.token_expires_at and datetime.now() >= self.token_expires_at):
            if not self.authenticate():
                raise Exception("Failed to authenticate")
        
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get user information"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/users/me",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None
    
    def get_devices(self) -> List[Dict[str, Any]]:
        """Get list of user devices"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/users/me/devices",
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            logger.error(f"Failed to get devices: {e}")
            return []
    
    def get_consumption_data(self, device_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get consumption data for a specific device and time period"""
        try:
            params = {
                'start_date': start_date,
                'end_date': end_date,
                'bucket': 'MIN'  # 1-minute intervals
            }
            
            response = self.session.get(
                f"{self.BASE_URL}/users/me/devices/{device_id}/consumption",
                headers=self._get_headers(),
                params=params
            )
            response.raise_for_status()
            data = response.json()
            return data.get('data', [])
        except Exception as e:
            logger.error(f"Failed to get consumption data for device {device_id}: {e}")
            return []

class FlumeMetrics:
    """Prometheus metrics for Flume Water data"""
    
    def __init__(self):
        # Device information
        self.device_info = Info('flume_device', 'Information about Flume devices', ['device_id', 'device_name', 'location'])
        
        # Water consumption metrics
        self.water_consumption_gallons = Gauge(
            'flume_water_consumption_gallons',
            'Water consumption in gallons',
            ['device_id', 'device_name']
        )
        
        self.water_consumption_liters = Gauge(
            'flume_water_consumption_liters',
            'Water consumption in liters',
            ['device_id', 'device_name']
        )
        
        self.water_flow_rate = Gauge(
            'flume_water_flow_rate',
            'Current water flow rate in gallons per minute',
            ['device_id', 'device_name']
        )
        
        # Daily consumption
        self.daily_consumption = Gauge(
            'flume_daily_consumption_gallons',
            'Daily water consumption in gallons',
            ['device_id', 'device_name', 'date']
        )
        
        # Monthly consumption
        self.monthly_consumption = Gauge(
            'flume_monthly_consumption_gallons',
            'Monthly water consumption in gallons',
            ['device_id', 'device_name', 'year', 'month']
        )
        
        # API request metrics
        self.api_requests_total = Counter(
            'flume_api_requests_total',
            'Total number of API requests',
            ['endpoint', 'status']
        )
        
        self.api_request_duration = Histogram(
            'flume_api_request_duration_seconds',
            'API request duration in seconds',
            ['endpoint']
        )
        
        # Error metrics
        self.api_errors_total = Counter(
            'flume_api_errors_total',
            'Total number of API errors',
            ['endpoint', 'error_type']
        )

class FlumeExporter:
    """Main exporter class that coordinates data collection and metric exposure"""
    
    def __init__(self):
        # Initialize API client
        self.api = FlumeAPI(
            client_id=os.getenv('FLUME_CLIENT_ID'),
            client_secret=os.getenv('FLUME_CLIENT_SECRET'),
            username=os.getenv('FLUME_USERNAME'),
            password=os.getenv('FLUME_PASSWORD')
        )
        
        # Initialize metrics
        self.metrics = FlumeMetrics()
        
        # Cache for device data
        self.devices_cache = []
        self.last_devices_update = None
        self.devices_cache_ttl = 3600  # 1 hour
        
        # Flask app for metrics endpoint
        self.app = Flask(__name__)
        self.setup_routes()
    
    def setup_routes(self):
        """Setup Flask routes"""
        @self.app.route('/metrics')
        def metrics():
            """Prometheus metrics endpoint"""
            from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
            return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
        
        @self.app.route('/health')
        def health():
            """Health check endpoint"""
            return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}
    
    def update_devices_cache(self):
        """Update the devices cache"""
        try:
            current_time = datetime.now()
            if (self.last_devices_update is None or 
                (current_time - self.last_devices_update).seconds > self.devices_cache_ttl):
                
                devices = self.api.get_devices()
                self.devices_cache = devices
                self.last_devices_update = current_time
                
                # Update device info metrics
                for device in devices:
                    device_id = device.get('id')
                    device_name = device.get('name', 'Unknown')
                    location = device.get('location', {}).get('address', 'Unknown')
                    
                    self.metrics.device_info.info({
                        'device_id': device_id,
                        'device_name': device_name,
                        'location': location
                    })
                
                logger.info(f"Updated devices cache with {len(devices)} devices")
                
        except Exception as e:
            logger.error(f"Failed to update devices cache: {e}")
            self.metrics.api_errors_total.labels(endpoint='devices', error_type='cache_update').inc()
    
    def collect_consumption_data(self):
        """Collect consumption data for all devices"""
        try:
            self.update_devices_cache()
            
            # Get data for the last hour
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=1)
            
            for device in self.devices_cache:
                device_id = device.get('id')
                device_name = device.get('name', 'Unknown')
                
                if not device_id:
                    continue
                
                # Get consumption data
                consumption_data = self.api.get_consumption_data(
                    device_id,
                    start_date.strftime('%Y-%m-%d %H:%M:%S'),
                    end_date.strftime('%Y-%m-%d %H:%M:%S')
                )
                
                if consumption_data:
                    # Get the most recent data point
                    latest_data = consumption_data[-1]
                    
                    # Update current consumption metrics
                    consumption_gallons = latest_data.get('value', 0)
                    consumption_liters = consumption_gallons * 3.78541  # Convert to liters
                    
                    self.metrics.water_consumption_gallons.labels(
                        device_id=device_id,
                        device_name=device_name
                    ).set(consumption_gallons)
                    
                    self.metrics.water_consumption_liters.labels(
                        device_id=device_id,
                        device_name=device_name
                    ).set(consumption_liters)
                    
                    # Calculate flow rate (difference from previous reading)
                    if len(consumption_data) > 1:
                        prev_data = consumption_data[-2]
                        prev_consumption = prev_data.get('value', 0)
                        time_diff = (latest_data.get('timestamp', 0) - prev_data.get('timestamp', 0)) / 60.0  # minutes
                        
                        if time_diff > 0:
                            flow_rate = (consumption_gallons - prev_consumption) / time_diff
                            self.metrics.water_flow_rate.labels(
                                device_id=device_id,
                                device_name=device_name
                            ).set(flow_rate)
                
                # Update daily consumption
                daily_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                daily_data = self.api.get_consumption_data(
                    device_id,
                    daily_start.strftime('%Y-%m-%d %H:%M:%S'),
                    end_date.strftime('%Y-%m-%d %H:%M:%S')
                )
                
                if daily_data:
                    daily_total = sum(point.get('value', 0) for point in daily_data)
                    self.metrics.daily_consumption.labels(
                        device_id=device_id,
                        device_name=device_name,
                        date=daily_start.strftime('%Y-%m-%d')
                    ).set(daily_total)
                
                # Update monthly consumption
                monthly_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                monthly_data = self.api.get_consumption_data(
                    device_id,
                    monthly_start.strftime('%Y-%m-%d %H:%M:%S'),
                    end_date.strftime('%Y-%m-%d %H:%M:%S')
                )
                
                if monthly_data:
                    monthly_total = sum(point.get('value', 0) for point in monthly_data)
                    self.metrics.monthly_consumption.labels(
                        device_id=device_id,
                        device_name=device_name,
                        year=monthly_start.strftime('%Y'),
                        month=monthly_start.strftime('%m')
                    ).set(monthly_total)
            
            logger.info("Successfully collected consumption data")
            
        except Exception as e:
            logger.error(f"Failed to collect consumption data: {e}")
            self.metrics.api_errors_total.labels(endpoint='consumption', error_type='data_collection').inc()
    
    def run_scheduler(self):
        """Run the data collection scheduler"""
        # Collect data every 5 minutes
        schedule.every(5).minutes.do(self.collect_consumption_data)
        
        # Initial data collection
        self.collect_consumption_data()
        
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def start(self, port: int = 8001):
        """Start the exporter"""
        logger.info(f"Starting Flume Water Prometheus exporter on port {port}")
        
        # Start the scheduler in a separate thread
        scheduler_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        scheduler_thread.start()
        
        # Start the Flask app
        self.app.run(host='0.0.0.0', port=port)

def main():
    """Main entry point"""
    # Validate environment variables
    required_env_vars = ['FLUME_CLIENT_ID', 'FLUME_CLIENT_SECRET', 'FLUME_USERNAME', 'FLUME_PASSWORD']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set the following environment variables:")
        for var in missing_vars:
            logger.error(f"  - {var}")
        return 1
    
    # Get port from environment or use default
    port = int(os.getenv('EXPORTER_PORT', '8001'))
    
    # Create and start exporter
    exporter = FlumeExporter()
    exporter.start(port)
    
    return 0

if __name__ == '__main__':
    exit(main()) 