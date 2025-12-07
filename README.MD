# Cloud Log Monitoring & Auto-Scaling Tool

A lightweight log monitoring and auto-scaling system for AWS EC2 instances. Parses application logs from S3, tracks key metrics (errors, slow responses), and automatically adjusts EC2 capacity based on CPU/memory load and application performance.

## 🎯 Features

- **Log Monitoring**: Downloads and parses application logs from S3
- **Metric Tracking**: Monitors error rates, response times, and slow requests
- **Auto-Scaling**: Adjusts EC2 capacity based on CloudWatch metrics and log analysis
- **Threshold-Based Triggers**: Configurable thresholds for CPU, errors, and response times

## 📁 Project Structure

```
cloud-log-monitor/
├── log_monitor.py          # Main monitoring script
├── log_generator.py        # Sample log generator for testing
├── requirements.txt        # Python dependencies
├── config.json            # Configuration file
└── README.md              # This file
```

## 🔧 Prerequisites

1. **AWS Account** with appropriate permissions
2. **Python 3.8+** installed
3. **AWS CLI** configured with credentials
4. **IAM Permissions** for:
   - S3 (read)
   - EC2 (describe instances, CloudWatch metrics)
   - Auto Scaling (describe and modify groups)
   - CloudWatch (get metrics)

## 📦 Installation

### 1. Clone or Download the Project

```bash
mkdir cloud-log-monitor
cd cloud-log-monitor
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure AWS Credentials

```bash
aws configure
```

Enter your:
- AWS Access Key ID
- AWS Secret Access Key
- Default region (e.g., us-east-1)
- Output format (json)

## 🚀 AWS Setup

### 1. Create S3 Bucket for Logs

```bash
# Create bucket
aws s3 mb s3://my-app-logs-bucket

# Enable versioning (optional)
aws s3api put-bucket-versioning \
  --bucket my-app-logs-bucket \
  --versioning-configuration Status=Enabled
```

### 2. Create EC2 Auto Scaling Group

```bash
# Create launch template
aws ec2 create-launch-template \
  --launch-template-name my-app-template \
  --version-description "Version 1" \
  --launch-template-data '{
    "ImageId": "ami-0c55b159cbfafe1f0",
    "InstanceType": "t2.micro",
    "KeyName": "my-key-pair",
    "SecurityGroupIds": ["sg-xxxxxxxxx"],
    "IamInstanceProfile": {"Name": "EC2-CloudWatch-Role"},
    "UserData": ""
  }'

# Create Auto Scaling Group
aws autoscaling create-auto-scaling-group \
  --auto-scaling-group-name my-app-asg \
  --launch-template LaunchTemplateName=my-app-template,Version='$Latest' \
  --min-size 1 \
  --max-size 5 \
  --desired-capacity 2 \
  --availability-zones us-east-1a us-east-1b \
  --health-check-type EC2 \
  --health-check-grace-period 300
```

### 3. Create IAM Role (if not exists)

Create a role with this policy for EC2 instances:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### 4. IAM Policy for Monitoring Script

Your AWS user/role needs this policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "ec2:DescribeInstances",
        "cloudwatch:GetMetricStatistics",
        "autoscaling:DescribeAutoScalingGroups",
        "autoscaling:SetDesiredCapacity"
      ],
      "Resource": "*"
    }
  ]
}
```

## 🎮 Usage

### Generate Sample Logs (for testing)

```bash
python log_generator.py
```

Edit the script first to set your S3 bucket name:
```python
S3_BUCKET = 'my-app-logs-bucket'  # Your bucket name
```

### Run the Monitoring Script

```bash
python log_monitor.py
```

Edit configuration in the script:
```python
S3_BUCKET = 'my-app-logs-bucket'
LOG_PREFIX = 'logs/'
AUTO_SCALING_GROUP = 'my-app-asg'
```

### Expected Output

```
🚀 Cloud Log Monitoring & Auto-Scaling Tool

📥 Downloading logs from s3://my-app-logs-bucket/logs/
  └─ Fetching logs/application_20241208_120000.log

📊 Parsing logs for metrics...

==================================================
📈 METRICS SUMMARY
==================================================
Total Requests:     450
Error Count:        15
Slow Responses:     23
Avg Response Time:  342.56ms
Error Rate:         3.33%
Slow Response Rate: 5.11%
==================================================

🖥️  Fetching EC2 instance metrics...
  └─ i-1234567890abcdef: CPU 75.32%

🔍 Checking auto-scaling conditions...
⬆️  SCALE UP RECOMMENDED
  └─ High CPU utilization: 75.32%

🎯 Current ASG Configuration:
  └─ Desired Capacity: 2
  └─ Min Size: 1
  └─ Max Size: 5

⬆️  Scaling up to 3 instances
✅ Successfully updated capacity to 3

✅ Monitoring cycle complete
```

