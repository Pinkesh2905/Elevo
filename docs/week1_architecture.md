# Elevo Week 1 Architecture Draft

## Runtime Profile Selection
- Entry module: `elevo/settings.py`
- Selector env var: `ELEVO_ENV`
- Targets:
  - development -> `elevo.settings_development`
  - staging -> `elevo.settings_staging`
  - production -> `elevo.settings_production`

## Layering
- `settings_base.py`:
  - app registration
  - database/email/AI/static/media defaults
  - REST framework config
  - product scope flags
- env overrides:
  - development: debug + console email
  - staging: secure cookies/SSL + demo mode defaults
  - production: strict secure defaults + demo mode defaults

## Feature Path Gating
- Chat route:
  - enabled when `ENABLE_CHAT=True`
- Social feed route:
  - enabled when `SHOW_SOCIAL_IN_SALES_DEMO=True`
  - or when `SALES_DEMO_MODE=False`

This keeps code intact while shaping the buyer-facing path.

## Subscription Packaging
- Seed source of truth:
  - `organizations/management/commands/seed_subscription_plans.py`
- Managed plans:
  - Free Trial
  - Starter
  - Growth
  - Enterprise
  - Personal Pro

## Next Architecture Steps (Week 2+)
- Separate settings into package form (`elevo/settings/`) when stable.
- Add structured logging and request tracing.
- Add task queue for AI-heavy operations.
