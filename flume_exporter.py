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
from prometheus_client import start_http_server, Gauge, Counter, Histogram, Info, REGISTRY, PROCESS_COLLECTOR, PLATFORM_COLLECTOR, GC_COLLECTOR
from flask import Flask, Response
import threading
import base64
import json as js
import traceback

# Disable default collectors to remove Python GC and process metrics
REGISTRY.unregister(PROCESS_COLLECTOR)
REGISTRY.unregister(PLATFORM_COLLECTOR)
REGISTRY.unregister(GC_COLLECTOR)

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
        self.user_id = None
        self.session = requests.Session()
        
        # Authenticate immediately upon initialization
        logger.info("Initializing FlumeAPI - attempting authentication...")
        if not self.authenticate():
            logger.error("Failed to authenticate during initialization")
        else:
            logger.info("Successfully authenticated during initialization")
    
    def authenticate(self) -> bool:
        """Authenticate with the Flume API using OAuth"""
        try:
            logger.info("Starting authentication process...")
            auth_url = f"{self.BASE_URL}/oauth/token"
            auth_data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'password',
                'username': self.username,
                'password': self.password
            }
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            logger.info(f"Making authentication request to: {auth_url} with data: {auth_data}")
            response = self.session.post(auth_url, json=auth_data, headers=headers)
            logger.info(f"Authentication response status: {response.status_code}")
            logger.info(f"Authentication response text: {response.text}")
            response.raise_for_status()
            token_data = response.json()
            logger.info(f"Token response: {token_data}")  # Debug log
            if 'data' in token_data and isinstance(token_data['data'], list) and token_data['data']:
                token_info = token_data['data'][0]
                self.access_token = token_info['access_token']
                expires_in = token_info.get('expires_in', 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                logger.info(f"Access token: {self.access_token}")
                logger.info(f"Expires in: {expires_in}")
                # Extract user_id from JWT access token
                try:
                    payload = self.access_token.split('.')[1]
                    payload += '=' * (-len(payload) % 4)
                    user_info = js.loads(base64.urlsafe_b64decode(payload).decode())
                    logger.info(f"Decoded JWT payload: {user_info}")
                    self.user_id = str(user_info.get('user_id') or user_info.get('user', ''))
                    logger.info(f"Extracted user_id: {self.user_id}")
                except Exception as e:
                    logger.error(f"Failed to decode JWT or extract user_id: {e}")
                    logger.error(traceback.format_exc())
                    self.user_id = None
            else:
                logger.error(f"Unexpected token response format: {token_data}")
                self.user_id = None
                return False
            logger.info("Successfully authenticated with Flume API")
            return True
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            logger.error(traceback.format_exc())
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
            logger.info(f"Fetching devices for user_id: {getattr(self, 'user_id', None)}")
            if not hasattr(self, 'user_id') or not self.user_id:
                logger.error("user_id not set after authentication")
                return []
            response = self.session.get(
                f"{self.BASE_URL}/users/{self.user_id}/devices",
                headers=self._get_headers()
            )
            logger.info(f"Devices response status: {response.status_code}")
            logger.info(f"Devices response text: {response.text}")
            response.raise_for_status()
            data = response.json()
            logger.info(f"Devices data: {data}")
            return data.get('data', [])
        except Exception as e:
            logger.error(f"Failed to get devices: {e}")
            logger.error(traceback.format_exc())
            return []
    
    def get_consumption_data(self, device_id: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Get consumption data for a specific device and time period"""
        try:
            url = f"{self.BASE_URL}/users/{self.user_id}/devices/{device_id}/query"
            body = {
                "queries": [
                    {
                        "request_id": "usage",
                        "bucket": "MIN",
                        "since_datetime": start_date,
                        "until_datetime": end_date
                    }
                ]
            }
            logger.info(f"Getting consumption data for device {device_id} from {start_date} to {end_date}")
            response = self.session.post(url, headers=self._get_headers(), json=body)
            logger.info(f"Consumption response status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            
            # Log only success/failure, not the full data
            if 'data' in data and isinstance(data['data'], list) and data['data']:
                usage_data = data['data'][0].get('usage', [])
                logger.info(f"Retrieved {len(usage_data)} consumption data points for device {device_id}")
                return usage_data
            else:
                logger.warning(f"No consumption data found for device {device_id}")
                return []
        except Exception as e:
            logger.error(f"Failed to get consumption data for device {device_id}: {e}")
            logger.error(traceback.format_exc())
            return []

    def get_current_flow_rate(self, device_id: str) -> Optional[float]:
        """Get the current flow rate for a device (gallons per minute)"""
        try:
            url = f"{self.BASE_URL}/users/{self.user_id}/devices/{device_id}/query/active"
            logger.info(f"Fetching current flow rate from: {url}")
            response = self.session.get(url, headers=self._get_headers())
            logger.info(f"Flow rate response status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            
            # The flow rate is directly in data['data'][0]['gpm']
            if 'data' in data and isinstance(data['data'], list) and data['data']:
                flow_rate = data['data'][0].get('gpm')
                if flow_rate is not None:
                    logger.info(f"Retrieved flow rate: {flow_rate} GPM for device {device_id}")
                return flow_rate
            return None
        except Exception as e:
            logger.error(f"Failed to get current flow rate for device {device_id}: {e}")
            logger.error(traceback.format_exc())
            return None

class FlumeMetrics:
    """Prometheus metrics for Flume Water data"""
    
    def __init__(self):
        # Device information
        self.device_info = Info('flume_device', 'Information about Flume devices', ['device_id', 'device_name', 'location'])
        
        self.water_flow_rate = Gauge(
            'flume_water_flow_rate',
            'Current water flow rate in gallons per minute',
            ['device_id', 'device_name']
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
                    device_name = f"Flume {device.get('product', 'Unknown')}"
                    location = f"Location {device.get('location_id', 'Unknown')}"
                    
                    # Fix Info metric usage
                    self.metrics.device_info.labels(
                        device_id=device_id,
                        device_name=device_name,
                        location=location
                    ).info({
                        'product': device.get('product', 'Unknown'),
                        'type': str(device.get('type', 'Unknown')),
                        'connected': str(device.get('connected', False))
                    })
                
                logger.info(f"Updated devices cache with {len(devices)} devices")
                
        except Exception as e:
            logger.error(f"Failed to update devices cache: {e}")

    def collect_consumption_data(self):
        """Collect consumption data for all devices"""
        try:
            self.update_devices_cache()
            
            # Get data for the last 23 hours (staying under 1440 minute limit)
            end_date = datetime.now()
            start_date = end_date - timedelta(hours=23)
            
            for device in self.devices_cache:
                device_id = device.get('id')
                device_name = f"Flume {device.get('product', 'Unknown')}"
                
                if not device_id:
                    continue
                
                # Get consumption data for the last 23 hours
                consumption_data = self.api.get_consumption_data(
                    device_id,
                    start_date.strftime('%Y-%m-%d %H:%M:%S'),
                    end_date.strftime('%Y-%m-%d %H:%M:%S')
                )
                
                # Removed water consumption metrics update
                
                # Get current flow rate from /query/active
                flow_rate = self.api.get_current_flow_rate(device_id)
                if flow_rate is not None:
                    self.metrics.water_flow_rate.labels(
                        device_id=device_id,
                        device_name=device_name
                    ).set(flow_rate)
                
                logger.info(f"Collected data for device {device_id} ({device_name})")
            
            logger.info("Successfully collected consumption data")
            
        except Exception as e:
            logger.error(f"Failed to collect consumption data: {e}")

    def run_scheduler(self):
        """Run the data collection scheduler"""
        # Collect data every minute
        schedule.every(1).minutes.do(self.collect_consumption_data)
        
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
    logger.info("Starting main() entry point...")
    # Validate environment variables
    required_env_vars = ['FLUME_CLIENT_ID', 'FLUME_CLIENT_SECRET', 'FLUME_USERNAME', 'FLUME_PASSWORD']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set the following environment variables:")
        for var in missing_vars:
            logger.error(f"  - {var}")
        return 1
    
    port = int(os.getenv('EXPORTER_PORT', '8001'))
    logger.info(f"Exporter will run on port {port}")
    
    try:
        logger.info("Instantiating FlumeExporter...")
        exporter = FlumeExporter()
        logger.info("FlumeExporter instantiated. Starting exporter...")
        exporter.start(port)
    except Exception as e:
        logger.error(f"Exception in main: {e}")
        logger.error(traceback.format_exc())
    return 0

if __name__ == '__main__':
    exit(main()) 