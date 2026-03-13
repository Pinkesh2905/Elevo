"""
Organization Analytics Engine.

All functions scope data to the given organization using tenant utilities.
No external dependencies required — pure Django ORM aggregations.
"""

from datetime import timedelta
from django.db.models import Avg, Count, Q, F, Case, When, Value, CharField
from django.utils import timezone

from organizations.tenant import get_org_user_ids
from core.placement_readiness import (
    compute_readiness_score,
    confidence_from_activity,
    confidence_from_coverage,
    readiness_band,
)


# ---------------------------------------------------------------------------
# 1. Org-Level KPIs
# ---------------------------------------------------------------------------

def compute_org_kpis(org):
    """
    Compute headline KPIs for an organization.

    Returns dict with:
        active_members, attempt_rate, completion_rate,
        avg_aptitude_score, avg_interview_score, readiness_score
    """
    user_ids = get_org_user_ids(org)
    total_members = user_ids.count()

    if total_members == 0:
        return _empty_kpis()

    # --- Aptitude ---
    apt_stats = _aptitude_stats(user_ids)

    # --- Coding Practice ---
    code_stats = _coding_stats(user_ids)

    # --- Mock Interviews ---
    interview_stats = _interview_stats(user_ids)

    # Attempt rate: % members who attempted at least one activity
    members_who_attempted = set()
    members_who_attempted.update(apt_stats["active_user_ids"])
    members_who_attempted.update(code_stats["active_user_ids"])
    members_who_attempted.update(interview_stats["active_user_ids"])
    attempt_rate = round(len(members_who_attempted) / total_members * 100, 1)

    # Completion rate: completed activities / total attempts
    total_attempts = apt_stats["total"] + code_stats["total"] + interview_stats["total"]
    total_completed = apt_stats["completed"] + code_stats["completed"] + interview_stats["completed"]
    completion_rate = round(total_completed / total_attempts * 100, 1) if total_attempts else 0

    # Readiness score: weighted composite (40% aptitude, 30% coding, 30% interviews)
    apt_score = apt_stats["avg_score"]  # 0-100
    code_score = min(code_stats["solve_rate"] * 100, 100)  # 0-100
    interview_score = interview_stats["avg_score"]  # 0-100
    readiness = compute_readiness_score(apt_score, code_score, interview_score)
    readiness_meta = confidence_from_coverage(
        total_members,
        len(apt_stats["active_user_ids"]),
        len(code_stats["active_user_ids"]),
        len(interview_stats["active_user_ids"]),
    )

    return {
        "active_members": total_members,
        "attempt_rate": attempt_rate,
        "completion_rate": completion_rate,
        "avg_aptitude_score": round(apt_score, 1),
        "avg_interview_score": round(interview_score, 1),
        "readiness_score": round(readiness, 1),
        "readiness_band": readiness_band(readiness),
        "readiness_confidence_score": readiness_meta["score"],
        "readiness_confidence_band": readiness_meta["band"],
        # Raw numbers for cards
        "aptitude_attempts": apt_stats["total"],
        "aptitude_completed": apt_stats["completed"],
        "coding_submissions": code_stats["total"],
        "coding_accepted": code_stats["completed"],
        "interview_sessions": interview_stats["total"],
        "interview_completed": interview_stats["completed"],
    }


# ---------------------------------------------------------------------------
# 2. Weak Topics
# ---------------------------------------------------------------------------

def compute_weak_topics(org, limit=10):
    """
    Identify weakest aptitude topics for org members.

    Returns list of dicts sorted by accuracy ascending:
        [{topic_name, category_name, accuracy_pct, attempt_count}, ...]
    """
    user_ids = get_org_user_ids(org)

    try:
        from aptitude.models import AptitudeQuizResponse
        rows = (
            AptitudeQuizResponse.objects
            .filter(attempt__user__in=user_ids)
            .values(
                topic_name=F("problem__topic__name"),
                category_name=F("problem__topic__category__name"),
            )
            .annotate(
                total=Count("id"),
                correct=Count("id", filter=Q(is_correct=True)),
            )
            .filter(total__gte=3)  # At least 3 responses to be meaningful
            .order_by("total")
        )
        results = []
        for r in rows:
            accuracy = round(r["correct"] / r["total"] * 100, 1) if r["total"] else 0
            results.append({
                "topic_name": r["topic_name"],
                "category_name": r["category_name"],
                "accuracy_pct": accuracy,
                "attempt_count": r["total"],
            })
        results.sort(key=lambda x: x["accuracy_pct"])
        return results[:limit]
    except (ImportError, Exception):
        return []


# ---------------------------------------------------------------------------
# 3. Student Analytics Table
# ---------------------------------------------------------------------------

