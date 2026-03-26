"""
Message Formatter Utility
--------------------------
Formats evaluation results into readable WhatsApp messages.

WhatsApp supports a limited subset of markdown:
- *bold* 
- _italic_
- ~strikethrough~
- ```monospace```
"""

from typing import Dict, Any


def format_evaluation_message(evaluation: Dict[str, Any]) -> str:
    """
    Format the full evaluation result as a WhatsApp-friendly message.
    
    Respects WhatsApp's ~1600 character soft limit per message by
    prioritizing the most actionable information first.
    """
    score = evaluation.get("score", 0)
    breakdown = evaluation.get("score_breakdown", {})
    summary = evaluation.get("summary", "")
    missing_skills = evaluation.get("missing_skills", [])
    suggestions = evaluation.get("suggestions", [])
    ats_warnings = evaluation.get("ats_warnings", [])
    matched = evaluation.get("matched_skills", [])

    # ─── Score with visual bar ────────────────────────────────────────────────
    score_bar = _score_to_bar(score)
    score_emoji = _score_to_emoji(score)

    lines = [
        f"📊 *RESUME EVALUATION RESULTS*",
        f"",
        f"{score_emoji} *ATS Score: {score}/100*",
        f"{score_bar}",
        f"",
    ]

    # ─── Score Breakdown ──────────────────────────────────────────────────────
    if breakdown:
        lines.extend([
            "📈 *Score Breakdown:*",
            f"• Skill Match: {breakdown.get('skill_match', 0)}/30",
            f"• Keyword Density: {breakdown.get('keyword_density', 0)}/25",
            f"• Experience Relevance: {breakdown.get('experience_relevance', 0)}/25",
            f"• ATS Friendliness: {breakdown.get('ats_friendliness', 0)}/20",
            "",
        ])

    # ─── Overall Summary ──────────────────────────────────────────────────────
    if summary:
        lines.extend([f"💬 {summary}", ""])

    # ─── Matched Skills ───────────────────────────────────────────────────────
    if matched:
        matched_str = ", ".join(matched[:8])
        lines.extend([f"✅ *Matched Skills:* {matched_str}", ""])

    # ─── Missing Skills (top 5 most critical) ─────────────────────────────────
    critical_missing = [
        s for s in missing_skills
        if s.get("importance") == "critical"
    ][:5]

    if critical_missing:
        lines.append("❌ *Critical Missing Skills:*")
        for skill in critical_missing:
            lines.append(f"• *{skill.get('skill')}*")
        lines.append("")

    # ─── Top Suggestions ─────────────────────────────────────────────────────
    if suggestions:
        lines.append("💡 *Top Improvements:*")
        for s in suggestions[:3]:
            lines.append(f"• {s.get('fix', s.get('issue', ''))}")
        lines.append("")

    # ─── ATS Warnings ─────────────────────────────────────────────────────────
    if ats_warnings:
        lines.append("⚠️ *ATS Warnings:*")
        for w in ats_warnings[:2]:
            lines.append(f"• {w}")
        lines.append("")

    return "\n".join(lines)


def format_options_menu() -> str:
    """
    The interactive options menu shown after evaluation.
    Users reply with a number to choose an action.
    """
    return (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 *What would you like to do?*\n"
        "\n"
        "1️⃣  Rewrite bullet points\n"
        "2️⃣  See missing skills + how to fix\n"
        "3️⃣  Rewrite professional summary\n"
        "4️⃣  Generate improved resume (DOCX + PDF)\n"
        "5️⃣  Show evaluation again\n"
        "\n"
        "Reply with a number (1-5)"
    )


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _score_to_bar(score: int, width: int = 10) -> str:
    """Convert numeric score to a visual progress bar for WhatsApp."""
    filled = round((score / 100) * width)
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}] {score}%"


def _score_to_emoji(score: int) -> str:
    """Return a contextual emoji based on score range."""
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    elif score >= 40:
        return "🟠"
    else:
        return "🔴"
