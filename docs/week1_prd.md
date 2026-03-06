# Elevo Week 1 PRD (B2B MVP)

## Objective
Position Elevo as a subscription platform for organizations teaching tech students, with a clear B2B MVP path.

## Scope Freeze (Week 1)
In scope for B2B MVP:
- `organizations`
- `practice`
- `aptitude`
- `mock_interview`
- `chat` (retained by request for student collaboration)

Out of primary sales demo path:
- `posts` social feed (feature retained, hidden in sales demo mode)

## Key Product Decisions
- Institutional-first packaging: Starter, Growth, Enterprise.
- Individual plan retained: Personal Pro.
- Organization onboarding starts with trial plan (`FREE` fallback to `STARTER`).
- Sales demos emphasize outcomes:
  - coding readiness
  - aptitude readiness
  - interview readiness
  - cohort analytics roadmap

## Week 1 Engineering Deliverables
- Environment settings split:
  - `settings_development.py`
  - `settings_staging.py`
  - `settings_production.py`
  - dynamic loader in `settings.py` via `ELEVO_ENV`
- Product scope flags:
  - `B2B_MVP_MODULES`
  - `SALES_DEMO_MODE`
  - `SHOW_SOCIAL_IN_SALES_DEMO`
  - `ENABLE_CHAT`
- URL gating:
  - chat always available when enabled
  - posts hidden from default sales demo path
- Plan seeding command:
  - `python manage.py seed_subscription_plans`

## Acceptance Criteria
- Team can switch environments with `ELEVO_ENV`.
- Plans can be seeded repeatably across environments.
- Sales demo can run without social feed while keeping chat enabled.
