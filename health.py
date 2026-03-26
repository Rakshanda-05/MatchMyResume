"""Health check endpoint for monitoring and deployment readiness."""

from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("")
async def health_check():
    """Basic health check - used by load balancers and uptime monitors."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "WhatsApp Resume Bot",
    }
