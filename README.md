# Wine House

**Smart Wine Restaurant Management System** — *Akıllı Şarap Restoranı Yönetim Sistemi*

A locally-installed, offline-capable, role-based management system for
wine-focused restaurants: floor operations, a digital wine cellar, menu and
recipe costing, stock, reporting, staff, and an optional AI assistant that
prefers a local model.

| | |
|---|---|
| **Version** | 0.1.0 |
| **Maturity** | **Pre-production development release — never run in a live restaurant** |
| **Platform** | Windows (local install); the Django app itself is portable |
| **Languages** | Türkçe · English (UI). Code comments and several docs are Turkish only |
| **Licence** | **MIT — free to use, modify, distribute and sublicense within applicable law; see [`LICENSE`](LICENSE)** |

> ### Read this first
>
> **This repository is not licensed for use.** No `LICENSE` file is present on
> purpose. All rights are reserved until the owner chooses terms. You may read
> the source to evaluate it; you may not use, copy, modify or redistribute it.
>
> **It has never been used in production.** There is no field experience and no
> operational history. Treat every capability below as "implemented and tested"
> — not as "proven in service".

📖 **[Türkçe belgeler](README_TR.md)** · **[English documentation](README_EN.md)**

---

## What it does

**Floor operations** — table map and status, reservations with conflict
checking, waitlist, orders/tabs, kitchen/bar/wine display screens (KDS), prep
tickets, bill splitting and merging, multi-payment, end-of-day close and cash
reconciliation.

**Digital wine cellar** — producer, appellation, grape composition and vintage
records; cellar/cabinet/shelf placement; temperature and humidity tracking;
lot-based bottle stock; **by-the-glass sales deducted from the actual opened
bottle**; realised yield and spillage analysis; preservation-system tracking;
cork-taint and oxidation records; tasting notes; drinking-window alerts;
food–wine pairing; cellar valuation; duplicate detection.

**Menu, stock and cost** — recipes and portion costing, allergen and dietary
labels, dynamic pricing and happy hour, menu engineering (Star/Plough
Horse/Puzzle/Dog), FIFO/FEFO stock, expiry alerts, waste analysis, suppliers,
purchasing and quote comparison.

**Customers and staff** — CRM with per-purpose consent records, loyalty,
privacy centre (export / anonymise), shifts, leave, performance indicators.

**Reporting** — 13 built-in reports, exportable to PDF / Excel / CSV.

**AI (provider-independent)** — LM Studio (local, default) · Anthropic Claude ·
NVIDIA · Mock (offline). Sommelier assistant, pairing, natural-language report
querying, end-of-day summary, cost and token tracking.

## What it does **not** do

- **Not a hosted service and not multi-tenant.** One business, one machine.
- **No live payments.** Payment and e-invoice paths are **sandbox-only**.
- **Not accounting software.** Reports are operational, not books of account.
- **No age-verification workflow**, despite being alcohol-sales software.
- **No multi-factor authentication.**
- **No HTTPS by default** — the assumed deployment is a local machine.
- **The AI cannot take any business action.** It produces text for a human.
- **Not legal, financial, medical or dietary advice.** See the limits below.

The complete list is [`docs/known-limitations.md`](docs/known-limitations.md).
Please read it before evaluating.

---

## Install and run a demo

Requires Python 3.11–3.13.

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip setuptools
pip install -r requirements.txt

copy .env.example .env
# set DJANGO_SECRET_KEY in .env, then:

python manage.py migrate
python manage.py seed_demo      # synthetic demo data
python manage.py create_admin   # creates one-time admin/admin when no password is supplied
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

On Windows there is also a guided installer: `INSTALL_WINE_HOUSE.ps1`, then
`START_WINE_HOUSE.bat`. Details in
[`docs/INSTALLATION_WINDOWS.md`](docs/INSTALLATION_WINDOWS.md).

### One-time bootstrap credential

On an empty installation, `create_admin` uses `admin` / `admin` when no password
is supplied. It is accepted only from the host computer and must be replaced on
the first sign-in. Passwords are stored with a secure hash; the temporary pair
is not suitable for normal use.

If an account is flagged "must change password", it cannot reach *any* screen,
REST resource, or the Django admin until the password is actually changed.

### Demo data is synthetic

Everything `seed_demo` creates is fictional and generated from a fixed seed.
**No real personal data exists anywhere in this repository.** Demo phone
numbers are deliberately **not dialable** — they contain literal `X` characters
in the subscriber digits (`+90 5XX XXX XX 07`) — and demo e-mail addresses use
the reserved `.test` domain.

---

## Configuration

All settings come from environment variables; see [`.env.example`](.env.example)
for the full annotated list. **It contains empty values only — no key, no
secret, no token.**

The ones that matter most:

| Variable | Default | Meaning |
|---|---|---|
| `DJANGO_SECRET_KEY` | *(generated in dev)* | Required in production |
| `WINEHOUSE_ENV` | `dev` | `prod` turns off DEBUG and enables security headers |
| `WINEHOUSE_DB_ENGINE` | `sqlite` | or `postgres` |
| `WINEHOUSE_FIELD_ENCRYPTION_KEY` | *(empty)* | Fernet key for personal-data fields |
| `WINEHOUSE_AI_DEFAULT_PROVIDER` | `lmstudio` | Local-first by default |
| `WINEHOUSE_AI_LOCAL_ONLY` | `False` | `True` forbids all cloud transfer |
| `WINEHOUSE_FORCE_HTTPS` | `False` | Turn on for any routed network |
| `ANTHROPIC_API_KEY` / `NVIDIA_API_KEY` | *(empty)* | Supplied by you, after install |

