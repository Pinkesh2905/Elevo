"""
Async task wrappers for heavy AI operations.

Run with Django-Q2:  python manage.py qcluster
"""
import logging

logger = logging.getLogger(__name__)


def async_parse_resume(session_id):
    """
    Off-load resume parsing + ATS insights to a background worker.
    Called via django_q.tasks.async_task('mock_interview.tasks.async_parse_resume', session_id).
    """
    from mock_interview.models import MockInterviewSession
    from mock_interview.views import (
        _extract_resume_profile,
        _compute_resume_ats_insights,
        _strip,
        _safe_list,
    )

    try:
        session = MockInterviewSession.objects.get(pk=session_id)
    except MockInterviewSession.DoesNotExist:
        logger.error("async_parse_resume: session %s not found", session_id)
        return {"error": "session_not_found"}

    resume_text = session.extracted_resume_text or ""
    if not _strip(resume_text):
        return {"error": "no_resume_text"}

    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    role_hint = _strip(parsed.get("job_role", "")) or session.job_role or ""
    track = _strip(parsed.get("interview_track", "")) or "technical"

    profile = _extract_resume_profile(resume_text, role_hint=role_hint, track=track)
    insights = _compute_resume_ats_insights(
        profile,
        role_hint=role_hint,
        skills_hint=session.key_skills or "",
        track=track,
        resume_text=resume_text,
    )

    # Merge into parsed_resume_data
    merged = dict(parsed)
    merged["resume_profile"] = profile
    merged["ats_insights"] = insights
    merged["async_parse_complete"] = True

    session.parsed_resume_data = merged
    session.save(update_fields=["parsed_resume_data", "updated_at"])

    logger.info("async_parse_resume: session %s completed", session_id)
    return {"status": "ok", "ats_score": insights.get("ats_score")}


def async_generate_feedback(session_id):
    """
    Off-load feedback generation to a background worker.
    Called via django_q.tasks.async_task('mock_interview.tasks.async_generate_feedback', session_id).
    """
    import json
    from mock_interview.models import MockInterviewSession
    from mock_interview.views import _generate_feedback

    try:
        session = MockInterviewSession.objects.get(pk=session_id)
    except MockInterviewSession.DoesNotExist:
        logger.error("async_generate_feedback: session %s not found", session_id)
        return {"error": "session_not_found"}

    feedback = _generate_feedback(session)
    session.overall_feedback = json.dumps(feedback)
    session.score = feedback.get("overall_score")
    session.save(update_fields=["overall_feedback", "score", "updated_at"])

    logger.info("async_generate_feedback: session %s completed, score=%s", session_id, session.score)
    return {"status": "ok", "score": session.score}
