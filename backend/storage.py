import os
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, status

import db
from authorization import get_current_user
from db import User

router = APIRouter(prefix="/files", tags=["files"])

# MinIO / S3 config
MINIO_INTERNAL = os.getenv("MINIO_INTERNAL_URL", "http://minio:9000")
MINIO_PUBLIC   = os.getenv("MINIO_PUBLIC_URL",   "http://localhost:9000")
BUCKET         = os.getenv("S3_BUCKET", "CloudStorage")
ACCESS_KEY     = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
SECRET_KEY     = os.getenv("MINIO_SECRET_KEY", "miniopass")

# Internal client (server→MinIO): used for delete and presign generation
s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_INTERNAL,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

# Public client (for presigned URLs the browser will call)
s3_public = boto3.client(
    "s3",
    endpoint_url=MINIO_PUBLIC,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)


def _ensure_bucket():
    try:
        s3.head_bucket(Bucket=BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", summary="List user files")
def list_files(current_user: User = Depends(get_current_user)):
    files = db.get_user_files(current_user.id)
    return [
        {
            "id":          f.id,
            "file_name":   f.file_name,
            "file_size":   f.file_size,
            "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
        }
        for f in files
    ]


@router.post("/upload-url", summary="Get presigned PUT URL for direct upload")
def get_upload_url(
    file_name: str,
    file_size: float = 0,
    current_user: User = Depends(get_current_user),
):
    _ensure_bucket()
    s3_key = f"{current_user.login}/{file_name}"

    # Check for duplicate key → append timestamp
    existing = [f for f in db.get_user_files(current_user.id) if f.s3_key == s3_key]
    if existing:
        import time
        s3_key = f"{current_user.login}/{int(time.time())}_{file_name}"

    try:
        url = s3_public.generate_presigned_url(
            "put_object",
            Params={"Bucket": BUCKET, "Key": s3_key},
            ExpiresIn=300,
        )
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

    file_record = db.insert_file(current_user.id, file_name, s3_key, file_size)
    return {"upload_url": url, "key": s3_key, "file_id": file_record.id}


@router.get("/download/{file_id}", summary="Get presigned GET URL for download")
def get_download_url(
    file_id: int,
    current_user: User = Depends(get_current_user),
):
    file = db.get_file(file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        url = s3_public.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET,
                "Key":    file.s3_key,
                "ResponseContentDisposition": f'attachment; filename="{file.file_name}"',
            },
            ExpiresIn=300,
        )
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"download_url": url, "file_name": file.file_name}


@router.delete("/{file_id}", summary="Delete a file")
def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
):
    file = db.get_file(file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        s3.delete_object(Bucket=BUCKET, Key=file.s3_key)
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {e}")

    deleted = db.delete_file_record(file_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to remove file record")

    return {"msg": "File deleted successfully"}