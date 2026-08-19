# Security Policy

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Report privately through GitHub's **Security → Report a vulnerability**
(private vulnerability reporting) on this repository. If that is unavailable,
open a normal issue that contains **only** the sentence "I would like to report
a security issue privately" and no technical detail, and wait to be contacted.

What helps:

- affected version / commit
- the settings profile in use (`dev`, `prod`, `test`)
- steps to reproduce, ideally against a fresh `seed_demo` install
- impact you believe it has

Please **do not** include real customer data, real API keys, or production
database contents in a report. Synthetic reproduction only.

### What to expect

This is a small project maintained by one person. There is no paid support
contract, no bug bounty, and no guaranteed response time. Reports are handled
on a best-effort basis. Realistically: acknowledgement within about a week,
and a fix timeline that depends on severity and on maintainer availability.
If that does not meet your needs, please factor it into your deployment
decision.

## Supported versions

Version `0.1.0` is a **pre-production development release**. Only the current
`main` branch receives fixes. There are no backports and no long-term support
branch.

## Security model — what the software does and does not defend against

### Design assumptions

Wine House is built for a **single business, installed on the local network**,
usually on one Windows machine, with SQLite (or optionally PostgreSQL). It is
**not** designed or hardened as a multi-tenant, internet-facing SaaS. Deploying
it on a public IP is outside the tested and intended envelope.

### Controls that are implemented and tested

| Control | Where |
|---|---|
| One-time `admin/admin` bootstrap credential — empty-install only, local-device login only, and forced password change | `apps/accounts/management/commands/create_admin.py`, `apps/accounts/views.py` |
| Argon2id password hashing (PBKDF2 retained only to verify legacy hashes) | `winehouse/settings/base.py` |
| Forced password change is enforced — a flagged account cannot reach any screen, REST resource, or the Django admin until the password is changed | `apps/core/middleware.PasswordChangeRequiredMiddleware` |
| PIN sessions are scope-limited to floor/kitchen/bar screens; the management surface requires a password login | `apps/core/middleware.PinSessionScopeMiddleware` |
| Account lockout after repeated failed logins | `apps/accounts/models.User.register_failed_login` |
| Role-based authorization with audit-logged denials, and read-only roles blocked from writes | `apps/accounts/permissions.py` |
| Second-approval workflow for critical actions, with separation of duties (no self-approval) | `apps/accounts/models.ApprovalRequest` |
| Hash-chained audit log with tamper detection | `apps/core/integrity.py` |
| Field-level encryption (Fernet) for personal data, with HMAC blind index for equality search | `apps/core/fields.py` |
| Secret masking in logs and error output | `apps/core/security.mask_secrets` |
| PII masking before any cloud AI call, with a receipt recording what was masked | `apps/core/security.mask_pii`, `apps/hsp/` |
| API keys shown in the UI as last-4 only | `apps/core/security.redact_key` |
| Same-site redirect validation on the language switch | `apps/core/views._safe_back_url` |

Regression tests for the access-control contracts live in
`tests/test_bootstrap_and_session_scope.py` and `tests/test_rbac.py`.

### Known limitations — please read before deploying

- **No multi-factor authentication.** Password (or PIN) is the only factor.
- **No HTTPS by default.** `WINEHOUSE_FORCE_HTTPS` is off by default because
  the target deployment is a local machine. On any shared or routed network,
  turn it on and terminate TLS properly.
- **The PIN is 4–8 digits.** It is deliberately weak-by-design for POS speed.
  Its blast radius is limited by session scoping, not by its own strength.
- **Field encryption is only as good as key storage.** The Fernet key lives in
  `.env` on the same machine as the database. An attacker with filesystem
  access to that machine has both. This protects against database file theft
  and casual inspection, not against host compromise.
- **The audit-log hash chain and HSP receipt chain are integrity mechanisms,
  not cryptographic non-repudiation.** They are signed with a `SECRET_KEY`
  derivative held on the same host. Someone who controls the host can forge a
  consistent chain. They detect tampering by ordinary users and accidental
  corruption; they are not court-grade evidence.
- **The AI Development Studio can propose code changes.** It is disabled by
  default in production and command execution is off by default. Enabling
  either on a machine holding real business data is a deliberate risk decision.
- **Payment and e-invoice integrations are sandbox-only.** No live payment path
  is implemented or tested.
- **No rate limiting at the HTTP layer.** Brute-force protection is per-account
  lockout, not per-IP throttling. A reverse proxy should provide that.
- **Dependency scanning covers declared dependencies.** The optional Windows
  packaging tools in `requirements-packaging.txt` bring a large, older
  transitive tree and are excluded from the clean-scan claim on purpose — scan
  your own environment before using them.

See [`docs/known-limitations.md`](docs/known-limitations.md) for the full list,
including non-security gaps.

## Verification performed on this release

Run at build time against this exact tree:

- `gitleaks dir` — no findings
- `semgrep --config p/security-audit --config p/secrets --config p/python` —
  no high or critical findings
- `bandit -r src scripts --severity-level medium` — no findings
- `pip-audit` / `osv-scanner` on runtime dependencies — no known vulnerabilities
- full test suite — all tests passing

These results describe **this tree at this moment**. They are not a warranty,
and they say nothing about vulnerabilities that were unknown at build time.
Re-run the scanners yourself before deploying.