def compute_student_table(org):
    """
    Per-student analytics rows.

    Returns list of dicts:
        [{username, full_name, email, role, joined_at,
          quizzes_taken, avg_aptitude_score,
          problems_solved, problems_attempted,
          interviews_done, avg_interview_score,
          readiness_score, risk_level}, ...]
    """
    from organizations.models import Membership
    memberships = (
        Membership.objects
        .filter(organization=org, is_active=True)
        .select_related("user")
    )

    students = []
    for mem in memberships:
        user = mem.user
        row = {
            "user_id": user.pk,
            "username": user.username,
            "full_name": user.get_full_name() or user.username,
            "email": user.email,
            "role": mem.normalized_role,
            "joined_at": mem.joined_at,
        }

        # Aptitude
        apt = _user_aptitude_stats(user)
        row["quizzes_taken"] = apt["total"]
        row["avg_aptitude_score"] = apt["avg_score"]

        # Coding
        code = _user_coding_stats(user)
        row["problems_solved"] = code["solved"]
        row["problems_attempted"] = code["attempted"]

        # Interviews
        iv = _user_interview_stats(user)
        row["interviews_done"] = iv["total"]
        row["avg_interview_score"] = iv["avg_score"]

        # Readiness (same 40/30/30 weighting)
        a = row["avg_aptitude_score"]
        c = min(code["solve_rate"] * 100, 100) if code["attempted"] else 0
        i = row["avg_interview_score"]
        row["readiness_score"] = compute_readiness_score(a, c, i)
        row["readiness_band"] = readiness_band(row["readiness_score"])
        conf = confidence_from_activity(
            apt["completed"],
            code["attempted"],
            iv["completed"],
        )
        row["readiness_confidence_score"] = conf["score"]
        row["readiness_confidence_band"] = conf["band"]

        students.append(row)

    # Apply risk flags
    compute_risk_flags(students)

    # Sort by readiness ascending (riskiest first)
    students.sort(key=lambda s: s["readiness_score"])
    return students


# ---------------------------------------------------------------------------
# 4. Risk Flags
# ---------------------------------------------------------------------------

RISK_THRESHOLDS = {
    "at_risk": (0, 40),
    "needs_attention": (40, 60),
    "on_track": (60, 80),
    "strong": (80, 101),
}

RISK_LABELS = {
    "at_risk": {"label": "At Risk", "color": "rose", "icon": "ri-alarm-warning-line"},
    "needs_attention": {"label": "Needs Attention", "color": "amber", "icon": "ri-error-warning-line"},
    "on_track": {"label": "On Track", "color": "sky", "icon": "ri-checkbox-circle-line"},
    "strong": {"label": "Strong", "color": "emerald", "icon": "ri-shield-check-line"},
}


def compute_risk_flags(student_rows):
    """
    Mutate student_rows in-place, adding 'risk_level' and 'risk_meta'.
    """
    for row in student_rows:
        score = row.get("readiness_score", 0)
        level = "at_risk"
        for key, (lo, hi) in RISK_THRESHOLDS.items():
            if lo <= score < hi:
                level = key
                break
        row["risk_level"] = level
        row["risk_meta"] = RISK_LABELS[level]


# ---------------------------------------------------------------------------
# 5. Cohort Comparison
# ---------------------------------------------------------------------------

def compute_cohort_comparison(org, days=30):
    """
    Compare KPIs between current period and previous period.

    Returns dict with:
        current: {kpi_dict}, previous: {kpi_dict}, deltas: {field: delta_value}
    """
    now = timezone.now()
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)

    user_ids = get_org_user_ids(org)

    current = _period_kpis(user_ids, current_start, now)
    previous = _period_kpis(user_ids, previous_start, current_start)

    deltas = {}
    for key in current:
        try:
            deltas[key] = round(current[key] - previous[key], 1)
        except (TypeError, KeyError):
            deltas[key] = 0

    return {"current": current, "previous": previous, "deltas": deltas}


# ===========================================================================
# Internal helpers
# ===========================================================================

def _empty_kpis():
    return {
        "active_members": 0,
        "attempt_rate": 0,
        "completion_rate": 0,
        "avg_aptitude_score": 0,
        "avg_interview_score": 0,
        "readiness_score": 0,
        "readiness_band": "early_stage",
        "readiness_confidence_score": 0,
        "readiness_confidence_band": "low",
        "aptitude_attempts": 0,
        "aptitude_completed": 0,
        "coding_submissions": 0,
        "coding_accepted": 0,
        "interview_sessions": 0,
        "interview_completed": 0,
    }


