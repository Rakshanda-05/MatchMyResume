"""
Conversation Handler
---------------------
The central state machine that routes every incoming WhatsApp message
to the right handler based on the user's current session state.

Think of this as the "controller" in an MVC pattern — it orchestrates
services (evaluation, resume generation) but contains no business logic itself.
"""

from typing import Optional

from app.services.session_manager import SessionManager, ConversationState
from app.services.resume_parser import ResumeParser
from app.services.evaluator import ResumeEvaluator
from app.services.resume_generator import ResumeGenerator
from app.utils.formatter import format_evaluation_message, format_options_menu
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ─── Menu Shortcuts ───────────────────────────────────────────────────────────
HELP_TEXT = """
🤖 *WhatsApp Resume Evaluation Bot*

Commands:
• Send your *Job Description* to get started
• *restart* — Start a new evaluation
• *help* — Show this menu
• *status* — Check current session state

Supported resume formats: PDF, DOCX
""".strip()

WELCOME_TEXT = """
👋 Welcome to the *Resume Evaluation Bot*!

I'll analyze your resume against a job description and give you:
✅ ATS Match Score (out of 100)
📋 Missing Skills
💡 Improvement Suggestions
✍️ Rewritten Bullet Points
📄 Downloadable Improved Resume

*Please paste the Job Description to get started:*
""".strip()


