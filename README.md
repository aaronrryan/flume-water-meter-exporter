# Flume Water Prometheus Exporter

A Python-based Prometheus exporter that collects water flow rate data from the Flume Water API and exposes it as metrics for monitoring and alerting.

## Features

- **Real-time Water Flow Monitoring**: Collects current water flow rates from Flume devices
- **Device Management**: Supports multiple Flume devices with individual metrics
- **Prometheus Integration**: Exposes standard Prometheus metrics format
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **Health Monitoring**: Built-in health checks
- **Authentication**: Secure OAuth2 authentication with token refresh
- **Minimal Resource Usage**: Clean metrics output without default Python/process metrics

## Metrics Exposed

### Water Flow Metrics
- `flume_water_flow_rate`: Current water flow rate in gallons per minute

### Device Information
- `flume_device_info`: Device information including name, location, and connection status

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
  -p 8001:8001 \
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
# HELP flume_device_info Information about Flume devices
# TYPE flume_device_info gauge
flume_device_info{connected="True",device_id="12345",device_name="Flume flume2",location="Location 123",product="flume2",type="1"} 1.0

# HELP flume_water_flow_rate Current water flow rate in gallons per minute
# TYPE flume_water_flow_rate gauge
flume_water_flow_rate{device_id="12345",device_name="Flume flume2"} 2.3
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
- Data collection runs every minute by default
- The API has a limit of 1440 data points per query

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

- **Collection Interval**: Change `schedule.every(1).minutes` to adjust frequency
- **Data Retention**: Modify cache TTL values
- **Metrics**: Add custom metrics in the `FlumeMetrics` class
- **API Endpoints**: Extend the `FlumeAPI` class for additional endpoints

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify your API credentials
   - Check if your Flume account is active
   - Ensure your application is approved in the developer portal

2. **No Flow Rate Data**
   - Verify your Flume devices are online
   - Check if devices have recent water flow activity
   - Review API rate limits

3. **High Memory Usage**
   - Reduce collection frequency
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
- Real-time flow rates
- Device status and health
- Historical flow rate trends

## Development

### Project Structure

```
flume-water-meter-exporter/
├── flume_exporter.py      # Main exporter application
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker container definition
├── docker-compose.yml    # Docker Compose configuration
├── .env                  # Environment variables (create from env.example)
├── env.example           # Example environment file
└── README.md            # This file
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License. 