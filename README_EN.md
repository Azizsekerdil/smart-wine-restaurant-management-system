# 🍷 Wine House

**Smart Wine Restaurant Management System** — *Akıllı Şarap Restoranı Yönetim Sistemi*

A locally-hosted, offline-resilient, role-based management system for
wine-focused restaurants. From floor operations and a digital wine cellar to
inventory costing and an AI sommelier assistant — in a single application.

| | |
|---|---|
| **Version** | 0.1.0 |
| **Status** | Development release — pre-production |
| **Platform** | Windows (local installation) |
| **Languages** | Turkish · English |
| **License** | Proprietary — see [`LICENSE`](LICENSE) |

📖 **[Türkçe belgeler](README_TR.md)** · This is the English version

> **Note on language:** The application interface, database field labels and
> documentation are primarily Turkish. English interface strings are declared
> via Django's i18n framework but the translation catalogues are not yet
> compiled — see *Known limitations* below.

---

## Quick start (Windows)

```powershell
# 1. Install (once)
powershell -ExecutionPolicy Bypass -File INSTALL_WINE_HOUSE.ps1
```

```
2. Double-click START_WINE_HOUSE.bat
3. Browser opens at http://127.0.0.1:8000/
```

Detailed guide: [`docs/INSTALLATION_WINDOWS.md`](docs/INSTALLATION_WINDOWS.md)

---

## What it does

### Floor operations
Table map and statuses · reservations with conflict detection · waitlist ·
orders · kitchen/bar/wine display screens (KDS) · kitchen order tickets (KOT) ·
bill splitting and order merging · multi-method payment · end-of-day close and
cash reconciliation

### Digital wine cellar
Producer, appellation, grape composition and vintage records · cellar/cabinet/
rack layout · temperature and humidity monitoring · lot-based bottle stock ·
**by-the-glass sales correctly deducted from opened bottles** · realised yield
and spillage analysis · Coravin/preservation system distinction · cork taint and
oxidation records · tasting notes · drink-window alerts · food–wine pairing ·
cellar valuation · duplicate record detection

### Menu, inventory and costing
Recipes and portion costing · allergen and dietary tags · dynamic pricing and
happy hour · menu engineering (Star/Plowhorse/Puzzle/Dog) · FIFO/FEFO inventory ·
expiry alerts · waste analysis · suppliers, purchasing and quotation comparison

### Artificial intelligence (provider-agnostic)
LM Studio (local) · Anthropic Claude · NVIDIA · Mock (offline testing)
Sommelier assistant · food–wine pairing · natural-language report queries ·
end-of-day manager summary · cost and token tracking

> All core restaurant functions work fully **with AI disabled**.

### Security and compliance
19 roles · least-privilege · second approval for critical operations ·
append-only audit log · encrypted sensitive fields · GDPR/KVKK consent, data
portability and erasure · personal-data masking before any cloud call ·
encrypted backups with verified restore

---

## Key design decisions

| Decision | Rationale |
|---|---|
| **Local-first** | The restaurant keeps working when the internet drops. Application and database live on the same machine. |
| **AI is optional** | The system is fully functional without AI; AI only proposes, it never writes to the database. |
| **Local model preference** | Customer data does not leave the premises by default. If a cloud call is needed, personal data is masked and the user is shown *exactly what was sent*. |
| **Financial records are frozen** | An order line copies its price at creation time; changing the menu price later never alters past bills. |
| **Trace instead of delete** | Orders, payments, stock movements and audit entries are never physically deleted. Corrections are made with reversing entries. |
| **Payments are sandboxed** | Real payment and e-invoice integrations exist only as adapter interfaces; enabling live mode requires explicit user consent. |

---

## Project status

| Metric | Value |
|---|---|
| Tests | 255 passing |
| Coverage (core business rules) | 82% |
| Known vulnerabilities | None (`pip-audit` clean) |
| Static security analysis | 0 high, 1 medium (deliberate), 28 low |
| Runtime dependencies | 27 packages, all permissively licensed |

Open the **Feature Status** screen in the application, or read
[`docs/STATUS.md`](docs/STATUS.md), to see which features are ready,
experimental or planned.

---

## Known limitations

The following are deliberately incomplete and are flagged in the UI as
*Experimental* or *Planned*:

- Live payment and e-invoice integration (adapter interface only)
- Thermal printer driver
- Bulk email/SMS campaign dispatch
- Cellar sensor integration
- End-to-end wine label image analysis
- Multi-terminal offline synchronisation
- Windows `.exe` package (PyInstaller config ready, not built)
- **English translation catalogues are not yet compiled** — language switching
  and locale-aware number/date/currency formatting work, but most interface
  strings still render in Turkish

---

## Documentation

Documentation is written in Turkish. Key entry points:

| Document | Contents |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Architecture, modules, data flows |
| [`docs/API.md`](docs/API.md) | REST API reference |
| [`docs/SECURITY.md`](docs/SECURITY.md) | Threat model and security controls |
| [`docs/PRIVACY.md`](docs/PRIVACY.md) | GDPR/KVKK compliance |
| [`docs/AI_CONFIGURATION.md`](docs/AI_CONFIGURATION.md) | AI provider configuration |
| [`docs/BACKUP_RESTORE.md`](docs/BACKUP_RESTORE.md) | Backup and restore |
| [`docs/LICENSE_AUDIT.md`](docs/LICENSE_AUDIT.md) | Licence audit and code provenance |
| [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) | Test report and known issues |
| [`USER_GUIDE_EN.md`](USER_GUIDE_EN.md) | Role-based user guide |

---

## Responsible use

This system is intended for businesses that sell alcoholic beverages.

- Alcoholic beverages **may not be sold to persons under 18**.
- AI suggestions are **not medical or health advice**; the system never makes
  health claims.
- Allergen information reflects the establishment's own declaration and does not
  replace kitchen verification.
- Excessive alcohol consumption is harmful. Do not recommend alcohol to guests
  who will be driving.

---

*Wine House · Aziz Şekerdil · 2026*
