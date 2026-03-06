"""
AI cost / latency / health analytics for the org dashboard.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, F, Max, Q, Sum
from django.db.models.functions import Percentile
from django.utils import timezone


def _month_start():
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _qs(org, days=30):
    """Base queryset scoped to org and time window."""
    from mock_interview.ai_models import AIUsageLog
    cutoff = timezone.now() - timedelta(days=days)
    qs = AIUsageLog.objects.filter(created_at__gte=cutoff)
    if org is not None:
        qs = qs.filter(organization=org)
    return qs


# ---------------------------------------------------------------------------
# Public analytics functions
# ---------------------------------------------------------------------------

def compute_ai_cost_summary(org, days=30):
    """Total tokens, cost, and call count by operation."""
    qs = _qs(org, days)
    by_op = (
        qs.values("operation")
          .annotate(
              calls=Count("id"),
              input_tok=Sum("input_tokens"),
              output_tok=Sum("output_tokens"),
              cost=Sum("estimated_cost_usd"),
          )
          .order_by("-cost")
    )
    totals = qs.aggregate(
        total_calls=Count("id"),
        total_input=Sum("input_tokens"),
        total_output=Sum("output_tokens"),
        total_cost=Sum("estimated_cost_usd"),
    )
    return {
        "by_operation": list(by_op),
        "totals": {
            "calls": totals["total_calls"] or 0,
            "input_tokens": totals["total_input"] or 0,
            "output_tokens": totals["total_output"] or 0,
            "cost_usd": float(totals["total_cost"] or 0),
        },
    }


def compute_latency_stats(org, days=30):
    """Latency percentiles by provider."""
    qs = _qs(org, days).filter(status__in=["success", "fallback"])
    by_provider = (
        qs.values("provider")
          .annotate(
              calls=Count("id"),
              avg_ms=Avg("latency_ms"),
              max_ms=Max("latency_ms"),
          )
          .order_by("provider")
    )
    result = []
    for row in by_provider:
        provider_qs = qs.filter(provider=row["provider"]).order_by("latency_ms")
        count = provider_qs.count()
        p50_idx = max(0, int(count * 0.5) - 1)
        p95_idx = max(0, int(count * 0.95) - 1)
        latencies = list(provider_qs.values_list("latency_ms", flat=True))
        result.append({
            "provider": row["provider"],
            "calls": row["calls"],
            "avg_ms": int(row["avg_ms"] or 0),
            "p50_ms": latencies[p50_idx] if latencies else 0,
            "p95_ms": latencies[p95_idx] if latencies else 0,
            "max_ms": row["max_ms"] or 0,
        })
    return result


def compute_provider_health(org, days=30):
    """Success / error / timeout / fallback rates per provider."""
    qs = _qs(org, days)
    total = qs.count() or 1
    by_status = (
        qs.values("provider", "status")
          .annotate(count=Count("id"))
          .order_by("provider", "status")
    )
    health = {}
    for row in by_status:
        p = row["provider"]
        if p not in health:
            health[p] = {"provider": p, "success": 0, "error": 0, "timeout": 0,
                         "fallback": 0, "quota_exceeded": 0, "total": 0}
        health[p][row["status"]] = row["count"]
        health[p]["total"] += row["count"]
    for p in health:
        t = health[p]["total"] or 1
        health[p]["success_rate"] = round(health[p]["success"] / t * 100, 1)
        health[p]["error_rate"] = round(health[p]["error"] / t * 100, 1)
    return list(health.values())


def compute_quota_usage(org):
    """Current month token usage vs plan limit."""
    if org is None:
        return {"used": 0, "limit": -1, "percent": 0}
    sub = org.active_subscription
    limit = sub.plan.ai_tokens_monthly if sub else 50000
    from mock_interview.ai_models import AIUsageLog
    month_start = _month_start()
    agg = AIUsageLog.objects.filter(
        organization=org,
        created_at__gte=month_start,
        status__in=["success", "fallback"],
    ).aggregate(
        used_input=Sum("input_tokens"),
        used_output=Sum("output_tokens"),
    )
    used = (agg["used_input"] or 0) + (agg["used_output"] or 0)
    pct = round(used / max(1, limit) * 100, 1) if limit != -1 else 0
    return {"used": used, "limit": limit, "percent": min(100, pct)}
