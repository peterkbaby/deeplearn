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
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.s3_region,
    ).__aenter__()
 

async def close_s3(app: FastAPI) -> None:
    if _s3_client:
        await _s3_client.__aexit__(None, None, None)
 
async def upload_to_s3(file_data: bytes, key: str, content_type: str) -> str:
    await _s3_client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=file_data,
        ContentType=content_type,
    )
    return f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com/{key}"


async def delete_from_s3(key: str) -> None:
    """Delete an object from the configured profile bucket."""
    await _s3_client.delete_object(Bucket=settings.s3_bucket_name, Key=key)