class ConversationHandler:
    """
    Routes messages to the correct handler based on session state.
    
    Each state has a dedicated method. Adding new states is as simple
    as adding a new method and mapping it in `handle()`.
    """

    def __init__(self, session_manager: SessionManager):
        self.sessions = session_manager
        self.parser = ResumeParser()
        self.evaluator = ResumeEvaluator()
        self.generator = ResumeGenerator()

    async def handle(
        self,
        user_id: str,
        message: str,
        resume_path: Optional[str] = None,
    ) -> str:
        """
        Main dispatcher — called for every incoming message.
        Returns the text reply to send back to the user.
        """
        session = self.sessions.get(user_id)
        msg_lower = message.lower().strip()

        # ─── Global Commands (work in any state) ──────────────────────────────
        if msg_lower in ("restart", "reset", "start over"):
            session.reset()
            self.sessions.save(session)
            return "🔄 Session reset! " + WELCOME_TEXT

        if msg_lower in ("help", "?"):
            return HELP_TEXT

        if msg_lower == "status":
            return f"📍 Current state: `{session.state.value}`\nJD: {'✅' if session.job_description else '❌'} | Resume: {'✅' if session.resume_text else '❌'}"

        # ─── State Machine Dispatch ───────────────────────────────────────────
        state = session.state

        if state == ConversationState.IDLE:
            return await self._handle_idle(session, message, resume_path)

        elif state == ConversationState.WAITING_FOR_JD:
            return await self._handle_jd_input(session, message)

        elif state == ConversationState.WAITING_FOR_RESUME:
            return await self._handle_resume_upload(session, message, resume_path)

        elif state == ConversationState.REVIEW_RESULTS:
            return await self._handle_review_menu(session, message)

        elif state == ConversationState.WAITING_CHOICE:
            return await self._handle_choice(session, message)

        else:
            # Fallback for unexpected states
            session.reset()
            self.sessions.save(session)
            return "Something unexpected happened. Let's start fresh!\n\n" + WELCOME_TEXT

    # ─── State Handlers ───────────────────────────────────────────────────────

    async def _handle_idle(self, session, message: str, resume_path: Optional[str]) -> str:
        """
        IDLE state: user just connected or sent their first message.
        If they sent text, treat it as a JD. If they sent a file, ask for JD first.
        """
        if resume_path and not message:
            # User sent a file without JD — ask for JD first
            session.resume_path = resume_path
            session.state = ConversationState.WAITING_FOR_JD
            self.sessions.save(session)
            return "📎 Got your resume! Now please *paste the Job Description* so I can evaluate it:"

        if message:
            # Treat the message as a job description
            session.job_description = message
            session.state = ConversationState.WAITING_FOR_RESUME
            self.sessions.save(session)

            if resume_path:
                # They sent both at once — process immediately
                return await self._handle_resume_upload(session, "", resume_path)

            return "✅ Job Description saved!\n\n📎 Now please *upload your resume* (PDF or DOCX):"

        return WELCOME_TEXT

    async def _handle_jd_input(self, session, message: str) -> str:
        """WAITING_FOR_JD: user needs to provide their job description."""
        if len(message) < 50:
            return "⚠️ That seems too short for a job description. Please paste the full JD (at least 50 characters)."

        session.job_description = message
        session.state = ConversationState.WAITING_FOR_RESUME
        self.sessions.save(session)

        # If we already have the resume (sent before JD), evaluate now
        if session.resume_path:
            return await self._handle_resume_upload(session, "", None)

        return "✅ Got the Job Description!\n\n📎 Now please *upload your resume* (PDF or DOCX):"

    async def _handle_resume_upload(
        self, session, message: str, resume_path: Optional[str]
    ) -> str:
        """WAITING_FOR_RESUME: user needs to upload their resume file."""
        # Use newly uploaded file, or previously stored one
        path = resume_path or session.resume_path

        if not path:
            return "📎 Please upload your resume as a *PDF or DOCX* file."

        # ─── Parse resume text ────────────────────────────────────────────────
        try:
            resume_text = self.parser.extract_text(path)
        except Exception as e:
            logger.error(f"Resume parsing failed: {e}")
            return "❌ Couldn't read your resume. Please make sure it's a valid PDF or DOCX file and try again."

        if len(resume_text.strip()) < 100:
            return "⚠️ Your resume appears to be empty or image-based (non-text PDF). Please upload a text-based resume."

        session.resume_path = path
        session.resume_text = resume_text
        self.sessions.save(session)

        # ─── Run evaluation ───────────────────────────────────────────────────
        await self._send_typing_indicator(session)

        try:
            evaluation = await self.evaluator.evaluate(
                job_description=session.job_description,
                resume_text=resume_text,
            )
            session.evaluation = evaluation
            session.state = ConversationState.REVIEW_RESULTS
            self.sessions.save(session)
        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            return "❌ Evaluation failed. Please try again in a moment."

        # ─── Format and return results ────────────────────────────────────────
        result_message = format_evaluation_message(evaluation)
        menu = format_options_menu()
        return result_message + "\n\n" + menu

    async def _handle_review_menu(self, session, message: str) -> str:
        """
        REVIEW_RESULTS: User has seen their evaluation. 
        Offer interactive improvement options.
        """
        msg = message.strip()

        # ─── Option routing ───────────────────────────────────────────────────
        if msg == "1":
            return await self._rewrite_bullets(session)

        elif msg == "2":
            return await self._add_missing_skills(session)

        elif msg == "3":
            return await self._rewrite_summary(session)

        elif msg == "4":
            return await self._generate_resume(session)

        elif msg == "5":
            # Re-show evaluation
            return format_evaluation_message(session.evaluation) + "\n\n" + format_options_menu()

        else:
            return (
                "Please choose an option:\n"
                + format_options_menu()
            )

    async def _handle_choice(self, session, message: str) -> str:
        """
        WAITING_CHOICE: User is responding to a sub-prompt (e.g., confirm bullet rewrite).
        """
        msg = message.lower().strip()
        action = session.pending_action

        if action == "confirm_bullet_rewrite":
            if msg in ("yes", "y", "1", "apply"):
                # Apply all rewrites to session evaluation
                evaluation = session.evaluation
                if evaluation and "rewritten_bullets" in evaluation:
                    evaluation["bullets_applied"] = True
                    session.evaluation = evaluation
                session.state = ConversationState.REVIEW_RESULTS
                session.pending_action = None
                self.sessions.save(session)
                return "✅ Bullet rewrites saved! Generate your improved resume with option *4*.\n\n" + format_options_menu()
            else:
                session.state = ConversationState.REVIEW_RESULTS
                session.pending_action = None
                self.sessions.save(session)
                return "No changes made.\n\n" + format_options_menu()

        # Default: return to review menu
        session.state = ConversationState.REVIEW_RESULTS
        self.sessions.save(session)
        return await self._handle_review_menu(session, message)

    # ─── Action Implementations ───────────────────────────────────────────────

    async def _rewrite_bullets(self, session) -> str:
        """Generate impact-driven rewrites for experience bullets."""
        evaluation = session.evaluation
        if not evaluation:
            return "❌ No evaluation found. Please restart."

        bullets = evaluation.get("rewritten_bullets", [])
        if not bullets:
            return "No bullet rewrites available. Try re-evaluating your resume."

        # Format rewrites for display
        lines = ["✍️ *Rewritten Bullets (Impact-Driven):*\n"]
        for i, item in enumerate(bullets[:5], 1):  # Show max 5
            lines.append(f"*Before:* _{item.get('original', '')}_")
            lines.append(f"*After:* {item.get('rewritten', '')}\n")

        lines.append("Type *yes* to apply these changes, or *no* to skip.")

        session.state = ConversationState.WAITING_CHOICE
        session.pending_action = "confirm_bullet_rewrite"
        self.sessions.save(session)

        return "\n".join(lines)

    async def _add_missing_skills(self, session) -> str:
        """Show missing skills with context on how to address each."""
        evaluation = session.evaluation
        missing = evaluation.get("missing_skills", [])

        if not missing:
            return "🎉 No critical skills are missing! Your resume covers the key requirements.\n\n" + format_options_menu()

        lines = ["📋 *Missing Skills & How to Address Them:*\n"]
        for skill in missing[:8]:
            lines.append(f"• *{skill.get('skill')}* — {skill.get('suggestion', 'Add to skills section or mention in experience.')}")

        lines.append("\n💡 Tip: Add these to your Skills section and weave them into bullet points where applicable.")
        lines.append("\n" + format_options_menu())

        return "\n".join(lines)

    async def _rewrite_summary(self, session) -> str:
        """Generate a rewritten professional summary."""
        evaluation = session.evaluation
        summary = evaluation.get("rewritten_summary", "")

        if not summary:
            return "❌ No summary rewrite available. Please re-evaluate.\n\n" + format_options_menu()

        reply = f"📝 *Rewritten Professional Summary:*\n\n_{summary}_\n\n"
        reply += "Copy this into your resume's summary/objective section.\n\n"
        reply += format_options_menu()
        return reply

    async def _generate_resume(self, session) -> str:
        """Generate and return download links for improved resume (DOCX + PDF)."""
        if not session.resume_text or not session.evaluation:
            return "❌ Missing data. Please restart and re-upload your resume."

        session.state = ConversationState.GENERATING_RESUME
        self.sessions.save(session)

        try:
            from config import get_settings
            settings = get_settings()

            docx_path, pdf_path = await self.generator.generate(
                resume_text=session.resume_text,
                evaluation=session.evaluation,
                job_description=session.job_description,
            )

            session.generated_resume_docx = docx_path
            session.generated_resume_pdf = pdf_path
            session.state = ConversationState.REVIEW_RESULTS
            self.sessions.save(session)

            # Build public download URLs
            base = settings.BASE_URL
            docx_url = f"{base}/{docx_path}"
            pdf_url = f"{base}/{pdf_path}"

            return (
                f"✅ *Your Improved Resume is Ready!*\n\n"
                f"📄 *ATS-Optimized DOCX:*\n{docx_url}\n\n"
                f"📄 *Modern PDF:*\n{pdf_url}\n\n"
                f"These links expire in 24 hours.\n\n"
                + format_options_menu()
            )

        except Exception as e:
            logger.error(f"Resume generation failed: {e}", exc_info=True)
            session.state = ConversationState.REVIEW_RESULTS
            self.sessions.save(session)
            return "❌ Resume generation failed. Please try again.\n\n" + format_options_menu()

    async def _send_typing_indicator(self, session):
        """Placeholder for typing indicator (Twilio doesn't support this natively)."""
        pass
