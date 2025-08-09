# Load Testing for E-commerce Microservices

This directory contains comprehensive load testing scripts for the e-commerce microservices system using Locust.

## Overview

The load testing suite includes various scenarios to test different aspects of the system:

- **Baseline Testing**: Normal user behavior patterns
- **Stress Testing**: Gradually increasing load to find breaking points
- **Spike Testing**: Sudden load increases to test elasticity
- **Endurance Testing**: Extended testing to identify memory leaks and performance degradation
- **Black Friday Testing**: High-traffic e-commerce scenarios
- **Chaos Resilience Testing**: Testing with chaos engineering experiments
- **API-Only Testing**: Testing API endpoints without web interface

## Files

- `comprehensive_load_test.py`: Main Locust test file with user behaviors
- `run_tests.py`: Test runner script with various scenarios
- `README.md`: This documentation file

## Prerequisites

1. **Install Dependencies**:
   ```bash
   pip install locust requests
   ```

2. **System Requirements**:
   - Python 3.8+
   - Running e-commerce microservices system
   - Sufficient system resources for load generation

## Quick Start

### 1. Basic Load Test
```bash
python run_tests.py --test baseline --users 10 --duration 300
```

### 2. Stress Test
```bash
python run_tests.py --test stress --users 100 --duration 600
```

### 3. Complete Test Suite
```bash
python run_tests.py --test suite
```

## Test Scenarios

### Baseline Test
- **Purpose**: Establish performance baseline
- **Users**: 10 concurrent users
- **Duration**: 5 minutes
- **Behavior**: Normal browsing, shopping, and ordering

### Stress Test
- **Purpose**: Find system breaking point
- **Users**: Gradually increase to 100+
- **Duration**: 10 minutes
- **Behavior**: Sustained high load

### Spike Test
- **Purpose**: Test system elasticity
- **Users**: Sudden spike to 200 users
- **Duration**: 5 minutes
- **Behavior**: Immediate high load

### Endurance Test
- **Purpose**: Test for memory leaks and degradation
- **Users**: 50 sustained users
- **Duration**: 1+ hours
- **Behavior**: Continuous load over time

### Black Friday Test
- **Purpose**: Simulate high-traffic sales events
- **Users**: 500+ users
- **Duration**: 15 minutes
- **Behavior**: Intensive browsing and purchasing

### Chaos Resilience Test
- **Purpose**: Test system resilience under failure conditions
- **Users**: 50 users
- **Duration**: 10 minutes
- **Behavior**: Normal load with chaos experiments

### API-Only Test
- **Purpose**: Test API performance without web interface
- **Users**: 30 API clients
- **Duration**: 5 minutes
- **Behavior**: Direct API calls

## User Behaviors

### EcommerceUser (Weight: 10)
- Browse products catalog
- Search for items
- Manage shopping cart
- Place orders using SAGA pattern
- Check order status
- Process payments

### AdminUser (Weight: 1)
- Monitor system health
- Manage inventory
- View order statistics
- Monitor payments
- Trigger chaos experiments
- Test SAGA patterns

### APIUser (Weight: 2)
- Access products via API
- Check inventory via API
- Place orders via API
- Pure API interactions

### BlackFridayScenario (Weight: 5)
- Intensive browsing
- Quick purchase decisions
- High-frequency interactions

## Monitoring During Tests

### Key Metrics to Watch

1. **Response Times**:
   - Average response time
   - 95th percentile response time
   - Maximum response time

2. **Throughput**:
   - Requests per second
   - Successful requests
   - Failed requests

3. **Error Rates**:
   - HTTP error rates
   - Application errors
   - Timeout errors

4. **System Resources**:
   - CPU utilization
   - Memory usage
   - Database connections
   - Redis performance

5. **Business Metrics**:
   - Order completion rate
   - Payment success rate
   - Inventory accuracy
   - SAGA success rate

### System Health Endpoints

Monitor these endpoints during load tests:
- `/api/gateway/health/` - Overall system health
- `/api/resilience/health/` - Circuit breaker states
- `/api/saga/health/` - SAGA transaction health
- `/prometheus/metrics` - Detailed metrics

## Running Tests

### Interactive Mode (Web UI)
```bash
locust -f comprehensive_load_test.py --host http://localhost:8000
```
Then open http://localhost:8089 in your browser.

