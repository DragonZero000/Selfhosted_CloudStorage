import os
import io
import time
import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File as FastAPIFile, status
from fastapi.responses import StreamingResponse
import urllib.parse

import db
from authorization import get_current_user
from db import User

router = APIRouter(prefix="/files", tags=["files"])

MINIO_INTERNAL = os.getenv("MINIO_INTERNAL_URL", "http://minio:9000")
MINIO_PUBLIC   = os.getenv("MINIO_PUBLIC_URL",   "http://localhost:9000")
BUCKET         = os.getenv("S3_BUCKET", "cloudstorage")
ACCESS_KEY     = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
SECRET_KEY     = os.getenv("MINIO_SECRET_KEY", "miniopass")

s3 = boto3.client(
    "s3",
    endpoint_url=MINIO_INTERNAL,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)

s3_public = boto3.client(
    "s3",
    endpoint_url=MINIO_PUBLIC,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
)


def _ensure_bucket():
    try:
        existing = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        if BUCKET not in existing:
            s3.create_bucket(Bucket=BUCKET)
            print(f"Bucket '{BUCKET}' created.")
        else:
            print(f"Bucket '{BUCKET}' already exists.")
    except Exception as e:
        print(f"Warning: could not ensure bucket: {e}")


# ─── Helpers ────────────────────────────────────────────────────────────────

def generate_presigned_url(s3_key, file_name, expires=3600):
    """Generate a presigned URL for direct download"""
    try:
        url = s3_public.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET, 'Key': s3_key},
            ExpiresIn=expires
        )
        return url
    except Exception as e:
        print(f"Presigned URL error: {e}")
        return None


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
    # В новых версиях FastAPI/Starlette размер доступен через file.size
    file_size = file.size if hasattr(file, "size") and file.size is not None else 0
    
    # Если размер не определен, пробуем определить через seek/tell
    if file_size == 0:
        file.file.seek(0, os.SEEK_END)
        file_size = file.file.tell()
        file.file.seek(0)

    # ── Проверка лимита хранилища ─────────────────────────────────────────────
    limit = current_user.size_of_memory or 0
    used  = current_user.storage_used  or 0

    if limit <= 0:
        raise HTTPException(
            status_code=403,
            detail={
                "error":   "storage_blocked",
                "message": "Загрузка файлов заблокирована. Обратитесь к администратору.",
            },
        )

    if used + file_size > limit:
        free = max(0, limit - used)
        raise HTTPException(
            status_code=413,
            detail={
                "error":     "storage_limit_exceeded",
                "message":   "Недостаточно места в хранилище",
                "used":      used,
                "limit":     limit,
                "free":      free,
                "file_size": file_size,
            },
        )

    # ── Загрузка в MinIO ──────────────────────────────────────────────────────
    s3_key = f"{current_user.login}/{file.filename}"
    existing = [f for f in db.get_user_files(current_user.id) if f.s3_key == s3_key]
    if existing:
        s3_key = f"{current_user.login}/{int(time.time())}_{file.filename}"

    try:
        # Используем upload_fileobj для потоковой загрузки (не грузим файл целиком в RAM)
        s3.upload_fileobj(
            file.file,
            BUCKET,
            s3_key,
            ExtraArgs={
                "ContentType": file.content_type or "application/octet-stream"
            }
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

@router.get("/share/{file_id}", summary="Get shareable presigned URL")
def get_share_link(
    file_id: int,
    current_user: User = Depends(get_current_user),
):
    file = db.get_file(file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    url = generate_presigned_url(file.s3_key, file.file_name, expires=86400)  # 24 hours
    if not url:
        raise HTTPException(status_code=500, detail="Failed to generate share link")
    return {"share_url": url, "file_name": file.file_name}


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


@router.patch("/{file_id}/rename", summary="Rename file")
def rename_file(
    file_id: int,
    new_name: str,
    current_user: User = Depends(get_current_user),
):
    if not new_name or not new_name.strip():
        raise HTTPException(status_code=400, detail="New name cannot be empty")
    
    file = db.get_file(file_id, current_user.id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Update in DB
    success = db.rename_file(file_id, current_user.id, new_name.strip())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to rename")
    
    return {"msg": "File renamed successfully", "new_name": new_name.strip()}
