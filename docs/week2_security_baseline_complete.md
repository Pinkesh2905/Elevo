# Week 2 Security Baseline Complete Checklist

Date: March 3, 2026

## Platform Security Settings
- [x] `SECURE_SSL_REDIRECT` enabled for staging and production
- [x] `SECURE_PROXY_SSL_HEADER` configured for reverse-proxy TLS termination
- [x] secure session and CSRF cookies enabled (`Secure`, `SameSite`)
- [x] HSTS enabled in staging and production
- [x] secure browser headers enabled (`X-Frame-Options`, `nosniff`, referrer policy)

## Static/Media Serving
- [x] media serving from Django URLs limited to debug mode or explicit insecure override
- [x] production path expects platform/storage delivery for media

## Auditability and Traceability
- [x] organization audit log model created (`OrganizationAuditLog`)
- [x] critical org actions logged (org create, invite send/cancel/accept, member remove/leave)
- [x] membership role changes audited via signal
- [x] subscription create/plan changes audited via signal
- [x] audit log exposed in Django admin

## Compliance Drafts
- [x] Privacy Policy draft created (template + docs)
- [x] Terms of Service draft created (template + docs)
- [x] Data Processing Addendum draft created (template + docs)

## Validation
- [x] `python manage.py check` passes
- [ ] `python manage.py migrate` run locally to apply new migration
