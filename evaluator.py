"""
Resume Evaluator Service
-------------------------
The core intelligence of the bot. Sends structured prompts to Claude
to evaluate the resume against the job description.

Returns a structured JSON evaluation with:
- ATS score
- Missing skills
- Improvement suggestions
- Rewritten bullets
- Keyword analysis
- Rewritten summary
"""

import json
import re
from typing import Dict, Any

import anthropic

from config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Initialize Anthropic client once at module load (thread-safe)
client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


# ─── Evaluation Prompt Template ───────────────────────────────────────────────
EVALUATION_SYSTEM_PROMPT = """
You are an expert ATS (Applicant Tracking System) analyst and career coach with 15+ years of experience 
in technical recruiting. You analyze resumes against job descriptions with surgical precision.

Your evaluations are:
- Honest and actionable (not generic advice)
- Specific to the job description provided
- Focused on quantifiable improvements
- ATS-aware (keyword density, formatting, parsability)

Always respond with ONLY valid JSON — no preamble, no markdown fences, no explanation outside the JSON.
""".strip()

EVALUATION_USER_PROMPT = """
Evaluate this resume against the job description below.

=== JOB DESCRIPTION ===
{job_description}

=== RESUME ===
{resume_text}

Return a JSON object with EXACTLY this structure:

{{
  "score": <integer 0-100>,
  "score_breakdown": {{
    "skill_match": <integer 0-30>,
    "keyword_density": <integer 0-25>,
    "experience_relevance": <integer 0-25>,
    "ats_friendliness": <integer 0-20>
  }},
  "summary": "<2-3 sentence overall assessment>",
  "missing_skills": [
    {{
      "skill": "<skill name>",
      "importance": "<critical|important|nice-to-have>",
      "suggestion": "<specific advice to address this gap>"
    }}
  ],
  "matched_skills": ["<skill1>", "<skill2>"],
  "suggestions": [
    {{
      "category": "<formatting|content|keywords|structure>",
      "issue": "<specific issue found>",
      "fix": "<specific actionable fix>"
    }}
  ],
  "rewritten_bullets": [
    {{
      "original": "<original bullet point from resume>",
      "rewritten": "<impact-driven rewrite with metrics where possible>",
      "reason": "<why this rewrite is better>"
    }}
  ],
  "rewritten_summary": "<rewritten professional summary optimized for this role>",
  "keyword_optimization": {{
    "missing_keywords": ["<keyword1>", "<keyword2>"],
    "overused_words": ["<word1>"],
    "recommended_additions": ["<phrase to add>"]
  }},
  "ats_warnings": ["<warning1>", "<warning2>"]
}}

Rules:
- Extract REAL bullet points from the resume for rewriting (up to 5 most impactful)
- Missing skills must be from the JD, not generic advice
- Score must reflect actual JD-resume alignment
- Rewritten bullets must be specific and include metrics if possible
""".strip()


class ResumeEvaluator:
    """
    Orchestrates resume evaluation via Claude API.
    
    Uses a single, well-engineered prompt to get structured JSON output.
    The JSON is validated and returned to the conversation handler.
    """

    async def evaluate(
        self,
        job_description: str,
        resume_text: str,
    ) -> Dict[str, Any]:
        """
        Evaluate resume against job description using Claude.
        
        Args:
            job_description: The full JD text from the user
            resume_text: Parsed plain text of the resume
            
        Returns:
            Structured evaluation dict matching the JSON schema above
        """
        # Truncate very long inputs to avoid token limits
        # Claude can handle ~100k tokens but we want fast responses
        jd_truncated = job_description[:4000]
        resume_truncated = resume_text[:6000]

        user_prompt = EVALUATION_USER_PROMPT.format(
            job_description=jd_truncated,
            resume_text=resume_truncated,
        )

        logger.info("Sending evaluation request to Claude...")

        # ─── Call Claude API ──────────────────────────────────────────────────
        # Using synchronous client here; for async, use anthropic.AsyncAnthropic
        response = client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=4096,  # Evaluation responses can be large
            system=EVALUATION_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt}
            ],
        )

        raw_content = response.content[0].text
        logger.info(f"Received evaluation response ({len(raw_content)} chars)")

        # ─── Parse and validate JSON ──────────────────────────────────────────
        evaluation = self._parse_response(raw_content)
        evaluation = self._validate_and_fix(evaluation)

        return evaluation

    def _parse_response(self, raw: str) -> Dict[str, Any]:
        """
        Parse Claude's JSON response, handling edge cases where
        the model wraps output in markdown fences despite instructions.
        """
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse evaluation JSON: {e}\nRaw: {raw[:500]}")
            # Return a safe fallback rather than crashing
            return self._fallback_evaluation()

    def _validate_and_fix(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure all required fields exist with sensible defaults.
        Prevents KeyErrors downstream if Claude omits a field.
        """
        defaults = {
            "score": 0,
            "score_breakdown": {
                "skill_match": 0,
                "keyword_density": 0,
                "experience_relevance": 0,
                "ats_friendliness": 0,
            },
            "summary": "Unable to generate summary.",
            "missing_skills": [],
            "matched_skills": [],
            "suggestions": [],
            "rewritten_bullets": [],
            "rewritten_summary": "",
            "keyword_optimization": {
                "missing_keywords": [],
                "overused_words": [],
                "recommended_additions": [],
            },
            "ats_warnings": [],
        }

        # Merge defaults with actual data (actual data wins)
        for key, default_val in defaults.items():
            if key not in data:
                data[key] = default_val

        # Clamp score to valid range
        data["score"] = max(0, min(100, int(data.get("score", 0))))

        return data

    def _fallback_evaluation(self) -> Dict[str, Any]:
        """Return a minimal valid evaluation when parsing fails completely."""
        return {
            "score": 0,
            "score_breakdown": {"skill_match": 0, "keyword_density": 0, "experience_relevance": 0, "ats_friendliness": 0},
            "summary": "Evaluation could not be completed. Please try again.",
            "missing_skills": [],
            "matched_skills": [],
            "suggestions": [{"category": "error", "issue": "Evaluation failed", "fix": "Please re-upload your resume and try again."}],
            "rewritten_bullets": [],
            "rewritten_summary": "",
            "keyword_optimization": {"missing_keywords": [], "overused_words": [], "recommended_additions": []},
            "ats_warnings": ["Evaluation could not be completed"],
        }
