# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| Latest release | Yes |
| Previous minor | Security fixes only |
| Older | No |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report security issues by emailing **krishnalsh2004@gmail.com** with:

- A clear description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigations you have in mind

You will receive an acknowledgement within **48 hours** and a status update within **7 days**.

## Disclosure Policy

- We will confirm receipt and assess severity within 7 days.
- We aim to release a fix within 30 days for critical issues, 90 days for others.
- We will credit reporters in the release notes unless you prefer anonymity.
- We ask that you do not publicly disclose the issue until a fix is released.

## Scope

In scope:
- Authentication bypass or privilege escalation
- SQL injection or data exfiltration via API endpoints
- JWT signing key exposure or token forgery
- Unprotected admin endpoints
- XSS in the frontend (stored or reflected)
- Dependency CVEs with a working exploit against this project's usage

Out of scope:
- Rate limiting (this is an intranet app; DoS from inside the campus network is a separate concern)
- TLS configuration (responsibility of the deploying institution)
- Social engineering

## Security Design Notes

- Passwords hashed with bcrypt (cost factor 12)
- JWTs signed with HS256; the signing key must be a 64-character hex string
- All API routes require a valid JWT except `/api/v1/auth/login` and `/api/v1/guest/*`
- Role-based access control enforced at the route handler level via `Depends(require_role(...))`
- SQL queries use SQLAlchemy ORM — no raw string interpolation
- CORS origins restricted via `APP_CORS_ORIGINS` environment variable
- Nginx serves `X-Frame-Options`, `X-Content-Type-Options`, and `Referrer-Policy` headers by default
