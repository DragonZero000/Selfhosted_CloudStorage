import os
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, status

import db
from authorization import get_current_user
from db import User

router = APIRouter(prefix="/files", tags=["files"])

# MinIO / S3 config
MINIO_INTERNAL = os.getenv("MINIO_INTERNAL_URL", "http://minio:9000")
MINIO_PUBLIC   = os.getenv("MINIO_PUBLIC_URL",   "http://localhost:9000")
BUCKET         = os.getenv("S3_BUCKET", "cloudstorage")
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
    """Вызывается один раз при старте — просто проверяет/создаёт бакет."""
    try:
        existing = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        if BUCKET not in existing:
            s3.create_bucket(Bucket=BUCKET)
            print(f"Bucket '{BUCKET}' created.")
        else:
            print(f"Bucket '{BUCKET}' already exists.")
    except Exception as e:
        print(f"Warning: could not ensure bucket: {e}")


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


@router.post("/upload", summary="Upload file via backend")
def upload_file(
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
):
    import io, time
    s3_key = f"{current_user.login}/{file.filename}"

    existing = [f for f in db.get_user_files(current_user.id) if f.s3_key == s3_key]
    if existing:
        s3_key = f"{current_user.login}/{int(time.time())}_{file.filename}"

    contents = file.file.read()
    file_size = len(contents)

    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=s3_key,
            Body=io.BytesIO(contents),
            ContentLength=file_size,
            ContentType=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    file_record = db.insert_file(current_user.id, file.filename, s3_key, file_size)
    return {"file_id": file_record.id, "file_name": file.filename, "file_size": file_size}


@router.get("/download/{file_id}", summary="Download file streamed through backend")
def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
):
    from fastapi.responses import StreamingResponse
    import urllib.parse

    file = db.get_file(file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        obj = s3.get_object(Bucket=BUCKET, Key=file.s3_key)
    except ClientError as e:
        raise HTTPException(status_code=500, detail=str(e))

    encoded_name = urllib.parse.quote(file.file_name, safe="")
    return StreamingResponse(
        obj["Body"].iter_chunks(chunk_size=1024 * 1024),
        media_type=obj.get("ContentType", "application/octet-stream"),
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
            "Content-Length": str(obj.get("ContentLength", "")),
        },
    )


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