#!/usr/bin/env python3

import random
import boto3
from datetime import datetime
import time

class LogGenerator:
    def __init__(self, bucket_name):
        self.s3_client = boto3.client('s3')
        self.bucket_name = bucket_name
        
        self.endpoints = [
            '/api/users', '/api/products', '/api/orders',
            '/api/search', '/api/checkout', '/api/auth/login'
        ]
        
        self.status_codes = {
            200: 0.85,
            201: 0.05,
            400: 0.03,
            404: 0.02,
            500: 0.03,
            503: 0.02
        }
        
        self.log_levels = ['INFO', 'WARN', 'ERROR', 'DEBUG']
    
    def generate_log_entry(self):
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        status_code = random.choices(
            list(self.status_codes.keys()),
            weights=list(self.status_codes.values())
        )[0]
        
        if status_code < 400:
            response_time = random.uniform(50, 500)
        else:
            response_time = random.uniform(500, 3000)
        
        endpoint = random.choice(self.endpoints)
        method = random.choice(['GET', 'POST', 'PUT', 'DELETE'])
        
        if status_code >= 500:
            level = 'ERROR'
        elif status_code >= 400:
            level = 'WARN'
        else:
            level = random.choice(['INFO', 'DEBUG'])
        
        log_entry = (
            f"[{timestamp}] {level} - "
            f"{method} {endpoint} - "
            f"status: {status_code} - "
            f"response_time: {response_time:.2f}ms"
        )
        
        if status_code >= 500:
            errors = [
                'Database connection timeout',
                'Exception in query execution',
                'Failed to process request',
                'Internal server error occurred'
            ]
            log_entry += f" - {random.choice(errors)}"
        
        return log_entry
    
    def generate_log_file(self, num_entries=100):
        print(f"Generating log file with {num_entries} entries...")
        
        log_entries = []
        for _ in range(num_entries):
            log_entries.append(self.generate_log_entry())
        
        return '\n'.join(log_entries)
    
    def upload_to_s3(self, log_content, prefix='logs/'):
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        key = f"{prefix}application_{timestamp}.log"
        
        try:
            print(f"Uploading to s3://{self.bucket_name}/{key}")
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=log_content.encode('utf-8'),
                ContentType='text/plain'
            )
            
            print(f"Successfully uploaded log file")
            return key
        except Exception as e:
            print(f"Error uploading to S3: {e}")
            return None
    
    def generate_and_upload(self, num_files=5, entries_per_file=100):
        print(f"Generating {num_files} log files...\n")
        
        uploaded_files = []
        
        for i in range(num_files):
            print(f"\nFile {i+1}/{num_files}")
            log_content = self.generate_log_file(entries_per_file)
            key = self.upload_to_s3(log_content)
            
            if key:
                uploaded_files.append(key)
            
            if i < num_files - 1:
                time.sleep(1)
        
        print(f"\nGenerated and uploaded {len(uploaded_files)} log files")
        return uploaded_files


def main():
    print("Sample Log Generator for Cloud Monitoring\n")
    
    S3_BUCKET = 'my-app-logs-bucket'
    NUM_FILES = 3
    ENTRIES_PER_FILE = 150
    
    generator = LogGenerator(S3_BUCKET)
    generator.generate_and_upload(NUM_FILES, ENTRIES_PER_FILE)
    
    print("\nLog generation complete!")


if __name__ == "__main__":
    main()  