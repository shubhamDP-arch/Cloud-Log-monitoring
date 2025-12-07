#!/bin/bash

set -e

echo "Cloud Log Monitoring & Auto-Scaling Setup"
echo "============================================"
echo ""

read -p "Enter S3 bucket name for logs: " BUCKET_NAME
read -p "Enter AWS region (default: us-east-1): " REGION
REGION=${REGION:-us-east-1}

read -p "Enter Auto Scaling Group name: " ASG_NAME
read -p "Enter Launch Template name: " TEMPLATE_NAME
read -p "Enter EC2 Key Pair name: " KEY_PAIR
read -p "Enter Security Group ID: " SECURITY_GROUP

echo ""
echo "Configuration:"
echo "  S3 Bucket: $BUCKET_NAME"
echo "  Region: $REGION"
echo "  ASG Name: $ASG_NAME"
echo "  Template: $TEMPLATE_NAME"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 1
fi

echo ""
echo "Step 1: Creating S3 Bucket..."
if aws s3 mb s3://$BUCKET_NAME --region $REGION 2>/dev/null; then
    echo "S3 bucket created successfully"
    
    aws s3api put-bucket-versioning \
        --bucket $BUCKET_NAME \
        --versioning-configuration Status=Enabled \
        --region $REGION
    echo "Versioning enabled"
    
    aws s3api put-object \
        --bucket $BUCKET_NAME \
        --key logs/ \
        --region $REGION
    echo "Logs directory created"
else
    echo "Bucket may already exist or creation failed"
fi

echo ""
echo "Step 2: Creating IAM Role for EC2..."

cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

if aws iam create-role \
    --role-name EC2-CloudWatch-Role \
    --assume-role-policy-document file:///tmp/trust-policy.json 2>/dev/null; then
    echo "IAM role created"
else
    echo "Role may already exist"
fi

cat > /tmp/cloudwatch-policy.json <<EOF
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
        "logs:PutLogEvents",
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "*"
    }
  ]
}
EOF

if aws iam put-role-policy \
    --role-name EC2-CloudWatch-Role \
    --policy-name CloudWatch-S3-Policy \
    --policy-document file:///tmp/cloudwatch-policy.json 2>/dev/null; then
    echo "IAM policy attached"
fi

if aws iam create-instance-profile \
    --instance-profile-name EC2-CloudWatch-Profile 2>/dev/null; then
    echo "Instance profile created"
    
    aws iam add-role-to-instance-profile \
        --instance-profile-name EC2-CloudWatch-Profile \
        --role-name EC2-CloudWatch-Role 2>/dev/null || true
    echo "Role added to instance profile"
else
    echo "Instance profile may already exist"
fi

echo ""
echo "Step 3: Creating Launch Template..."

AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text \
    --region $REGION)

echo "Using AMI: $AMI_ID"

cat > /tmp/user-data.sh <<'EOF'
#!/bin/bash
yum update -y
yum install -y amazon-cloudwatch-agent
yum install -y python3 python3-pip

echo "Application installed" > /var/log/app-install.log
EOF

USER_DATA=$(base64 /tmp/user-data.sh | tr -d '\n')

if aws ec2 create-launch-template \
    --launch-template-name $TEMPLATE_NAME \
    --version-description "Version 1" \
    --launch-template-data "{
        \"ImageId\": \"$AMI_ID\",
        \"InstanceType\": \"t2.micro\",
        \"KeyName\": \"$KEY_PAIR\",
        \"SecurityGroupIds\": [\"$SECURITY_GROUP\"],
        \"IamInstanceProfile\": {\"Name\": \"EC2-CloudWatch-Profile\"},
        \"UserData\": \"$USER_DATA\"
    }" \
    --region $REGION 2>/dev/null; then
    echo "Launch template created"
else
    echo "Launch template may already exist"
fi

echo ""
echo "Step 4: Creating Auto Scaling Group..."

if aws autoscaling create-auto-scaling-group \
    --auto-scaling-group-name $ASG_NAME \
    --launch-template "LaunchTemplateName=$TEMPLATE_NAME,Version=\$Latest" \
    --min-size 1 \
    --max-size 5 \
    --desired-capacity 2 \
    --vpc-zone-identifier "$(aws ec2 describe-subnets --region $REGION --query 'Subnets[0:2].SubnetId' --output text | tr '\t' ',')" \
    --health-check-type EC2 \
    --health-check-grace-period 300 \
    --region $REGION 2>/dev/null; then
    echo "Auto Scaling Group created"
else
    echo "Auto Scaling Group may already exist"
fi

echo ""
echo "Step 5: Creating IAM Policy for Monitoring Script..."

cat > /tmp/monitor-policy.json <<EOF
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
EOF

POLICY_ARN=$(aws iam create-policy \
    --policy-name CloudLogMonitorPolicy \
    --policy-document file:///tmp/monitor-policy.json \
    --query 'Policy.Arn' \
    --output text 2>/dev/null || \
    aws iam list-policies --query "Policies[?PolicyName=='CloudLogMonitorPolicy'].Arn" --output text)

echo "Monitoring policy created/found: $POLICY_ARN"
echo ""
echo "Attach this policy to your IAM user/role:"
echo "aws iam attach-user-policy --user-name YOUR_USER --policy-arn $POLICY_ARN"

rm -f /tmp/trust-policy.json /tmp/cloudwatch-policy.json /tmp/monitor-policy.json /tmp/user-data.sh

echo ""
echo "AWS Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Update config.json with your settings:"
echo "   - s3_bucket: $BUCKET_NAME"
echo "   - auto_scaling_group: $ASG_NAME"
echo ""
echo "2. Attach CloudLogMonitorPolicy to your IAM user"
echo ""
echo "3. Run the log generator:"
echo "   python log_generator.py"
echo ""
echo "4. Run the monitoring script:"
echo "   python log_monitor.py"
echo ""