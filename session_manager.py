"""
Session Manager
----------------
Maintains per-user conversation state across multiple WhatsApp messages.
Uses an in-memory dict with TTL-based expiry.

For production at scale: replace the in-memory store with Redis using
`redis-py` or `aioredis`. The interface stays the same.
"""

import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from config import get_settings

settings = get_settings()


class ConversationState(str, Enum):
    """All possible states in the conversation flow."""
    IDLE = "idle"                        # Fresh start, waiting for JD
    WAITING_FOR_JD = "waiting_for_jd"   # Bot asked for job description
    WAITING_FOR_RESUME = "waiting_for_resume"  # JD received, waiting for resume
    EVALUATING = "evaluating"           # Processing (async)
    REVIEW_RESULTS = "review_results"   # Showing evaluation, waiting for action
    WAITING_CHOICE = "waiting_choice"   # User choosing an improvement option
    GENERATING_RESUME = "generating"    # Building improved resume


@dataclass
class UserSession:
    """
    Stores all state for a single user's conversation.
    
    Each field is populated progressively as the conversation advances.
    """
    user_id: str
    state: ConversationState = ConversationState.IDLE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    # ─── Content collected from user ──────────────────────────────────────────
    job_description: Optional[str] = None
    resume_path: Optional[str] = None      # Local path to uploaded resume
    resume_text: Optional[str] = None      # Extracted plain text from resume

    # ─── Evaluation results ───────────────────────────────────────────────────
    evaluation: Optional[Dict[str, Any]] = None   # Full evaluation JSON from Claude

    # ─── Interactive improvement tracking ─────────────────────────────────────
    pending_options: Optional[list] = None   # Options shown to user (1, 2, 3...)
    pending_action: Optional[str] = None     # Which action is in progress

    # ─── Generated resume paths ───────────────────────────────────────────────
    generated_resume_docx: Optional[str] = None
    generated_resume_pdf: Optional[str] = None

    def touch(self):
        """Update the last-active timestamp to reset TTL."""
        self.updated_at = time.time()

    def is_expired(self, ttl_minutes: int) -> bool:
        """Check if session has been inactive longer than TTL."""
        return (time.time() - self.updated_at) > (ttl_minutes * 60)

    def reset(self):
        """Clear all conversation data, keeping user_id."""
        self.state = ConversationState.IDLE
        self.job_description = None
        self.resume_path = None
        self.resume_text = None
        self.evaluation = None
        self.pending_options = None
        self.pending_action = None
        self.generated_resume_docx = None
        self.generated_resume_pdf = None
        self.touch()


class SessionManager:
    """
    Thread-safe in-memory session store.
    
    Replace `_sessions` dict with Redis calls to scale horizontally.
    """

    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}

    def get(self, user_id: str) -> UserSession:
        """
        Retrieve existing session or create a new one.
        Expired sessions are automatically reset.
        """
        if user_id in self._sessions:
            session = self._sessions[user_id]
            if session.is_expired(settings.SESSION_TTL_MINUTES):
                session.reset()  # Reset stale session
        else:
            session = UserSession(user_id=user_id)
            self._sessions[user_id] = session

        session.touch()
        return session

    def save(self, session: UserSession):
        """Persist session updates (no-op for in-memory, important for Redis)."""
        session.touch()
        self._sessions[session.user_id] = session

    def delete(self, user_id: str):
        """Remove session entirely (e.g., on 'restart' command)."""
        self._sessions.pop(user_id, None)

    def cleanup_expired(self):
        """Purge all expired sessions. Call periodically (e.g., via APScheduler)."""
        expired = [
            uid for uid, s in self._sessions.items()
            if s.is_expired(settings.SESSION_TTL_MINUTES)
        ]
        for uid in expired:
            del self._sessions[uid]
