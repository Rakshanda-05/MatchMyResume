"""
WhatsApp Webhook Route
-----------------------
Handles incoming Twilio WhatsApp messages.
Twilio sends a POST request here for every message received.
"""

import os
import tempfile
from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import PlainTextResponse
from twilio.request_validator import RequestValidator

from config import get_settings
from app.services.session_manager import SessionManager
from app.services.conversation_handler import ConversationHandler
from app.utils.logger import get_logger
from app.utils.twilio_helpers import download_media

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()

# In-memory session store (use Redis in production for multi-instance deployments)
session_manager = SessionManager()
conversation_handler = ConversationHandler(session_manager)


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),           # Sender's WhatsApp number
    Body: str = Form(default=""),    # Text message content
    NumMedia: int = Form(default=0), # Number of media attachments
    MediaUrl0: str = Form(default=""),       # First media file URL
    MediaContentType0: str = Form(default=""), # MIME type of first media
):
    """
    Main webhook endpoint for Twilio WhatsApp messages.
    
    Flow:
    1. Validate request authenticity (Twilio signature)
    2. Extract user phone number as session key
    3. Download any attached files (resumes)
    4. Route message to conversation handler
    5. Return TwiML response with bot's reply
    """

    # ─── Step 1: Validate Twilio Signature ───────────────────────────────────
    # This prevents unauthorized requests from hitting your endpoint
    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    form_data = dict(await request.form())
    request_url = str(request.url)

    if not validator.validate(request_url, form_data, request.headers.get("X-Twilio-Signature", "")):
        logger.warning(f"Invalid Twilio signature from {From}")
        return PlainTextResponse("Forbidden", status_code=403)

    # ─── Step 2: Identify user by phone number ────────────────────────────────
    user_id = From  # e.g., "whatsapp:+919876543210"
    logger.info(f"Message from {user_id}: '{Body[:50]}' | Media: {NumMedia}")

    # ─── Step 3: Handle file attachment (resume) ─────────────────────────────
    resume_path = None
    if NumMedia > 0 and MediaUrl0:
        try:
            resume_path = await download_media(
                url=MediaUrl0,
                content_type=MediaContentType0,
                account_sid=settings.TWILIO_ACCOUNT_SID,
                auth_token=settings.TWILIO_AUTH_TOKEN,
            )
            logger.info(f"Downloaded resume to: {resume_path}")
        except Exception as e:
            logger.error(f"Failed to download media: {e}")

    # ─── Step 4: Process message through conversation handler ─────────────────
    try:
        reply = await conversation_handler.handle(
            user_id=user_id,
            message=Body.strip(),
            resume_path=resume_path,
        )
    except Exception as e:
        logger.error(f"Conversation handler error: {e}", exc_info=True)
        reply = "Sorry, something went wrong. Please try again or type *restart* to start over."

    # ─── Step 5: Return TwiML response ───────────────────────────────────────
    # Twilio expects a TwiML XML response to send the reply
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{reply}</Message>
</Response>"""

    return Response(content=twiml, media_type="application/xml")
