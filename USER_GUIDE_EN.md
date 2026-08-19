# User Guide

> Wine House 0.1.0 · Role-based guide

> **Language note:** The application interface is primarily Turkish. English
> translation catalogues are declared via Django i18n but not yet compiled, so
> most on-screen text still renders in Turkish. Turkish menu labels are given
> in *italics* throughout this guide so you can follow along.

---

## Signing in

| Route | Address |
|---|---|
| Password login | `http://127.0.0.1:8000/hesap/giris/` |
| POS quick login (staff code + PIN) | `http://127.0.0.1:8000/hesap/pin/` |

The PIN is 4–8 digits, set by your administrator. Five failed attempts lock the
account for **15 minutes**.

**Language switch:** TR / EN buttons, top right. Your choice is saved to your
account.

### Status badges at the top of every screen

| Badge | Meaning |
|---|---|
| *GELİŞTİRME MODU* | System is in development configuration |
| *Ödeme: Sandbox* | **No real money movement** |
| *Gizlilik modu açık* | Personal data is masked before any AI call |

---

## 🍽️ Waiter — *Garson*

**Open a table** — *Salon → Masa planı*. Click a free table, enter guest count.

Table colours: green free · blue seated · yellow ordered · grey served ·
red bill requested

**Take an order** — select items, quantity, seat number and special requests.

> **Always enter the seat number** if the bill might be split later.

**Send to kitchen** — *"Mutfağa gönder"*. Food goes to the kitchen, drinks to
the bar, wine to the sommelier screen automatically. Already-sent lines are
never re-sent.

**Discounts** — your discount limit is capped (5% by default). Exceeding it does
**not** apply the discount; an approval request is raised instead. Comps
(free items) **always** require approval.

**Split the bill** — *"Hesabı böl"* creates a separate order per seat. Orders
with a partial payment cannot be split.

---

## 🍷 Sommelier

**Find a wine** — *Kav → Şaraplar*. Search by name, producer, SKU or barcode.

**Wine card** — identity, tasting profile (body / acidity / tannin / sweetness),
grape composition, serving temperature, decanting time, drink window, lots, open
bottles and food pairings on one screen.

**Open a bottle** — choose a service method:

| Method | Freshness window |
|---|---|
| Standard | 48 hours |
| Preservation (argon / vacuum) | 1 week |
| Needle system (Coravin-like) | 30 days |
| Tasting | 24 hours |

The system deducts from the lot that must be consumed first (**FEFO**).

**Pour a glass** — choose volume and pour type.

- If an open bottle has enough volume, it is used
- Otherwise a **new bottle is opened automatically** and one bottle is deducted
  from stock
- **Record spillage and comps too** — yield analysis depends on it

**Open bottles** — *Kav → Açık şişeler*. Bottles past their freshness window are
highlighted. The *Verim* (yield) column shows how much was actually served: if a
bottle yields 4 glasses instead of the theoretical 5, there is spillage or
over-pouring.

**Wine faults** — record cork taint, oxidation, spillage or breakage. Stock is
deducted and the loss is costed automatically.

**AI pairing** — *Yapay Zekâ → Sommelier*. Describe the dish, get a suggestion.

> Suggestions are drawn **only from wines currently in stock** and are never
> written to the pairing records without your approval.

---

## 👨‍🍳 Kitchen and Bar

*Hazırlık → Mutfak / Bar / Şarap ekranı* · The screen refreshes every 30 seconds.

| Border | Meaning |
|---|---|
| Grey | Within target time |
| Yellow | 70% of target elapsed |
| Red | **Overdue** |
| Green | Ready |

**Advance a ticket** — *"İlerlet →"*: Queued → Preparing → Ready → Served

⚠️ **Allergen warnings** appear as a red line on the ticket. This reflects the
guest's own declaration — verify with the supervisor if in doubt.

---

## 💳 Cashier — *Kasiyer*

**Take payment** — order → *"Ödeme al"* → method and amount

- Partial payments are allowed; the outstanding balance is shown
- Card payments require a reference
- A fully paid order closes automatically and the table moves to "cleaning"

> **Sandbox notice:** no real payment gateway is connected in this release. The
> record is kept; no money moves.

**Void / refund** — if you lack authority, an approval request is created and the
operation is **not** applied.

---

## 📋 Host / Reservations

*Salon → Rezervasyonlar* · Filters: today · upcoming · all

When assigning tables the system performs a **conflict check**: the same table
cannot be double-booked for overlapping time windows. Capacity is checked too.

Allergy notes entered on a reservation appear on the kitchen ticket.

**Waitlist** — entries exceeding their quoted wait are highlighted.

---

## 📦 Warehouse and purchasing

| Task | Screen | Note |
|---|---|---|
| Stock | *Stok → Stok kalemleri* | The "*Minimum altı*" filter shows critical items |
| Lots / expiry | *Stok → Partiler* | Red: expired · Yellow: expiring soon |
| Goods receipt | *Sipariş → mal kabul → "Stoğa işle"* | Enter rejected quantity separately |
| Stock count | *Sayım → "Farkları işle"* | Variance becomes an immutable stock movement |
| Waste | *Stok → Fire* | Cost is calculated automatically |
| Reorder suggestions | *Stok → Sipariş önerileri* | **Suggestions only** — no order is created |

Stock is issued **FEFO**: the lot expiring soonest leaves first.

---

## 📊 Manager

**End of day** — *Salon → Gün sonu*

> The day cannot be closed while orders are still open. Close them all first.

Enter the counted cash; the system compares it with the expected amount and
shows the variance. After closing, the figures are **frozen** and reports read
from them.

**Reports** — *Raporlar* · 13 reports · choose a period · download PDF / Excel /
CSV. Turkish characters render correctly in all three formats.

**Approval queue** — *Profil → Onay kuyruğu*. You cannot approve your own
request (separation of duties).

**Audit log** — *Profil → Denetim kaydı*. The "only failed" filter shows
unauthorised access attempts.

**Users and roles** — *Profil → Kullanıcılar / Roller*. The *Roller* screen shows
exactly which permissions each role holds.

---

## 🔐 System administrator

| Task | How |
|---|---|
| Health check | `CHECK_WINE_HOUSE.bat` — 26 checks, prints no secrets |
| Backup | *Yedekleme* screen or `BACKUP_WINE_HOUSE.bat` |
| Restore | Requires approval; default target is the **test database** |
| AI settings | *Yapay Zekâ → Sağlayıcı ayarları → "Bağlantıları sına"* |
| Feature status | *Profil → Özellik durumu* |

> ⚠️ Store `WINEHOUSE_FIELD_ENCRYPTION_KEY` **separately from the backups**.
> Without it, encrypted backups cannot be opened.

> API keys are **never entered through the interface**; they live only in `.env`
> or an operating-system environment variable.

---

## Responsible service

- Alcoholic beverages **may not be sold to persons under 18**
- AI suggestions are **not medical advice**
- Allergen data is the establishment's declaration, not a substitute for kitchen
  verification
- Do not recommend alcohol to guests who will be driving
