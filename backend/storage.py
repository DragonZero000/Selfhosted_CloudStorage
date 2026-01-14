import boto3
from fastapi import APIRouter, Depends

router = APIRouter()
s3_client = boto3.client(
    's3',
    endpoint_url='http://minio:9000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='miniopass'
)

@router.post("/files/upload")
async def get_upload_url(file_name: str, user=Depends(get_current_user)):
    key = f"{user['email']}/{file_name}"
    url = s3_client.generate_presigned_url(
        'put_object',
        Params={'Bucket': 'CloudStorage', 'Key': key},
        ExpiresIn=300
    )
    return {"upload_url": url, "key": key}