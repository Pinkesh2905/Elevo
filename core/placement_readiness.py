"""
Shared placement-readiness scoring utilities.
"""

from __future__ import annotations


READINESS_WEIGHTS = {
    "aptitude": 0.40,
    "coding": 0.30,
    "interview": 0.30,
}


def _clamp_0_100(value):
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def readiness_band(readiness_score):
    score = _clamp_0_100(readiness_score)
    if score >= 80:
        return "placement_ready"
    if score >= 65:
        return "near_ready"
    if score >= 50:
        return "developing"
    return "early_stage"


def confidence_band(confidence_score):
    score = _clamp_0_100(confidence_score)
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def compute_readiness_score(aptitude_score, coding_score, interview_score):
    apt = _clamp_0_100(aptitude_score)
    code = _clamp_0_100(coding_score)
    interview = _clamp_0_100(interview_score)
    score = (
        (apt * READINESS_WEIGHTS["aptitude"])
        + (code * READINESS_WEIGHTS["coding"])
        + (interview * READINESS_WEIGHTS["interview"])
    )
    return round(score, 1)


def confidence_from_activity(aptitude_completed, coding_attempted, interview_completed):
    """
    Confidence in readiness score based on activity volume for one user.
    """
    apt_component = min(1.0, (float(aptitude_completed or 0) / 4.0)) * 35.0
    code_component = min(1.0, (float(coding_attempted or 0) / 8.0)) * 35.0
    interview_component = min(1.0, (float(interview_completed or 0) / 3.0)) * 30.0
    score = round(apt_component + code_component + interview_component, 1)
    return {
        "score": score,
        "band": confidence_band(score),
    }


def confidence_from_coverage(total_members, aptitude_active, coding_active, interview_active):
    """
    Confidence in organization-level readiness score based on cohort coverage.
    """
    if not total_members:
        return {"score": 0.0, "band": "low"}

    apt_ratio = min(1.0, float(aptitude_active or 0) / float(total_members))
    code_ratio = min(1.0, float(coding_active or 0) / float(total_members))
    interview_ratio = min(1.0, float(interview_active or 0) / float(total_members))
    score = round((apt_ratio * 35.0) + (code_ratio * 35.0) + (interview_ratio * 30.0), 1)
    return {
        "score": score,
        "band": confidence_band(score),
    }

