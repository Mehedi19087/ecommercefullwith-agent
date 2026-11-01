import logging
import uuid
import cloudinary
import cloudinary.uploader

logger = logging.getLogger(__name__)


def is_cloudinary_configured() -> bool:
    config = cloudinary.config()
    return bool(config.cloud_name and (config.api_key or config.api_secret))


def upload_image_to_cloudinary(file_obj) -> str:
    """
    Uploads a file to Cloudinary and returns its secure URL.
    Falls back to a safe placeholder URL if credentials are not configured.
    """
    if not file_obj:
        raise ValueError("No file provided for upload.")

    if is_cloudinary_configured():
        try:
            # If it's a Django file object, ensure cursor is at beginning
            if hasattr(file_obj, 'seek'):
                file_obj.seek(0)
            result = cloudinary.uploader.upload(
                file_obj,
                folder="ecommerce/products",
                resource_type="image",
            )
            return result.get('secure_url') or result.get('url')
        except Exception as exc:
            logger.error("Cloudinary upload failed: %s", exc)
            raise RuntimeError(f"Cloudinary image upload failed: {exc}")

    # Fallback for development/testing when Cloudinary is not configured
    unique_id = uuid.uuid4().hex[:12]
    filename = getattr(file_obj, 'name', 'product')
    logger.info("Cloudinary credentials not set. Using test URL for %s", filename)
    return f"https://res.cloudinary.com/demo/image/upload/v1/products/{unique_id}_{filename}"