### Headless Mode
```bash
locust -f comprehensive_load_test.py --host http://localhost:8000 \
    --users 50 --spawn-rate 5 --run-time 300s --headless
```

### Custom Scenarios
```bash
# Baseline test
python run_tests.py --test baseline --users 10 --duration 300

# Stress test
python run_tests.py --test stress --users 100 --duration 600

# Spike test
python run_tests.py --test spike --users 200 --duration 300

# Endurance test (1 hour)
python run_tests.py --test endurance --users 50 --duration 3600

# Black Friday simulation
python run_tests.py --test black_friday --users 500 --duration 900

# Chaos resilience test
python run_tests.py --test chaos_resilience --users 50 --duration 600

# API-only test
python run_tests.py --test api_only --users 30 --duration 300

# Complete test suite
python run_tests.py --test suite
```

## Results and Reporting

### Output Files
Load test results are saved in the `load_test_results/` directory:

- **HTML Reports**: `{test_type}_test_YYYYMMDD_HHMMSS.html`
- **CSV Data**: `{test_type}_test_stats.csv`, `{test_type}_test_failures.csv`
- **JSON Summary**: `{test_type}_summary_YYYYMMDD_HHMMSS.json`
- **Suite Report**: `test_suite_report_YYYYMMDD_HHMMSS.json`

### Analyzing Results

1. **HTML Reports**: Open in browser for interactive charts and graphs
2. **CSV Data**: Import into Excel/Google Sheets for analysis
3. **JSON Summary**: Programmatic analysis and CI/CD integration

### Key Performance Indicators (KPIs)

1. **Response Time Targets**:
   - Average: < 200ms
   - 95th percentile: < 500ms
   - Maximum: < 2000ms

2. **Throughput Targets**:
   - Handle 1000+ RPS
   - Maintain performance under load

3. **Error Rate Targets**:
   - < 1% error rate under normal load
   - < 5% error rate under stress

4. **Availability Targets**:
   - 99.9% uptime
   - Graceful degradation under extreme load

## Troubleshooting

### Common Issues

1. **Connection Refused**:
   - Ensure the application is running
   - Check the host URL
   - Verify network connectivity

2. **High Error Rates**:
   - Check system resources
   - Review application logs
   - Monitor database performance

3. **Slow Response Times**:
   - Check CPU and memory usage
   - Monitor database queries
   - Review Redis performance

4. **Authentication Failures**:
   - Verify test user credentials
   - Check JWT token expiration
   - Review authentication service logs

### Performance Tuning

1. **Database Optimization**:
   - Add database indexes
   - Optimize slow queries
   - Configure connection pooling

2. **Caching Strategy**:
   - Implement Redis caching
   - Add application-level caching
   - Use CDN for static assets

3. **Scaling**:
   - Horizontal scaling with multiple instances
   - Load balancer configuration
   - Auto-scaling policies

## Integration with CI/CD

### Example GitHub Actions Workflow
```yaml
name: Load Tests
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: pip install locust requests
      - name: Run Load Tests
        run: python load_test/run_tests.py --test suite
      - name: Upload Results
        uses: actions/upload-artifact@v2
        with:
          name: load-test-results
          path: load_test/load_test_results/
```

## Best Practices

1. **Test Environment**:
   - Use production-like environment
   - Separate test data
   - Monitor system resources

2. **Test Strategy**:
   - Start with baseline tests
   - Gradually increase load
   - Test failure scenarios

3. **Monitoring**:
   - Monitor all system components
   - Set up alerts for anomalies
   - Review results regularly

4. **Continuous Testing**:
   - Integrate into CI/CD pipeline
   - Run tests regularly
   - Track performance trends

## Advanced Features

### Custom User Behaviors
Extend the test scenarios by creating custom user classes:

```python
class CustomUser(HttpUser):
    wait_time = between(1, 3)
    
    @task
    def custom_behavior(self):
        # Implement custom test logic
        pass
```

### Dynamic Load Patterns
Implement custom load patterns:

```python
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    # Custom test initialization
    pass
```

### Custom Metrics
Add custom metrics collection:

```python
@events.request.add_listener
def record_custom_metrics(request_type, name, response_time, **kwargs):
    # Custom metrics logic
    pass
```

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review application logs
3. Monitor system metrics
4. Contact the development team
