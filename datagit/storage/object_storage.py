import os
import io
import time
import secrets
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Generator, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from datagit.config import settings
from datagit.storage.models import ExportArtifact, User

class StorageBackend(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def save(self, filename: str, content: bytes) -> Tuple[str, int, str]:
        """Saves content bytes and returns (storage_path, file_size, sha256_checksum)."""
        pass

    @abstractmethod
    def get_stream(self, storage_path: str, chunk_size: int = 65536) -> Generator[bytes, None, None]:
        """Yields chunks of the file stream."""
        pass

    @abstractmethod
    def delete(self, storage_path: str) -> bool:
        """Deletes the stored object."""
        pass


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.export_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "local"

    def save(self, filename: str, content: bytes) -> Tuple[str, int, str]:
        file_path = self.base_dir / filename
        sha256 = hashlib.sha256(content).hexdigest()
        file_size = len(content)

        with open(file_path, "wb") as f:
            f.write(content)

        return str(file_path), file_size, sha256

    def get_stream(self, storage_path: str, chunk_size: int = 65536) -> Generator[bytes, None, None]:
        path = Path(storage_path)
        if not path.is_file():
            raise FileNotFoundError(f"Export file not found: {storage_path}")

        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    def delete(self, storage_path: str) -> bool:
        try:
            path = Path(storage_path)
            if path.is_file():
                path.unlink()
                return True
        except Exception:
            pass
        return False


class S3StorageBackend(StorageBackend):
    def __init__(self, bucket: str, region: str = "us-east-1", endpoint_url: Optional[str] = None):
        self.bucket = bucket
        self.region = region
        self.endpoint_url = endpoint_url
        self._s3_client = None

    @property
    def name(self) -> str:
        return "s3"

    def _get_client(self):
        if self._s3_client is None:
            import boto3
            self._s3_client = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=self.endpoint_url
            )
        return self._s3_client

    def save(self, filename: str, content: bytes) -> Tuple[str, int, str]:
        s3 = self._get_client()
        key = f"exports/{filename}"
        sha256 = hashlib.sha256(content).hexdigest()
        file_size = len(content)

        s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            Metadata={"sha256": sha256}
        )
        storage_path = f"s3://{self.bucket}/{key}"
        return storage_path, file_size, sha256

    def get_stream(self, storage_path: str, chunk_size: int = 65536) -> Generator[bytes, None, None]:
        s3 = self._get_client()
        key = storage_path.replace(f"s3://{self.bucket}/", "")
        response = s3.get_object(Bucket=self.bucket, Key=key)
        stream = response["Body"]
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk

    def generate_presigned_url(self, storage_path: str, expires_in_seconds: int = 86400) -> str:
        s3 = self._get_client()
        key = storage_path.replace(f"s3://{self.bucket}/", "")
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in_seconds
        )

    def delete(self, storage_path: str) -> bool:
        try:
            s3 = self._get_client()
            key = storage_path.replace(f"s3://{self.bucket}/", "")
            s3.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


class ObjectStorageManager:
    """Enterprise Object Storage Manager handling local filesystem & S3/MinIO/R2 exports."""

    def __init__(self):
        s3_bucket = os.getenv("DATAGIT_S3_BUCKET")
        if s3_bucket:
            s3_region = os.getenv("DATAGIT_S3_REGION", "us-east-1")
            s3_endpoint = os.getenv("DATAGIT_S3_ENDPOINT_URL")
            self.backend = S3StorageBackend(bucket=s3_bucket, region=s3_region, endpoint_url=s3_endpoint)
        else:
            self.backend = LocalStorageBackend()

    def store_export(
        self,
        db: Session,
        user_id: int,
        filename: str,
        content: bytes,
        export_format: str,
        workspace_id: Optional[int] = None,
        retention_hours: int = 48
    ) -> ExportArtifact:
        """Stores export content in object storage and creates tracked ExportArtifact."""
        storage_path, file_size, checksum = self.backend.save(filename=filename, content=content)
        download_token = secrets.token_hex(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=retention_hours)

        artifact = ExportArtifact(
            user_id=user_id,
            workspace_id=workspace_id,
            filename=filename,
            storage_path=storage_path,
            storage_backend=self.backend.name,
            format=export_format,
            file_size=file_size,
            checksum_sha256=checksum,
            download_token=download_token,
            expires_at=expires_at
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        return artifact

    def get_artifact_by_token(self, db: Session, token: str) -> Optional[ExportArtifact]:
        """Retrieves and validates an export artifact by its secure download token."""
        artifact = db.query(ExportArtifact).filter(ExportArtifact.download_token == token).first()
        if not artifact:
            return None
        # Check expiration
        now = datetime.now(timezone.utc)
        exp = artifact.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if now > exp:
            return None
        return artifact

    def stream_artifact(self, artifact: ExportArtifact) -> Generator[bytes, None, None]:
        return self.backend.get_stream(artifact.storage_path)

    def cleanup_expired(self, db: Session) -> int:
        """Removes expired artifacts and frees storage per Constitution Principle 4."""
        now = datetime.now(timezone.utc)
        expired = db.query(ExportArtifact).filter(ExportArtifact.expires_at < now).all()
        removed = 0
        for item in expired:
            try:
                self.backend.delete(item.storage_path)
            except Exception:
                pass
            db.delete(item)
            removed += 1
        if removed > 0:
            db.commit()
        return removed

storage_manager = ObjectStorageManager()
