# Elevo AI Service — Draft Service Level Agreement (SLA)

> **Version**: 1.0-draft  
> **Effective**: TBD  
> **Last Updated**: 2026-03-06

---

## 1. Scope

This SLA covers the AI-powered features within the Elevo platform:
- **Resume Parsing** — Automated extraction of structured profile data from uploaded resumes.
- **Interview Question Generation** — Real-time AI-generated follow-up questions during mock interviews.
- **Feedback Generation** — Post-interview scoring, strength/weakness analysis, and recommendations.
- **Interview Hints & Practice Questions** — On-demand AI-generated content for interview preparation.

---

## 2. Availability Target

| Metric | Target |
|---|---|
| Overall AI feature availability | **99.5%** monthly uptime |
| Planned maintenance window | Sundays 02:00–04:00 IST (excluded from SLA) |
| Unplanned downtime per month | ≤ 3.6 hours |

### Provider Failover

The platform uses a **dual-provider architecture** (Gemini → OpenAI) with automatic failover. If the primary provider is unavailable, requests are transparently routed to the secondary provider.

---

## 3. Latency Targets

| Operation | P50 Target | P95 Target | Hard Timeout |
|---|---|---|---|
| Resume Parsing | < 3 000 ms | < 8 000 ms | 30 s |
| Question Generation | < 1 500 ms | < 4 000 ms | 30 s |
| Feedback Generation | < 5 000 ms | < 12 000 ms | 30 s |
| Closing Message | < 1 500 ms | < 4 000 ms | 30 s |
| Hints / Practice | < 2 000 ms | < 5 000 ms | 30 s |

All operations enforce a **30-second hard timeout** per provider call.

---

## 4. Retry & Fallback Policy

| Parameter | Value |
|---|---|
| Retries per provider | 2 (with exponential backoff: 0.5 s, 1.0 s) |
| Max total attempts | 6 (3 Gemini + 3 OpenAI) |
| Fallback trigger | Any provider exception or timeout |
| Static fallback | Used when all AI providers fail (predefined question/feedback pools) |

---

## 5. Quota & Rate Limits

| Plan Tier | Monthly Token Quota | Burst Rate Limit |
|---|---|---|
| Free / Trial | 50 000 tokens | — |
| Starter | 200 000 tokens | — |
| Professional | 1 000 000 tokens | — |
| Enterprise | Unlimited (-1) | — |

### Quota Enforcement
- Token usage is tracked per-organization per-month via `AIUsageLog`.
- When quota is exceeded, AI calls are **blocked** and a `quota_exceeded` log entry is recorded.
- Quota resets on the 1st of each calendar month (UTC).

---

## 6. Cost Tracking

All AI calls log:
- Provider and model used
- Input / output token counts (estimated at ~4 chars per token)
- Estimated cost in USD (based on published provider pricing)
- Latency in milliseconds
- Call status (success / error / timeout / fallback / quota_exceeded)

Cost data is visible on the **AI Cost Dashboard** accessible by Org Owners and Admins.

---

## 7. Data Retention

| Data Type | Retention |
|---|---|
| AI Usage Logs | 90 days (rolling) |
| Interview transcripts | Indefinite (user-deletable) |
| Parsed resume profiles | Indefinite (stored with session) |

---

## 8. Incident Response

| Severity | Response Time | Resolution Target |
|---|---|---|
| Critical (all AI down) | 30 min acknowledgement | 4 hours |
| High (one provider down, fallback active) | 2 hours | 24 hours |
| Medium (elevated latency) | 8 hours | 48 hours |
| Low (dashboard data delay) | Next business day | 5 business days |

---

## 9. Exclusions

This SLA **does not** cover:
- Third-party AI provider outages beyond our failover capability
- Client-side network issues
- Planned maintenance windows
- Force majeure events
- Features in beta

---

## 10. Monitoring

The following monitoring is in place:
- `AIUsageLog` table captures every call with status, latency, and cost
- AI Cost Dashboard provides real-time visibility into provider health
- `ai_health_check` API endpoint for automated uptime monitoring
- Django-Q2 worker health is observable via Django admin (`/admin/django_q/`)

---

*This is a draft SLA for internal alignment. Terms are subject to change before publication.*
