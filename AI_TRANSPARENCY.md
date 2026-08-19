# AI Transparency

This document states plainly what the AI layer in Wine House does, what data it
sees, where that data goes, and what it is **not** allowed to decide.

## 1. AI is optional

Wine House runs fully without any AI provider configured. If no key is set, the
provider reports `NOT_CONFIGURED`, **makes no network call**, and every non-AI
feature — orders, tables, cellar, stock, reporting, HR, backups — keeps working
normally. AI is an assistive layer, never a dependency.

## 2. Providers

| Provider | Where it runs | Needs a key | Default |
|---|---|---|---|
| **LM Studio** | Your own machine | No | **Yes — the default** |
| **Mock** | Your own machine | No | Used in tests; no network at all |
| Anthropic Claude | Anthropic's servers | Yes | Off unless configured |
| NVIDIA | NVIDIA's servers | Yes | Off unless configured |

The default is **local-first**. `WINEHOUSE_AI_PREFER_LOCAL=True` means a cloud
provider is only reached if the local one fails. Setting
`WINEHOUSE_AI_LOCAL_ONLY=True` makes cloud transfer impossible regardless of
any other setting.

## 3. What the AI is used for

- Sommelier assistant and food–wine pairing suggestions
- Natural-language querying of your own reports
- End-of-day manager summary
- Menu text drafting and translation
- Training content assistance
- Anomaly and demand-forecast commentary
- Wine label photo interpretation

## 4. What the AI never does

The AI layer **produces text for a human to read**. It has no authority to act.
Specifically, it cannot and does not:

- place, modify, void or discount an order
- change a price, a recipe, or a stock level
- create, modify, or delete a customer record
- approve anything in the approval queue
- take, apply, or restore a backup
- change a user, a role, or a permission
- execute a payment or issue an invoice
- take disciplinary or performance action about a member of staff

Every suggestion it produces is displayed and requires a human to act on it.
Where a suggestion maps to a critical action, the existing second-approval
workflow still applies — the AI does not shortcut it.

## 5. Before anything leaves your machine

When a cloud provider is used, the outgoing prompt passes through a masking
step (`apps/core/security.mask_pii`) that redacts e-mail addresses, phone
numbers, national identity numbers, IBANs and card numbers, plus customer names
pulled from your own database. What was masked is recorded and shown to the
user alongside the answer.

A pre-action policy layer (`apps/hsp/`) classifies each AI feature by data
sensitivity **before** the call is made and decides whether cloud transfer is
allowed at all:

- Customer preference analysis is classified `RESTRICTED` → **local only**,
  never sent to a cloud provider.
- Any feature not explicitly classified is treated as `UNKNOWN` → **local
  only**. The design fails closed: an unclassified feature cannot leak to the
  cloud by omission.
- Business/financial features are `CONFIDENTIAL` → cloud allowed **only with
  masking applied**.
- Database policy rules can make this stricter but can never make it looser;
  loosening requires a reviewed code change.

Every decision writes a receipt recording the feature, data class, decision,
provider and outcome. Receipts contain **no prompt text, no response text and
no personal data**. They are chained by hash so tampering is detectable — see
the honest limits of that mechanism in [`SECURITY.md`](SECURITY.md).

## 6. API keys

- Keys are supplied by you after installation, via `.env` or the in-app
  settings screen. `.env.example` ships with **empty values only**.
- No key of any kind is committed to this repository.
- Stored keys are encrypted at rest with the field-encryption key.
- The UI shows only the provider name, its status, and the **last four
  characters** of the key.
- A connection test only runs when you explicitly click it.
- Keys are masked out of logs and error output.

## 7. Cost

Cloud calls cost money. Token usage and estimated cost are tracked per call and
shown on the cost screen. `WINEHOUSE_AI_MONTHLY_COST_LIMIT_USD` caps monthly
spend (default 10 USD). This is a **best-effort estimate based on published
provider pricing**, not a billing guarantee — reconcile against your provider's
own invoice.

## 8. Accuracy and limits — please read

Language models produce fluent text that can be **confidently wrong**. Treat
every output as a draft.

- **Wine and food suggestions** are stylistic opinion, not fact. Verify vintage,
  producer and availability against your own cellar records.
- **Allergen and dietary information must never be taken from the AI.** Allergen
  data in Wine House comes from the structured allergen fields you maintain on
  each menu item. If AI text and the allergen field disagree, the field is
  authoritative. Getting this wrong can seriously harm someone.
- **Financial and forecast commentary is not financial advice.** Numbers in
  reports come from your database; the AI's narrative around them may
  misinterpret them. Do not make purchasing, pricing or tax decisions on the
  narrative alone.
- **Nothing here is legal advice.** The compliance and privacy modules
  (KVKK/GDPR rule packs, ROPA preparation, consent records) are organisational
  aids that help you keep records. They do not determine your legal obligations
  and are not a substitute for a lawyer or your data protection officer.
- **Nothing here is medical or health advice.** Dietary and allergy notes are
  free-text operational fields, not clinical records.
- **Staff performance figures are descriptive statistics, not judgements.** The
  system deliberately applies no automated consequence to any member of staff.
  Any employment decision is a human decision, made by a human, on the record.

## 9. Turning it off entirely

Set `WINEHOUSE_AI_DEFAULT_PROVIDER=mock` and `WINEHOUSE_AI_LOCAL_ONLY=True`, or
simply leave every API key empty. The AI screens will report `NOT_CONFIGURED`
and no network call will be made.
