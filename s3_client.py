#!/usr/bin/env python
# -*- coding:utf-8 -*-
import io
import hashlib
import os
from urllib.parse import urlparse
from typing import Optional
import boto3
import requests
from botocore.exceptions import ClientError
from loguru import logger


class AwsS3Config:
    """AWS S3配置类"""
    def __init__(self, region_name: str, aws_access_key_id: str, 
                 aws_secret_access_key: str, bucket: str, 
                 root_dir: str = "", url: str = "", aws_token: str = ""):
        self.region_name = region_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_token = aws_token
        self.bucket = bucket
        self.root_dir = root_dir
        self.url = url


def _detect_content_type(data: bytes) -> str:
    """
    检测字节数据的内容类型(类似Go的http.DetectContentType)
    
    Args:
        data: 字节数据
    
    Returns:
        内容类型字符串
    """
    if not data:
        return 'application/octet-stream'
    
    # PNG
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image/png'
    # JPEG
    if data.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg'
    # GIF
    if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return 'image/gif'
    # PDF
    if data.startswith(b'%PDF'):
        return 'application/pdf'
    # ZIP (包括Office文档)
    if data.startswith(b'PK\x03\x04'):
        return 'application/zip'
    # JSON
    if data.startswith(b'{') or data.startswith(b'['):
        try:
            import json
            json.loads(data.decode('utf-8'))
            return 'application/json'
        except:
            pass
    if data.startswith(b'<?xml') or data.startswith(b'<svg') or data.startswith(b'<SVG'):
        try:
            decoded = data[:500].decode('utf-8', errors='ignore')
            if '<svg' in decoded.lower():
                return 'image/svg+xml'
        except:
            pass
    if data.startswith(b'<?xml') or data.startswith(b'<'):
        try:
            data.decode('utf-8')
            if b'<?xml' in data[:100] or (b'<' in data[:100] and b'>' in data[:100]):
                return 'application/xml'
        except:
            pass
    if b'<!DOCTYPE' in data[:100] or b'<html' in data[:100].lower():
        return 'text/html'
    try:
        data.decode('utf-8')
        return 'text/plain'
    except:
        pass
    
    return 'application/octet-stream'


def upload_aws_s3(data: bytes, conf: AwsS3Config, temp_file_name: str, 
                   content_type: str = "") -> tuple[Optional[str], Optional[Exception]]:
    try:
        s3_client = boto3.client(
            's3',
            region_name=conf.region_name,
            aws_access_key_id=conf.aws_access_key_id,
            aws_secret_access_key=conf.aws_secret_access_key,
            aws_session_token=conf.aws_token if conf.aws_token else None
        )
        
        size = len(data)
        
        temp_file_name = conf.root_dir + temp_file_name
        
        if not content_type:
            import mimetypes
            content_type, _ = mimetypes.guess_type(temp_file_name)
            if not content_type:
                content_type = _detect_content_type(data)
        
        put_object_params = {
            'Bucket': conf.bucket,
            'Key': temp_file_name,
            'Body': io.BytesIO(data),
            'ContentLength': size,
            'ContentType': content_type,
            'ContentDisposition': 'inline',
            'ServerSideEncryption': 'AES256',
            'StorageClass': 'INTELLIGENT_TIERING',
            # 'ACL': 'public-read',
        }
        
        s3_client.put_object(**put_object_params)
        
        logger.info(f"Successfully uploaded {temp_file_name} to S3 bucket {conf.bucket}")
        return temp_file_name, None
        
    except ClientError as e:
        logger.error(f"UploadAwsS3 - s3_client.put_object error: {e}")
        return None, e
    except Exception as e:
        logger.error(f"UploadAwsS3 - unexpected error: {e}")
        return None, e


def _get_file_extension_from_url(url: str, content_type: str = "") -> str:
    parsed_url = urlparse(url)
    path = parsed_url.path
    if '?' in path:
        path = path.split('?')[0]
    
    _, ext = os.path.splitext(path)
    if ext:
        return ext.lower()
    
    if content_type:
        content_type_map = {
            'image/png': '.png',
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/gif': '.gif',
            'image/svg+xml': '.svg',
            'image/webp': '.webp',
            'image/bmp': '.bmp',
            'image/x-icon': '.ico',
        }
        ext = content_type_map.get(content_type.lower())
        if ext:
            return ext
    
    return ''


def download_and_upload_image_to_s3(image_url: str, conf: AwsS3Config, 
                                    timeout: int = 30) -> tuple[Optional[str], Optional[Exception]]:
    try:
        logger.info(f"Downloading image from {image_url}")
        response = requests.get(image_url, timeout=timeout, stream=True)
        response.raise_for_status()
        image_data = response.content
        if not image_data:
            raise ValueError(f"Downloaded image data is empty from {image_url}")
        
        md5_hash = hashlib.md5(image_data).hexdigest()
        
        content_type = response.headers.get('Content-Type', '')
        file_ext = _get_file_extension_from_url(image_url, content_type)
        
        if not file_ext:
            detected_type = _detect_content_type(image_data)
            content_type_map = {
                'image/png': '.png',
                'image/jpeg': '.jpg',
                'image/jpg': '.jpg',
                'image/gif': '.gif',
                'image/svg+xml': '.svg',
                'image/webp': '.webp',
                'image/bmp': '.bmp',
                'image/x-icon': '.ico',
            }
            file_ext = content_type_map.get(detected_type, '')
        
        if not file_ext:
            file_ext = '.png'
            logger.warning(f"Could not determine file extension for {image_url}, using .png as default")
        
        file_name = f"{md5_hash}{file_ext}"
        
        s3_key, error = upload_aws_s3(image_data, conf, file_name, content_type or _detect_content_type(image_data))
        
        if error:
            logger.error(f"Failed to upload image to S3: {error}")
            return None, error
        
        if conf.url:
            s3_url = f"{conf.url.rstrip('/')}/{s3_key}"
        else:
            s3_url = f"https://{conf.bucket}.s3.{conf.region_name}.amazonaws.com/{s3_key}"
        
        logger.info(f"Successfully uploaded image to S3: {s3_url}")
        return s3_url, None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading image from {image_url}: {e}")
        return None, e
    except Exception as e:
        logger.error(f"Unexpected error in download_and_upload_image_to_s3: {e}")
        return None, e


if __name__ == '__main__':
    config = AwsS3Config(
        region_name='us-east-1',
        aws_access_key_id='xxx',
        aws_secret_access_key='xxx',
        bucket='xxx',
        root_dir='xxx/',
        url='xxx'
    )
    
    test_urls = [
        "https://img.rhea.finance/images/ethereum-chain-icon.svg",
        "https://coin-images.coingecko.com/coins/images/25057/large/Sweat_-_logo-nov-2025.png?1762411781",
        "https://assets.coingecko.com/coins/images/67977/standard/publicai.jpg?1754478612"
    ]
    
    for url in test_urls:
        print(f"\nTesting download and upload for: {url}")
        s3_url, error = download_and_upload_image_to_s3(url, config)
        if error:
            print(f"Failed: {error}")
        else:
            print(f"Success: {s3_url}")