**Never commit a real key.** `.env` is git-ignored; `gitleaks` and
`detect-secrets` run in CI.

## AI providers, and the local-only option

The default is **LM Studio running on your own machine** — no key, no network
egress. Cloud providers are used only if you supply a key.

With no key configured, a provider reports `NOT_CONFIGURED`, **makes no network
call**, and everything else keeps working.

Before anything reaches a cloud provider, personal data is masked and a
pre-action policy decides whether cloud transfer is allowed at all. Customer
preference analysis never leaves the machine; any unclassified feature is
treated as local-only (fails closed). The UI shows only the provider name, its
status, and the **last four characters** of a key.

Full statement: [`AI_TRANSPARENCY.md`](AI_TRANSPARENCY.md).

## Privacy and human approval limits

You are the data controller for everything the software stores. The repository
has **no telemetry and no phone-home**. Consent records, subject export,
anonymisation, field-level encryption, role-gated contact visibility, and
list-view masking are provided as tools — they do not discharge your legal
duties. See [`PRIVACY.md`](PRIVACY.md) and [`docs/PRIVACY.md`](docs/PRIVACY.md).

Critical actions require a **second human approval** from a different user
(self-approval is blocked). The AI layer cannot approve anything, cannot change
data, and cannot execute a payment.

## Claim limits — financial, legal, health

- **Financial.** Sandbox payments only. Reports and forecasts are operational
  aids, not accounting records, not tax-compliant output, and not financial
  advice.
- **Legal.** The KVKK/GDPR rule packs and ROPA aid are record-keeping tools.
  They ship in `DRAFT` and require explicit human approval before taking
  effect. They are not legal advice and do not determine your obligations.
- **Health and allergens.** Allergen information comes from the structured
  allergen fields you maintain, **never from AI text**. If AI narrative and the
  allergen field disagree, the field is authoritative. Nothing here is medical
  or dietary advice.
- **Alcohol.** Age limits, licensing and serving hours are entirely the
  operator's responsibility; the software does not enforce them.

---

## Screenshots and presentation

UI screenshots: [`docs/screenshots/`](docs/screenshots/) — captured
automatically from a real running instance loaded with synthetic demo data
(`scripts/capture_screenshots.py`).

Presentation deck (TR and EN, screen and print themes):
[`docs/presentation/`](docs/presentation/) — for example
[`Wine_House_Tanitim_PUBLIC.pdf`](docs/presentation/Wine_House_Tanitim_PUBLIC.pdf).

The whole chain — demo seed → screenshot capture → deck → PDF — is regenerated
from source by `scripts/make_presentation.py`. Every figure in the deck is
measured from this repository, not typed in by hand. Text is set in DejaVu
Sans, which is bundled under a permissive licence so output does not depend on
a proprietary system font.

## Running the tests

```powershell
pip install -r requirements-dev.txt
pytest                      # full suite
pytest --cov                # with coverage
ruff check src tests scripts
black --check src tests
python manage.py check
python manage.py makemigrations --check --dry-run
```

Measured from this tree at release time:

| Metric | Value |
|---|---|
| Automated tests | **380, all passing** |
| Line coverage (all code) | ~73% |
| Django apps | 16 |
| Database tables (product apps) | 129 |
| UI templates | 72 |
| Roles | 19 |
| Built-in reports | 13 |
| Migrations | 23 |
| Runtime dependencies (full closure) | 29 |

Tests run on in-memory SQLite with the Mock AI provider and make **no network
calls**. What is *not* covered — browser end-to-end, load, concurrency,
PostgreSQL in CI, populated-database upgrades — is listed in
[`docs/known-limitations.md`](docs/known-limitations.md).

## Licence and third-party notices

- **Licence: MIT.** See [`LICENSE`](LICENSE). The software may be used, modified,
  distributed and sublicensed subject to the MIT notice and applicable law.
- Third-party components and their licences:
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- Machine-readable SBOMs: [`sbom.spdx.json`](sbom.spdx.json) (SPDX 2.3) and
  [`sbom.cdx.json`](sbom.cdx.json) (CycloneDX)

All runtime dependencies are permissively licensed (BSD / MIT / Apache-2.0),
with `certifi` under MPL-2.0 used unmodified as a separate library.

## Reporting a vulnerability

**Do not open a public issue.** See [`SECURITY.md`](SECURITY.md) for the
private reporting route, the security model, and its honest limitations.

## Contributing

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first — the undecided licence
and the Turkish-language codebase both limit what can be accepted right now.

## Documentation map

| Document | Contents |
|---|---|
| [`docs/known-limitations.md`](docs/known-limitations.md) | **What it can't do, and the roadmap** |
| [`SECURITY.md`](SECURITY.md) | Security model, controls, limits, reporting |
| [`PRIVACY.md`](PRIVACY.md) · [`docs/PRIVACY.md`](docs/PRIVACY.md) | Privacy summary and technical detail |
| [`AI_TRANSPARENCY.md`](AI_TRANSPARENCY.md) | What the AI sees, does, and never does |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Module layout and design |
| [`docs/API.md`](docs/API.md) | REST API |
| [`docs/INSTALLATION_WINDOWS.md`](docs/INSTALLATION_WINDOWS.md) | Windows install |
| [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md) | Backup and restore |
| [`docs/AI_CONFIGURATION.md`](docs/AI_CONFIGURATION.md) | AI provider setup |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Architecture decision records |
| [`CHANGELOG.md`](CHANGELOG.md) | Version history |