## 📊 Metrics Tracked

| Metric | Description | Threshold |
|--------|-------------|-----------|
| Error Count | Number of errors/exceptions | 5% of total |
| Slow Responses | Requests > 1000ms | 10% of total |
| Avg Response Time | Mean response time | N/A |
| CPU Utilization | Average CPU across instances | 70% (high), 20% (low) |

## ⚙️ Configuration

### Scaling Thresholds

Edit in `log_monitor.py`:

```python
CPU_HIGH_THRESHOLD = 70      # Scale up at 70% CPU
CPU_LOW_THRESHOLD = 20       # Scale down at 20% CPU
ERROR_RATE_THRESHOLD = 5     # Scale up at 5% error rate
SLOW_RESPONSE_THRESHOLD = 10 # Scale up at 10% slow responses
```

### Log Patterns

The script recognizes these log patterns:

```python
# Error detection
error_pattern = r'(ERROR|FATAL|Exception|Failed)'

# Response time extraction
response_time_pattern = r'response_time[:\s]+(\d+\.?\d*)ms'

# HTTP status codes
status_code_pattern = r'status[:\s]+(\d{3})'
```

## 🔄 Scheduling (Production)

### Using Cron

```bash
# Edit crontab
crontab -e

# Run every 5 minutes
*/5 * * * * cd /path/to/cloud-log-monitor && /usr/bin/python3 log_monitor.py >> /var/log/monitor.log 2>&1
```

### Using AWS Lambda (Recommended)

1. Package the script:
```bash
pip install -r requirements.txt -t package/
cp log_monitor.py package/
cd package && zip -r ../lambda_function.zip .
```

2. Create Lambda function:
```bash
aws lambda create-function \
  --function-name log-monitor \
  --runtime python3.11 \
  --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
  --handler log_monitor.main \
  --zip-file fileb://lambda_function.zip \
  --timeout 60 \
  --memory-size 256
```

3. Add CloudWatch Events trigger (every 5 minutes):
```bash
aws events put-rule \
  --name log-monitor-schedule \
  --schedule-expression "rate(5 minutes)"

aws events put-targets \
  --rule log-monitor-schedule \
  --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT:function:log-monitor"
```

## 📝 Sample Log Format

The monitoring script expects logs in this format:

```
[2024-12-08 12:34:56.789] INFO - GET /api/users - status: 200 - response_time: 145.32ms
[2024-12-08 12:34:57.123] ERROR - POST /api/orders - status: 500 - response_time: 2341.56ms - Database connection timeout
[2024-12-08 12:34:58.456] WARN - GET /api/search - status: 404 - response_time: 89.12ms
```

## 🐛 Troubleshooting

### "NoCredentialsError"
- Run `aws configure` and enter valid credentials
- Check IAM permissions

### "AccessDenied" for S3
- Verify bucket name is correct
- Check S3 bucket policy allows your IAM user/role

### "Bucket not found"
- Create bucket: `aws s3 mb s3://your-bucket-name`
- Verify region matches your configuration

### No scaling action taken
- Check CloudWatch metrics are available (5-10 min delay)
- Verify Auto Scaling Group exists
- Review threshold values

## 🔐 Security Best Practices

1. **Use IAM Roles** instead of access keys when possible
2. **Encrypt S3 bucket** with server-side encryption
3. **Restrict S3 bucket** access to specific IAM roles
4. **Use VPC endpoints** for S3 access from EC2
5. **Enable CloudTrail** for audit logging
6. **Rotate credentials** regularly

## 📈 Enhancements

Potential improvements:

- [ ] Add SNS notifications for scaling events
- [ ] Implement more sophisticated anomaly detection
- [ ] Add dashboard with real-time metrics
- [ ] Support multiple log formats
- [ ] Add predictive scaling based on patterns
- [ ] Integrate with Prometheus/Grafana
- [ ] Add unit tests and integration tests

## 📄 License

MIT License - feel free to use and modify for your projects.

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📧 Contact

For questions or issues, please open a GitHub issue.

---

**Built with ❤️ for AWS infrastructure automation**