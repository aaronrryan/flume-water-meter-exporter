# Flume Water Prometheus Exporter

A Python-based Prometheus exporter that collects water consumption data from the Flume Water API and exposes it as metrics for monitoring and alerting.

## Features

- **Real-time Water Monitoring**: Collects current water consumption, flow rates, and historical data
- **Multiple Time Periods**: Tracks daily, monthly, and real-time consumption metrics
- **Device Management**: Supports multiple Flume devices with individual metrics
- **Prometheus Integration**: Exposes standard Prometheus metrics format
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **Health Monitoring**: Built-in health checks and error tracking
- **Authentication**: Secure OAuth2 authentication with token refresh

## Metrics Exposed

### Water Consumption Metrics
- `flume_water_consumption_gallons`: Current water consumption in gallons
- `flume_water_consumption_liters`: Current water consumption in liters
- `flume_water_flow_rate`: Current water flow rate in gallons per minute
- `flume_daily_consumption_gallons`: Daily water consumption in gallons
- `flume_monthly_consumption_gallons`: Monthly water consumption in gallons

### Device Information
- `flume_device`: Device information including name and location

### API Monitoring
- `flume_api_requests_total`: Total number of API requests
- `flume_api_request_duration_seconds`: API request duration
- `flume_api_errors_total`: Total number of API errors

## Prerequisites

1. **Flume Water Account**: You need a Flume Water account with devices installed
2. **API Credentials**: Register your application at [Flume Developer Portal](https://portal.flumewater.com/)
3. **Python 3.8+**: For local development
4. **Docker**: For containerized deployment (optional)

## Setup Instructions

### 1. Get Flume API Credentials

1. Visit [Flume Developer Portal](https://portal.flumewater.com/)
2. Register your application to get `CLIENT_ID` and `CLIENT_SECRET`
3. Note your Flume account username and password

### 2. Environment Configuration

Copy the example environment file and configure your credentials:

```bash
cp env.example .env
```

Edit `.env` with your actual credentials:

```env
FLUME_CLIENT_ID=your_client_id_here
FLUME_CLIENT_SECRET=your_client_secret_here
FLUME_USERNAME=your_flume_username
FLUME_PASSWORD=your_flume_password
EXPORTER_PORT=8001
LOG_LEVEL=INFO
```

### 3. Deployment Options

#### Option A: Docker Compose (Recommended)

```bash
# Build and start the exporter
docker-compose up -d

# View logs
docker-compose logs -f flume-exporter

# Stop the exporter
docker-compose down
```

#### Option B: Local Python Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the exporter
python flume_exporter.py
```

#### Option C: Docker Only

```bash
# Build the image
docker build -t flume-water-exporter .

# Run the container
docker run -d \
  --name flume-exporter \
  -p 8001:8000 \
  --env-file .env \
  flume-water-exporter
```

## Usage

### Accessing Metrics

Once running, the exporter will be available at:

- **Metrics Endpoint**: `http://localhost:8001/metrics`
- **Health Check**: `http://localhost:8001/health`

### Example Metrics Output

```
# HELP flume_water_consumption_gallons Water consumption in gallons
# TYPE flume_water_consumption_gallons gauge
flume_water_consumption_gallons{device_id="12345",device_name="Main Water Meter"} 1250.5

# HELP flume_water_flow_rate Current water flow rate in gallons per minute
# TYPE flume_water_flow_rate gauge
flume_water_flow_rate{device_id="12345",device_name="Main Water Meter"} 2.3

# HELP flume_daily_consumption_gallons Daily water consumption in gallons
# TYPE flume_daily_consumption_gallons gauge
flume_daily_consumption_gallons{device_id="12345",device_name="Main Water Meter",date="2024-01-15"} 45.2
```

### Prometheus Configuration

Add this to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'flume-water-exporter'
    scrape_interval: 30s
    static_configs:
      - targets: ['localhost:8001']
```

## Security Considerations

### Credential Management

- **Never commit credentials** to version control
- Use environment variables or `.env` files (not committed to git)
- Consider using a secrets management system in production
- Rotate API credentials regularly

### Network Security

- The exporter runs on port 8001 by default
- Consider using reverse proxy with TLS in production
- Restrict access to the metrics endpoint if needed
- Use firewall rules to limit access

### API Rate Limiting

- The exporter respects Flume API rate limits
- Data collection runs every 5 minutes by default
- Adjust collection frequency based on your needs and API limits

## Configuration Options

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `FLUME_CLIENT_ID` | Flume API client ID | - | Yes |
| `FLUME_CLIENT_SECRET` | Flume API client secret | - | Yes |
| `FLUME_USERNAME` | Flume account username | - | Yes |
| `FLUME_PASSWORD` | Flume account password | - | Yes |
| `EXPORTER_PORT` | Port for the exporter | 8001 | No |
| `LOG_LEVEL` | Logging level | INFO | No |

### Customization

You can modify the following in `flume_exporter.py`:

- **Collection Interval**: Change `schedule.every(5).minutes` to adjust frequency
- **Data Retention**: Modify cache TTL values
- **Metrics**: Add custom metrics in the `FlumeMetrics` class
- **API Endpoints**: Extend the `FlumeAPI` class for additional endpoints

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify your API credentials
   - Check if your Flume account is active
   - Ensure your application is approved in the developer portal

2. **No Data Available**
   - Verify your Flume devices are online
   - Check if devices have recent activity
   - Review API rate limits

3. **High Memory Usage**
   - Reduce collection frequency
   - Implement data retention policies
   - Monitor cache sizes

### Logs

Enable debug logging by setting `LOG_LEVEL=DEBUG` in your environment.

### Health Checks

The exporter provides health checks at `/health` endpoint:

```bash
curl http://localhost:8001/health
```

## Monitoring and Alerting

### Example Prometheus Alerts

```yaml
groups:
  - name: flume_water_alerts
    rules:
      - alert: HighWaterFlow
        expr: flume_water_flow_rate > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High water flow detected"
          description: "Water flow rate is {{ $value }} gallons per minute"

      - alert: NoWaterData
        expr: up{job="flume-water-exporter"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Flume exporter is down"
          description: "No metrics from Flume Water exporter"
```

### Grafana Dashboards

Create dashboards to visualize:
- Daily/monthly water consumption trends
- Real-time flow rates
- Device status and health
- API performance metrics

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Flume API documentation
3. Open an issue on GitHub

## Changelog

### v1.0.0
- Initial release
- Basic water consumption metrics
- OAuth2 authentication
- Docker support
- Prometheus integration 