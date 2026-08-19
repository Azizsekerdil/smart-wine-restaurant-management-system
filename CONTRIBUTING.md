# Contributing

Thank you for looking. Please read the notes below before investing real time.

## Before you start

### 1. Licence of contributions

This project is distributed under the MIT License. By submitting a contribution,
you agree that it may be distributed under those terms. Submit only work you have
the right to contribute, and do not include secrets or incompatible third-party code.

### 2. Much of the codebase is in Turkish

Docstrings, comments, commit messages, several documents and all user-facing
strings' source language are Turkish. The UI is bilingual (TR/EN); the
internals are not. This is a real barrier and there is no plan to change it
soon. If you cannot read Turkish, focus on areas where the code speaks for
itself.

---

## Reporting bugs

Open an issue with:

- what you did, what you expected, what happened
- the settings profile (`dev`, `prod`, `test`)
- Python version, OS, and database engine
- ideally a reproduction against a fresh `seed_demo` install

**Never** attach real customer data, real staff data, or real API keys to an
issue. Reproduce with synthetic data.

**Security problems do not go in issues.** See [`SECURITY.md`](SECURITY.md).

## Development setup

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # Linux/macOS

python -m pip install --upgrade pip setuptools
pip install -r requirements-dev.txt

cp .env.example .env            # then fill in DJANGO_SECRET_KEY
python manage.py migrate
python manage.py seed_demo      # synthetic demo data
python manage.py create_admin   # asks for a password interactively
python manage.py runserver
```

Optional extras:

- `requirements-postgres.txt` — PostgreSQL driver
- `requirements-packaging.txt` — Windows `.exe` / desktop shell tooling.
  **Not needed for development.** It pulls a large, older transitive tree; scan
  it yourself before installing.

## Before you open a pull request

All of these must pass:

```bash
ruff check src tests scripts
black --check src tests
mypy src
python manage.py check
python manage.py makemigrations --check --dry-run
pytest
```

And, for anything touching security, dependencies, or data handling:

```bash
bandit -r src scripts --severity-level medium --exclude '*/migrations/*'
pip-audit --strict -r requirements.txt
```

## Standards that are not negotiable

**Tests.** New behaviour needs a test. Changed behaviour needs its test
changed *with a stated reason*. Deleting or weakening a test to make a build
go green will be rejected outright — if a test now fails, either the code is
wrong or the test's contract genuinely changed, and the PR must say which.

**No secrets, ever.** No API key, password, token, private key or real personal
data in source, fixtures, tests, docs, screenshots, or commit history.
`.env.example` carries empty values only. `gitleaks` and `detect-secrets` run
in CI and a finding fails the build. The one allowlisted file is
`tests/test_security.py`, which holds clearly synthetic strings used to prove
the masking function works — see `.gitleaks.toml` for the reasoning.

**No unverifiable claims.** Do not add a number to the README, the docs or the
presentation unless it can be measured from the repository. The presentation's
figures are derived from the code, not typed in by hand.

**Demo data stays synthetic and undialable.** Demo phone numbers keep literal
`X` characters in the subscriber digits; demo e-mail addresses use the reserved
`.test` domain. Do not "improve" them into realistic values.

**No dead features.** Do not merge a model, an admin screen or a settings
toggle that implies a capability the code does not actually enforce. If the
enforcement point is not wired up, the feature does not ship. An AI authority
model was removed from this codebase for exactly this reason.

**Migrations are forward-only and reviewed.** Never edit an applied migration.
`makemigrations --check` must be clean.

## Code style

- Ruff and Black, line length 100, configured in `pyproject.toml`.
- Type hints on new code; `from __future__ import annotations` at the top.
- Business logic goes in `services.py`, not in views.
- Views use `AuditedPermissionMixin` or the audited decorators so that denials
  are logged.
- User-facing strings go through `gettext` / `{% trans %}`.
- New personal-data fields must be added to `docs/privacy/pii-baseline.json`,
  or the privacy gate in CI will fail.

## Commit messages

Short imperative subject, body explaining *why*. Reference an issue where one
exists.

## What is out of scope

- Multi-tenancy.
- Turning this into a hosted SaaS.
- Live payment processing (sandbox-only is deliberate for now).
- Anything that lets the AI layer take a business action without a human.
