import aioboto3
from core.config import settings
from fastapi import FastAPI

# Reusable session — safe to create at module level (no event loop needed)
_session = aioboto3.Session()
_s3_client = None

async def init_s3(app: FastAPI) -> None:
    global _s3_client
    _s3_client = await _session.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.S3_REGION,
    ).__aenter__()
 

async def close_s3(app: FastAPI) -> None:
    if _s3_client:
        await _s3_client.__aexit__(None, None, None)
 
async def upload_to_s3(file_data: bytes, key: str, content_type: str) -> str:
    await _s3_client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=file_data,
        ContentType=content_type,
    )
    return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.S3_REGION}.amazonaws.com/{key}"