def _aptitude_stats(user_ids):
    try:
        from aptitude.models import AptitudeQuizAttempt
        qs = AptitudeQuizAttempt.objects.filter(user__in=user_ids)
        total = qs.count()
        completed = qs.filter(status="completed").count()
        avg = qs.filter(status="completed").aggregate(a=Avg("score_percent"))["a"] or 0
        active = set(qs.values_list("user_id", flat=True).distinct())
        return {"total": total, "completed": completed, "avg_score": avg, "active_user_ids": active}
    except (ImportError, Exception):
        return {"total": 0, "completed": 0, "avg_score": 0, "active_user_ids": set()}


def _coding_stats(user_ids):
    try:
        from practice.models import Submission
        qs = Submission.objects.filter(user__in=user_ids)
        total = qs.count()
        accepted = qs.filter(status="accepted").count()
        active = set(qs.values_list("user_id", flat=True).distinct())
        solve_rate = accepted / total if total else 0
        return {"total": total, "completed": accepted, "solve_rate": solve_rate, "active_user_ids": active}
    except (ImportError, Exception):
        return {"total": 0, "completed": 0, "solve_rate": 0, "active_user_ids": set()}


def _interview_stats(user_ids):
    try:
        from mock_interview.models import MockInterviewSession
        qs = MockInterviewSession.objects.filter(user__in=user_ids)
        total = qs.count()
        completed_qs = qs.filter(status__in=["COMPLETED", "REVIEWED"], score__isnull=False)
        completed = completed_qs.count()
        avg = completed_qs.aggregate(a=Avg("score"))["a"] or 0
        active = set(qs.values_list("user_id", flat=True).distinct())
        return {"total": total, "completed": completed, "avg_score": float(avg), "active_user_ids": active}
    except (ImportError, Exception):
        return {"total": 0, "completed": 0, "avg_score": 0, "active_user_ids": set()}


def _user_aptitude_stats(user):
    try:
        from aptitude.models import AptitudeQuizAttempt
        qs = AptitudeQuizAttempt.objects.filter(user=user)
        total = qs.count()
        completed = qs.filter(status="completed").count()
        avg = qs.filter(status="completed").aggregate(a=Avg("score_percent"))["a"] or 0
        return {"total": total, "completed": completed, "avg_score": round(avg, 1)}
    except (ImportError, Exception):
        return {"total": 0, "completed": 0, "avg_score": 0}


def _user_coding_stats(user):
    try:
        from practice.models import UserProblemProgress
        qs = UserProblemProgress.objects.filter(user=user)
        solved = qs.filter(status="solved").count()
        attempted = qs.filter(status__in=["solved", "attempted"]).count()
        solve_rate = solved / attempted if attempted else 0
        return {"solved": solved, "attempted": attempted, "solve_rate": solve_rate}
    except (ImportError, Exception):
        return {"solved": 0, "attempted": 0, "solve_rate": 0}


def _user_interview_stats(user):
    try:
        from mock_interview.models import MockInterviewSession
        qs = MockInterviewSession.objects.filter(user=user)
        total = qs.count()
        completed_qs = qs.filter(status__in=["COMPLETED", "REVIEWED"], score__isnull=False)
        completed = completed_qs.count()
        avg = completed_qs.aggregate(a=Avg("score"))["a"] or 0
        return {"total": total, "completed": completed, "avg_score": round(float(avg), 1)}
    except (ImportError, Exception):
        return {"total": 0, "completed": 0, "avg_score": 0}


def _period_kpis(user_ids, start, end):
    """Compute KPIs for a specific time window."""
    result = {
        "aptitude_attempts": 0,
        "aptitude_avg": 0,
        "coding_submissions": 0,
        "coding_accepted": 0,
        "interview_sessions": 0,
        "interview_avg": 0,
    }
    try:
        from aptitude.models import AptitudeQuizAttempt
        qs = AptitudeQuizAttempt.objects.filter(user__in=user_ids, started_at__gte=start, started_at__lt=end)
        result["aptitude_attempts"] = qs.count()
        result["aptitude_avg"] = round(
            qs.filter(status="completed").aggregate(a=Avg("score_percent"))["a"] or 0, 1
        )
    except (ImportError, Exception):
        pass

    try:
        from practice.models import Submission
        qs = Submission.objects.filter(user__in=user_ids, created_at__gte=start, created_at__lt=end)
        result["coding_submissions"] = qs.count()
        result["coding_accepted"] = qs.filter(status="accepted").count()
    except (ImportError, Exception):
        pass

    try:
        from mock_interview.models import MockInterviewSession
        qs = MockInterviewSession.objects.filter(user__in=user_ids, created_at__gte=start, created_at__lt=end)
        result["interview_sessions"] = qs.count()
        result["interview_avg"] = round(
            float(qs.filter(status="COMPLETED", score__isnull=False).aggregate(a=Avg("score"))["a"] or 0), 1
        )
    except (ImportError, Exception):
        pass

    return result
