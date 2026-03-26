"""
Twilio Helper Utilities
------------------------
Handles downloading media attachments (resumes) from Twilio's media server.

Twilio stores uploaded files temporarily on their servers.
We download them to local disk for processing.
"""

import os
import tempfile
import httpx
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Map MIME types to file extensions
MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/octet-stream": ".pdf",  # Default assumption for binary
}


async def download_media(
    url: str,
    content_type: str,
    account_sid: str,
    auth_token: str,
    max_size_mb: int = 10,
) -> str:
    """
    Download a media file from Twilio and save it locally.
    
    Args:
        url: Twilio media URL (e.g., https://api.twilio.com/2010-04-01/Accounts/.../Media/...)
        content_type: MIME type of the file
        account_sid: Twilio Account SID (for authentication)
        auth_token: Twilio Auth Token (for authentication)
        max_size_mb: Maximum allowed file size in MB
        
    Returns:
        Local file path where the media was saved
        
    Raises:
        ValueError: If file type is not supported or file is too large
        httpx.HTTPError: If download fails
    """
    # Determine file extension
    ext = MIME_TO_EXT.get(content_type, "")
    if not ext:
        # Try to infer from content_type string
        if "pdf" in content_type:
            ext = ".pdf"
        elif "word" in content_type or "docx" in content_type:
            ext = ".docx"
        else:
            raise ValueError(
                f"Unsupported file type: {content_type}. "
                f"Please upload a PDF or DOCX resume."
            )

    logger.info(f"Downloading media: {url} ({content_type})")

    # ─── Download file with authentication ───────────────────────────────────
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            url,
            auth=(account_sid, auth_token),  # Twilio requires basic auth
            follow_redirects=True,
        )
        response.raise_for_status()

        # Check file size before writing
        content_length = int(response.headers.get("content-length", 0))
        if content_length > max_size_mb * 1024 * 1024:
            raise ValueError(
                f"File too large ({content_length // (1024*1024)}MB). "
                f"Maximum allowed: {max_size_mb}MB"
            )

        file_content = response.content

    # Check actual content size
    if len(file_content) > max_size_mb * 1024 * 1024:
        raise ValueError(f"File exceeds {max_size_mb}MB limit after download.")

    # ─── Save to temp file ────────────────────────────────────────────────────
    # Use a named temp file that persists (delete=False)
    # The caller is responsible for cleanup
    fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="resume_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(file_content)
    except Exception:
        os.unlink(temp_path)
        raise

    logger.info(f"Media saved to: {temp_path} ({len(file_content)} bytes)")
    return temp_path
