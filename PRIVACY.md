# Privacy

**Short version: this repository collects nothing from you. The software you
install collects data about *your* customers and staff, and *you* are the data
controller for it.**

The detailed Turkish-language technical document — data categories, legal
bases, consent purposes, retention, subject-request flows — is
[`docs/PRIVACY.md`](docs/PRIVACY.md). This file is the public summary.

> **Not legal advice.** This describes what the software can do. It does not
> determine your obligations under KVKK, GDPR, or any other regime. You need
> your own privacy notice, retention policy, and registrations.

---

## 1. The repository itself

This project has **no telemetry, no analytics, no crash reporting, no update
check, and no phone-home of any kind**. Nothing is sent anywhere when you clone,
install, or run it. There is no server operated by the maintainer.

The only outbound network connections the software can make are:

1. to a **local** LM Studio instance, if you configure one, and
2. to a **cloud AI provider**, only if you supply an API key and only for the
   features described in [`AI_TRANSPARENCY.md`](AI_TRANSPARENCY.md).

Both are off or local by default.

## 2. Demo data is synthetic

`python manage.py seed_demo` generates entirely fictional customers, staff,
suppliers, wines and orders from a fixed seed. **No real personal data is
included anywhere in this repository**, in the demo data, in the screenshots,
or in the presentation.

Demo phone numbers are deliberately **not dialable** — they carry literal `X`
characters in the subscriber digits (`+90 5XX XXX XX 07`) so that a shared
screenshot, demo database, or slide deck can never reach a real subscriber.
Demo e-mail addresses use the reserved, non-routable `.test` domain.

## 3. When you run it, you are the data controller

Wine House stores data about your customers, your staff and your suppliers on
your own machine, in your own database. The maintainer never sees it. That
makes **you** the data controller with all the duties that follow.

The software gives you tools to meet those duties:

| Capability | Where |
|---|---|
| Per-purpose consent records with withdrawal | `crm.ConsentRecord` |
| Data subject export (access request) | Privacy Centre screen |
| Anonymisation instead of hard deletion, so financial records stay intact | `crm` services |
| Field-level encryption of contact and identity data | `apps/core/fields.py` |
| Role-gated visibility — contact details hidden from roles that don't need them | `crm` views + templates |
| Data minimisation in lists — only the last two digits of a phone number are shown; the full value requires opening the record with an authorised role | `apps/core/templatetags/wh_privacy.py` |
| Retention and purge command for the audit log | `purge_audit_log` |
| Processing-record (ROPA) preparation aid | `docs/privacy/ROPA_PREP.md` |
| PII inventory of every model field | `docs/privacy/pii-baseline.json` |
| Automated PII scan | `privacy_scan` management command |

**Data minimisation by design:** customers' birth *year* is never stored — only
day and month, because the only purpose is a birthday greeting.

## 4. Special categories

Allergy and dietary notes are free-text operational fields used for food safety.
Depending on your jurisdiction they may count as **health data** and attract
stricter rules. The software treats them as sensitive (masked before any cloud
AI call) but **does not** implement a full special-category regime. Assess this
yourself before entering anything clinical.

The system stores no data about children as a distinct category and has no
guardian-consent workflow. Do not use free-text fields to record information
about minors.

## 5. Personal data and the AI layer

Customer preference analysis is classified `RESTRICTED` and is **never** sent to
a cloud provider — it runs locally or not at all. Any feature that is not
explicitly classified is treated as unknown and also stays local: the design
fails closed.

For features where cloud transfer is permitted, personal data is masked first
and a receipt records what was masked. Receipts contain no prompt text, no
response text and no personal data. Full detail in
[`AI_TRANSPARENCY.md`](AI_TRANSPARENCY.md).

You can disable cloud transfer entirely with `WINEHOUSE_AI_LOCAL_ONLY=True`.

## 6. Cross-border transfer

If you enable a cloud AI provider, masked prompt text leaves your country.
Under KVKK and GDPR that is an international transfer with its own conditions.
Decide this deliberately — the local-only default exists precisely so that you
do not do it by accident.

## 7. Encryption, honestly

Contact and identity fields are encrypted with Fernet before being written to
the database. The key lives in `.env` on the same machine as the database.

This protects against **someone stealing the database file** or reading it
casually. It does **not** protect against someone who has compromised the host,
because they have both the database and the key. Do not describe this to your
customers as more than it is.

## 8. Vulnerability and privacy contact

Security issues: see [`SECURITY.md`](SECURITY.md) — report privately, never in
a public issue, and never with real personal data attached.
