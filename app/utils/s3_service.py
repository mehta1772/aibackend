"""
AWS S3 Service
Handles document uploads and management
"""

import os
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
import uuid
from datetime import datetime
from typing import Optional, BinaryIO
import mimetypes

# AWS Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "crm-documents-bucket")

# Initialize S3 client
s3_config = Config(
    region_name=AWS_REGION,
    signature_version='s3v4',
    retries={
        'max_attempts': 3,
        'mode': 'standard'
    }
)

def get_s3_client():
    """Get S3 client with credentials"""
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        return boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            config=s3_config
        )
    return None

async def upload_document(
    file_content: bytes,
    file_name: str,
    booking_id: str,
    stage: str,
    content_type: Optional[str] = None
) -> Optional[str]:
    """
    Upload document to S3
    Returns the S3 URL of the uploaded file
    """
    s3_client = get_s3_client()
    
    if not s3_client:
        # For development without S3, return a mock URL
        mock_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/documents/{booking_id}/{stage}/{file_name}"
        print(f"Mock S3 upload: {mock_url}")
        return mock_url
    
    try:
        # Generate unique key
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        file_extension = os.path.splitext(file_name)[1]
        s3_key = f"documents/{booking_id}/{stage}/{timestamp}_{unique_id}{file_extension}"
        
        # Determine content type
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_name)
            content_type = content_type or 'application/octet-stream'
        
        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
            Metadata={
                'booking_id': booking_id,
                'stage': stage,
                'original_filename': file_name
            }
        )
        
        # Generate URL
        url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
        return url
        
    except ClientError as e:
        print(f"S3 upload error: {str(e)}")
        return None

async def delete_document(file_url: str) -> bool:
    """Delete document from S3"""
    s3_client = get_s3_client()
    
    if not s3_client:
        print(f"Mock S3 delete: {file_url}")
        return True
    
    try:
        # Extract key from URL
        # URL format: https://bucket.s3.region.amazonaws.com/key
        s3_key = file_url.split(f"{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/")[1]
        
        s3_client.delete_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key
        )
        return True
        
    except (ClientError, IndexError) as e:
        print(f"S3 delete error: {str(e)}")
        return False

async def get_presigned_url(file_url: str, expires_in: int = 3600) -> Optional[str]:
    """
    Generate a presigned URL for secure document access
    expires_in: URL expiration time in seconds (default 1 hour)
    """
    s3_client = get_s3_client()
    
    if not s3_client:
        return file_url  # Return original URL in dev mode
    
    try:
        # Extract key from URL
        s3_key = file_url.split(f"{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/")[1]
        
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET_NAME,
                'Key': s3_key
            },
            ExpiresIn=expires_in
        )
        return presigned_url
        
    except (ClientError, IndexError) as e:
        print(f"Presigned URL error: {str(e)}")
        return None

async def list_documents(booking_id: str, stage: Optional[str] = None) -> list:
    """List all documents for a booking"""
    s3_client = get_s3_client()
    
    if not s3_client:
        return []
    
    try:
        prefix = f"documents/{booking_id}/"
        if stage:
            prefix += f"{stage}/"
        
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=prefix
        )
        
        documents = []
        for obj in response.get('Contents', []):
            documents.append({
                'key': obj['Key'],
                'size': obj['Size'],
                'last_modified': obj['LastModified'].isoformat(),
                'url': f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{obj['Key']}"
            })
        
        return documents
        
    except ClientError as e:
        print(f"S3 list error: {str(e)}")
        return []
