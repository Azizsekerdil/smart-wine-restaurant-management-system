# Known limitations

This is the honest list. It exists so that nobody evaluates Wine House on the
basis of what the README's feature list *sounds* like it promises.

Version `0.1.0` — a **pre-production development release**. It has not run a
real restaurant for a real service. Every figure below was measured from this
tree at release time.

---

## 1. Maturity

- **No production deployment.** The software has never been run against live
  business operations. There is no field experience, no incident history, and
  no operational runbook beyond the docs in this repository.
- **One maintainer, best-effort support.** No SLA, no support contract, no
  guaranteed response time.
- **No upgrade path guarantees yet.** Migrations exist and are tested, but
  there has been no real 0.1 → 0.2 upgrade of a database containing real data.
- **Single language of implementation comments.** Most code comments and
  several documents are in Turkish. The UI is TR/EN; the internals are not.

## 2. Scale and deployment envelope

- **Designed for one business on one machine.** SQLite by default; PostgreSQL
  is supported but far less exercised.
- **Not multi-tenant.** There is no tenant isolation layer. Running several
  unrelated businesses on one instance is not supported and not safe.
- **Not hardened for internet exposure.** The intended deployment is a local
  network. See `SECURITY.md` for what that means in practice.
- **No horizontal scaling, no background worker, no task queue.** Long
  operations run in the request cycle or as management commands.
- **Windows-first.** Install scripts, launchers and the packaging path are
  Windows. The Django application itself is portable, but the surrounding
  tooling is not.

## 3. Security gaps

Full detail in [`../SECURITY.md`](../SECURITY.md). Summary:

- No multi-factor authentication.
- HTTPS off by default (local-install assumption).
- PIN login is 4–8 digits — weak by design, contained by session scoping.
- Field encryption key sits beside the database; protects against file theft,
  not host compromise.
- Audit-log and receipt hash chains detect tampering but are **not**
  cryptographic non-repudiation — they are signed with a host-local secret.
- No HTTP-layer rate limiting; brute-force protection is per-account lockout.
- The optional Windows packaging tools (`requirements-packaging.txt`) pull a
  large, older dependency tree and are deliberately excluded from the
  clean-dependency-scan claim.

## 4. Financial, legal and health boundaries

- **Payments are sandbox-only.** No live payment processing is implemented or
  tested. `WINEHOUSE_PAYMENT_MODE` defaults to `sandbox`.
- **E-invoicing is sandbox-only.** No live e-Fatura integration.
- **Not accounting software.** Reports help you run the floor; they are not
  books of account, they are not tax-compliant records, and they have not been
  reviewed by an accountant.
- **Not legal advice.** The compliance and privacy modules (KVKK/GDPR rule
  packs, ROPA preparation, consent records) are record-keeping aids. They do
  not determine your legal obligations. The rule packs ship in `DRAFT` state
  and require an explicit human approval step before they take effect —
  deliberately, so that nobody mistakes them for vetted legal content.
- **Not medical or dietary advice.** Allergen data comes from the structured
  allergen fields you maintain, never from AI text. If AI narrative and the
  allergen field disagree, **the field is authoritative**.
- **No age-verification workflow** despite this being alcohol-sales software.
  Complying with alcohol licensing, age limits and serving hours is entirely
  the operator's responsibility.

## 5. AI limitations

See [`../AI_TRANSPARENCY.md`](../AI_TRANSPARENCY.md) for the full statement.

- AI output is **advisory text only**. It cannot execute any business action.
- Language models can be confidently wrong. Every output is a draft.
- Cloud AI requires your own API key; without one the provider reports
  `NOT_CONFIGURED` and makes no call.
- Cost tracking is an estimate from published pricing, not a billing guarantee.
- Local AI requires you to run LM Studio yourself; model quality varies wildly
  and small local models will underperform the cloud ones noticeably.

## 6. Removed and deliberately absent

- **AI agent authority envelopes were removed from this release.** A delegation
  and monetary-authority model existed in the codebase but no product code path
  ever invoked it — Wine House has no agent that executes commands. Rather than
  ship an admin screen implying a capability that was not wired up, the
  component and its tests were removed. If command-executing agents are added
  later, it should be reintroduced *with* its enforcement point.
- **Internal R&D working documents are not part of this repository** and are
  out of scope for it. They describe process, not product behaviour.

## 7. Testing reality

Measured from this tree:

| Metric | Value |
|---|---|
| Automated tests | 380, all passing |
| Line coverage (all code) | ~73% |
| Django apps | 16 |
| Database tables (product apps) | 129 |
| UI templates | 72 |
| Roles | 19 |
| Built-in reports | 13 |
| Database migrations | 23 |
| Runtime dependencies (full closure) | 29 |

What the tests **do not** cover:

- No browser/end-to-end UI test suite. Screens are exercised through Django's
  test client, not a real browser. The screenshot capture script uses
  Playwright but it is a capture tool, not an assertion suite.
- No load, soak, or concurrency testing. Behaviour under simultaneous POS users
  is unknown.
- No PostgreSQL test run in CI — tests run on in-memory SQLite.
- No upgrade/migration test against a populated production-shaped database.
- Coverage is uneven: core business rules are well covered; several view layers
  (training, reporting views) sit below 50%.

## 8. Roadmap — what would move this to 1.0

Ordered by how much each would change the risk picture:

1. Multi-factor authentication for the management surface.
2. A real pilot deployment in one restaurant, with an incident log.
3. HTTP-layer rate limiting and a documented reverse-proxy deployment.
4. PostgreSQL in CI, plus a populated-database upgrade test.
5. Browser-level end-to-end tests for the POS and KDS flows.
6. Key management that does not keep the encryption key beside the database.
7. Live payment / e-invoice integration, properly certified.
8. English translation of internal documentation and code comments.

None of this is committed to a date. Treat it as direction, not a promise.
