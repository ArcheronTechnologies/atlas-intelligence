"""
Model Storage Manager for Atlas Intelligence
Supports S3-compatible storage (AWS S3, DigitalOcean Spaces, Cloudflare R2, etc.)

This enables model updates WITHOUT code redeployment:
1. Upload new model to S3
2. Update version in S3 config
3. Models auto-download on next startup or reload endpoint

Railway-optimized: Minimal redeployments, maximum flexibility
"""

import logging
import os
import asyncio
from pathlib import Path
from typing import Optional, Dict
import hashlib
import json
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import boto3, but make it optional for local dev
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logger.warning("boto3 not installed - S3 model storage disabled (local dev mode)")


class ModelStorage:
    """
    S3-compatible model storage manager

    Environment Variables:
        MODEL_STORAGE_TYPE: 's3', 'local' (default: 'local')
        S3_ENDPOINT_URL: Custom endpoint for DigitalOcean/R2 (optional for AWS)
        S3_BUCKET: Bucket name (e.g., 'atlas-models')
        S3_ACCESS_KEY: Access key ID
        S3_SECRET_KEY: Secret access key
        S3_REGION: Region (default: 'us-east-1')

    Supported Providers:
        - AWS S3: Don't set S3_ENDPOINT_URL
        - DigitalOcean Spaces: https://nyc3.digitaloceanspaces.com
        - Cloudflare R2: https://[account_id].r2.cloudflarestorage.com
        - MinIO: https://minio.example.com
    """

    def __init__(self):
        self.storage_type = os.getenv("MODEL_STORAGE_TYPE", "local")
        self.local_cache_dir = Path("models")
        self.local_cache_dir.mkdir(exist_ok=True)

        # S3 configuration
        self.s3_bucket = os.getenv("S3_BUCKET", "atlas-models")
        self.s3_endpoint = os.getenv("S3_ENDPOINT_URL")  # None = AWS S3
        self.s3_region = os.getenv("S3_REGION", "us-east-1")
        self.s3_access_key = os.getenv("S3_ACCESS_KEY")
        self.s3_secret_key = os.getenv("S3_SECRET_KEY")

        self.s3_client = None

        if self.storage_type == "s3":
            if not S3_AVAILABLE:
                logger.error("S3 storage requested but boto3 not installed!")
                self.storage_type = "local"
            elif not self.s3_access_key or not self.s3_secret_key:
                logger.warning("S3 credentials not provided, falling back to local storage")
                self.storage_type = "local"
            else:
                self._init_s3_client()

        logger.info(f"📦 Model storage initialized: {self.storage_type}")
        if self.storage_type == "s3":
            logger.info(f"   S3 Bucket: {self.s3_bucket}")
            logger.info(f"   Endpoint: {self.s3_endpoint or 'AWS S3'}")

    def _init_s3_client(self):
        """Initialize S3 client"""
        try:
            self.s3_client = boto3.client(
                's3',
                endpoint_url=self.s3_endpoint,
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
                region_name=self.s3_region
            )

            # Test connection
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            logger.info(f"✅ S3 connection successful: {self.s3_bucket}")

        except Exception as e:
            logger.error(f"❌ S3 initialization failed: {e}")
            logger.warning("Falling back to local storage")
            self.storage_type = "local"
            self.s3_client = None

    async def get_model(
        self,
        model_name: str,
        version: Optional[str] = None,
        force_download: bool = False
    ) -> Optional[Path]:
        """
        Get model from storage (downloads if needed)

        Args:
            model_name: e.g., 'yolov8m.pt', 'sait_audio_classifier.pth'
            version: Specific version or 'latest' (default: 'latest')
            force_download: Force re-download even if cached

        Returns:
            Path to local model file or None if failed
        """
        version = version or "latest"

        # Local cache path
        local_path = self.local_cache_dir / model_name

        # Check local cache first (unless force_download)
        if not force_download and local_path.exists():
            logger.info(f"📂 Using cached model: {local_path}")
            return local_path

        # Download from S3 if configured
        if self.storage_type == "s3" and self.s3_client:
            return await self._download_from_s3(model_name, version, local_path)

        # Local storage mode - check if file exists
        if local_path.exists():
            return local_path

        logger.warning(f"⚠️ Model not found: {model_name}")
        return None

    async def _download_from_s3(
        self,
        model_name: str,
        version: str,
        local_path: Path
    ) -> Optional[Path]:
        """Download model from S3"""
        try:
            # S3 key format: models/yolov8m/v1.0.0/yolov8m.pt
            # Or for latest: models/yolov8m/latest/yolov8m.pt
            s3_key = f"models/{model_name.split('.')[0]}/{version}/{model_name}"

            logger.info(f"⬇️ Downloading {model_name} v{version} from S3...")

            # Download to local cache
            await asyncio.to_thread(
                self.s3_client.download_file,
                self.s3_bucket,
                s3_key,
                str(local_path)
            )

            logger.info(f"✅ Model downloaded: {local_path}")
            return local_path

        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"❌ Model not found in S3: {s3_key}")
            else:
                logger.error(f"❌ S3 download failed: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return None

    async def get_model_metadata(self, model_name: str) -> Optional[Dict]:
        """
        Get model metadata from S3 (version, checksum, etc.)

        Metadata file format (JSON in S3):
        {
            "model_name": "yolov8m",
            "version": "v2.1.0",
            "uploaded_at": "2025-10-07T20:00:00Z",
            "sha256": "abc123...",
            "accuracy": 0.92,
            "file_size_mb": 49.7
        }
        """
        if self.storage_type != "s3" or not self.s3_client:
            return None

        try:
            # Metadata key: models/yolov8m/metadata.json
            s3_key = f"models/{model_name.split('.')[0]}/metadata.json"

            response = await asyncio.to_thread(
                self.s3_client.get_object,
                Bucket=self.s3_bucket,
                Key=s3_key
            )

            metadata = json.loads(response['Body'].read())
            return metadata

        except Exception as e:
            logger.warning(f"Could not fetch metadata for {model_name}: {e}")
            return None

    async def upload_model(
        self,
        local_path: Path,
        model_name: str,
        version: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Upload model to S3 (for training pipelines)

        Args:
            local_path: Path to local model file
            model_name: Model identifier
            version: Version string (e.g., 'v2.1.0')
            metadata: Optional metadata dict

        Returns:
            True if successful
        """
        if self.storage_type != "s3" or not self.s3_client:
            logger.warning("S3 not configured, cannot upload")
            return False

        try:
            # Upload model file
            s3_key = f"models/{model_name}/{version}/{local_path.name}"

            logger.info(f"⬆️ Uploading {local_path.name} to S3...")

            await asyncio.to_thread(
                self.s3_client.upload_file,
                str(local_path),
                self.s3_bucket,
                s3_key
            )

            # Upload metadata if provided
            if metadata:
                metadata['uploaded_at'] = datetime.utcnow().isoformat()
                metadata['version'] = version

                # Calculate SHA256
                sha256 = hashlib.sha256()
                with open(local_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        sha256.update(chunk)
                metadata['sha256'] = sha256.hexdigest()
                metadata['file_size_mb'] = local_path.stat().st_size / (1024 * 1024)

                # Upload metadata.json
                metadata_key = f"models/{model_name}/metadata.json"
                await asyncio.to_thread(
                    self.s3_client.put_object,
                    Bucket=self.s3_bucket,
                    Key=metadata_key,
                    Body=json.dumps(metadata, indent=2),
                    ContentType='application/json'
                )

                # Also upload as "latest"
                latest_key = f"models/{model_name}/latest/{local_path.name}"
                await asyncio.to_thread(
                    self.s3_client.copy_object,
                    Bucket=self.s3_bucket,
                    CopySource={'Bucket': self.s3_bucket, 'Key': s3_key},
                    Key=latest_key
                )

            logger.info(f"✅ Model uploaded: {s3_key}")
            return True

        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            return False

    async def list_model_versions(self, model_name: str) -> list:
        """List all versions of a model in S3"""
        if self.storage_type != "s3" or not self.s3_client:
            return []

        try:
            prefix = f"models/{model_name}/"
            response = await asyncio.to_thread(
                self.s3_client.list_objects_v2,
                Bucket=self.s3_bucket,
                Prefix=prefix,
                Delimiter='/'
            )

            versions = []
            for prefix_info in response.get('CommonPrefixes', []):
                version = prefix_info['Prefix'].rstrip('/').split('/')[-1]
                if version not in ['latest', 'metadata.json']:
                    versions.append(version)

            return sorted(versions, reverse=True)

        except Exception as e:
            logger.error(f"Failed to list versions: {e}")
            return []


# Singleton instance
_model_storage: Optional[ModelStorage] = None


def get_model_storage() -> ModelStorage:
    """Get or create model storage singleton"""
    global _model_storage

    if _model_storage is None:
        _model_storage = ModelStorage()

    return _model_storage
