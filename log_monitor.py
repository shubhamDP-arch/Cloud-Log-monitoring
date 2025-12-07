#!/usr/bin/env python3

import boto3
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict
import time

class LogMonitor:
    def __init__(self, bucket_name, ec2_region='us-east-1'):
        self.s3_client = boto3.client('s3')
        self.ec2_client = boto3.client('ec2', region_name=ec2_region)
        self.cloudwatch_client = boto3.client('cloudwatch', region_name=ec2_region)
        self.bucket_name = bucket_name
        self.metrics = {
            'error_count': 0,
            'slow_responses': 0,
            'total_requests': 0,
            'avg_response_time': 0
        }
    
    def download_logs_from_s3(self, prefix='logs/'):
        print(f"Downloading logs from s3://{self.bucket_name}/{prefix}")
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                print("No log files found")
                return []
            
            log_contents = []
            for obj in response['Contents'][-10:]:
                key = obj['Key']
                print(f"Fetching {key}")
                
                obj_data = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
                content = obj_data['Body'].read().decode('utf-8')
                log_contents.append(content)
            
            return log_contents
        except Exception as e:
            print(f"Error downloading logs: {e}")
            return []
    
    def parse_logs(self, log_contents):
        print("\nParsing logs for metrics...")
        
        response_times = []
        error_pattern = r'(ERROR|FATAL|Exception|Failed)'
        response_time_pattern = r'response_time[:\s]+(\d+\.?\d*)ms'
        status_code_pattern = r'status[:\s]+(\d{3})'
        
        for log_content in log_contents:
            lines = log_content.split('\n')
            
            for line in lines:
                if not line.strip():
                    continue
                
                self.metrics['total_requests'] += 1
                
                if re.search(error_pattern, line, re.IGNORECASE):
                    self.metrics['error_count'] += 1
                
                time_match = re.search(response_time_pattern, line)
                if time_match:
                    response_time = float(time_match.group(1))
                    response_times.append(response_time)
                    
                    if response_time > 1000:
                        self.metrics['slow_responses'] += 1
                
                status_match = re.search(status_code_pattern, line)
                if status_match:
                    status_code = int(status_match.group(1))
                    if status_code >= 500:
                        self.metrics['error_count'] += 1
        
        if response_times:
            self.metrics['avg_response_time'] = sum(response_times) / len(response_times)
        
        self.print_metrics()
        return self.metrics
    
    def print_metrics(self):
        print("\n" + "="*50)
        print("METRICS SUMMARY")
        print("="*50)
        print(f"Total Requests:     {self.metrics['total_requests']}")
        print(f"Error Count:        {self.metrics['error_count']}")
        print(f"Slow Responses:     {self.metrics['slow_responses']}")
        print(f"Avg Response Time:  {self.metrics['avg_response_time']:.2f}ms")
        
        if self.metrics['total_requests'] > 0:
            error_rate = (self.metrics['error_count'] / self.metrics['total_requests']) * 100
            slow_rate = (self.metrics['slow_responses'] / self.metrics['total_requests']) * 100
            print(f"Error Rate:         {error_rate:.2f}%")
            print(f"Slow Response Rate: {slow_rate:.2f}%")
        print("="*50 + "\n")
    
    def get_ec2_metrics(self, instance_ids):
        print("Fetching EC2 instance metrics...")
        
        metrics_data = {}
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=5)
        
        for instance_id in instance_ids:
            try:
                cpu_response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName='CPUUtilization',
                    Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,
                    Statistics=['Average']
                )
                
                cpu_util = 0
                if cpu_response['Datapoints']:
                    cpu_util = cpu_response['Datapoints'][-1]['Average']
                
                metrics_data[instance_id] = {
                    'cpu_utilization': cpu_util
                }
                
                print(f"{instance_id}: CPU {cpu_util:.2f}%")
                
            except Exception as e:
                print(f"Error fetching metrics for {instance_id}: {e}")
        
        return metrics_data
    
    def check_scaling_conditions(self, ec2_metrics):
        print("\nChecking auto-scaling conditions...")
        
        CPU_HIGH_THRESHOLD = 70
        CPU_LOW_THRESHOLD = 20
        ERROR_RATE_THRESHOLD = 5
        SLOW_RESPONSE_THRESHOLD = 10
        
        scale_up = False
        scale_down = False
        reasons = []
        
        if ec2_metrics:
            avg_cpu = sum(m['cpu_utilization'] for m in ec2_metrics.values()) / len(ec2_metrics)
            
            if avg_cpu > CPU_HIGH_THRESHOLD:
                scale_up = True
                reasons.append(f"High CPU utilization: {avg_cpu:.2f}%")
            elif avg_cpu < CPU_LOW_THRESHOLD:
                scale_down = True
                reasons.append(f"Low CPU utilization: {avg_cpu:.2f}%")
        
        if self.metrics['total_requests'] > 0:
            error_rate = (self.metrics['error_count'] / self.metrics['total_requests']) * 100
            if error_rate > ERROR_RATE_THRESHOLD:
                scale_up = True
                reasons.append(f"High error rate: {error_rate:.2f}%")
        
        if self.metrics['total_requests'] > 0:
            slow_rate = (self.metrics['slow_responses'] / self.metrics['total_requests']) * 100
            if slow_rate > SLOW_RESPONSE_THRESHOLD:
                scale_up = True
                reasons.append(f"High slow response rate: {slow_rate:.2f}%")
        
        if scale_up:
            print("SCALE UP RECOMMENDED")
            for reason in reasons:
                print(f"  {reason}")
            return 'scale_up'
        elif scale_down:
            print("SCALE DOWN RECOMMENDED")
            for reason in reasons:
                print(f"  {reason}")
            return 'scale_down'
        else:
            print("Current capacity is adequate")
            return 'maintain'
    
    def trigger_auto_scaling(self, action, auto_scaling_group_name):
        autoscaling_client = boto3.client('autoscaling')
        
        try:
            response = autoscaling_client.describe_auto_scaling_groups(
                AutoScalingGroupNames=[auto_scaling_group_name]
            )
            
            if not response['AutoScalingGroups']:
                print(f"Auto Scaling Group '{auto_scaling_group_name}' not found")
                return
            
            asg = response['AutoScalingGroups'][0]
            current_capacity = asg['DesiredCapacity']
            min_size = asg['MinSize']
            max_size = asg['MaxSize']
            
            print(f"\nCurrent ASG Configuration:")
            print(f"  Desired Capacity: {current_capacity}")
            print(f"  Min Size: {min_size}")
            print(f"  Max Size: {max_size}")
            
            new_capacity = current_capacity
            
            if action == 'scale_up' and current_capacity < max_size:
                new_capacity = min(current_capacity + 1, max_size)
                print(f"\nScaling up to {new_capacity} instances")
                
            elif action == 'scale_down' and current_capacity > min_size:
                new_capacity = max(current_capacity - 1, min_size)
                print(f"\nScaling down to {new_capacity} instances")
            else:
                print(f"\nNo scaling action taken (at capacity limits)")
                return
            
            autoscaling_client.set_desired_capacity(
                AutoScalingGroupName=auto_scaling_group_name,
                DesiredCapacity=new_capacity,
                HonorCooldown=True
            )
            
            print(f"Successfully updated capacity to {new_capacity}")
            
        except Exception as e:
            print(f"Error during auto-scaling: {e}")


def main():
    print("Cloud Log Monitoring & Auto-Scaling Tool\n")
    
    S3_BUCKET = 'my-app-logs-bucket'
    LOG_PREFIX = 'logs/'
    AUTO_SCALING_GROUP = 'my-app-asg'
    INSTANCE_IDS = []
    
    monitor = LogMonitor(S3_BUCKET)
    
    log_contents = monitor.download_logs_from_s3(LOG_PREFIX)
    if log_contents:
        monitor.parse_logs(log_contents)
    
    ec2_metrics = monitor.get_ec2_metrics(INSTANCE_IDS) if INSTANCE_IDS else {}
    
    scaling_decision = monitor.check_scaling_conditions(ec2_metrics)
    
    if scaling_decision in ['scale_up', 'scale_down']:
        monitor.trigger_auto_scaling(scaling_decision, AUTO_SCALING_GROUP)
    
    print("\nMonitoring cycle complete\n")


if __name__ == "__main__":
    main()