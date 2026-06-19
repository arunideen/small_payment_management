# Deep Research: Electronic Vendor Payments (UPI / Cards / Bank) via External Integration

> Research deliverable for adding an external-service integration that pays vendors
> from the **Small Payment Management** module (Odoo 19) using UPI, cards, and other
> payment modes. Grounded in the current `addons/custom/small_payment_management` code.
>
> Date: 2026-06-19 · Author: research compiled with Claude Code

---

## 1. The single most important architectural fact

The module already depends on Odoo's `account`, and Odoo ships a built-in **payment
provider framework** (`payment.provider`, under Accounting → Configuration → Payment
Providers). **Do not build this feature on it.** That framework is exclusively
**inbound** — it exists so *customers pay you* (cards/UPI/netbanking on invoices and
the website). It has no concept of pushing money *out* to a vendor.

Paying vendors is an **outbound payout / disbursement** problem, and Odoo ships **no
standard abstraction for it**. Standard Odoo "vendor payment" (`account.payment`, the
*Register Payment* button on a vendor bill) only records *that a payment happened* and
posts the journal entry — it never moves real money. The closest framework that
actually moves money outbound is the OCA **`bank-payment`** suite
(`account_payment_order` + ISO 20022 / SEPA / NACH file generation), but that is
**batch-file-to-bank**, not real-time API, and not India-UPI-native.

So the feature is genuinely net-new: **a thin outbound "payout provider" layer that
talks to a disbursement API and writes the result back onto the existing SPM documents
and Odoo's accounting.**

## 2. Where vendor payments live in *this* module today

Vendor money currently leaves the system through these documents, and **none of them
actually disburse** — they are approval/recording shells with `TODO` stubs:

| Model | File | Vendor relevance | Disbursement today |
|---|---|---|---|
| `spm.petty.cash.voucher` | `models/petty_cash.py:59` | Has `payee_type` (`employee`/`vendor`/`other`) + `partner_id` — **primary vendor-pay document** | None — no journal posting; balances are stubs (`_compute_balances`, `petty_cash.py:27`) |
| `spm.reimbursement.batch` | `models/expense.py:60` | Batch of expense sheets → marked `paid` | Just a `draft`→`paid` state flag |
| `hr.expense.sheet` | `models/expense.py:14` | Standard Odoo expense reimbursement | Inherits core, not wired to payout |
| `spm.advance` | `models/expense.py:33` | Cash advance to employee | None |

Everything routes through the generic `approval.workflow.mixin`
(`models/approval.py:196`). That is the **right insertion point**: a payout should only
ever fire *after* `approval_state == "approved"`. This is the built-in maker-checker
control that payout security demands.

**Implication:** the natural home for "pay this electronically" is
`spm.petty.cash.voucher` (when `payee_type == 'vendor'`) and `spm.reimbursement.batch`,
plus optionally standard vendor bills (`account.move`, `move_type='in_invoice'`) if the
feature should cover AP broadly and not just petty cash.

## 3. "UPI, cards, or any other mode" — what those modes really are

This phrase mixes two different axes. Keeping them straight prevents a wrong build.

**A. Destination rail (how the vendor receives money)** — what a payout API gives you:

- **UPI** → pay to a VPA (e.g. `vendor@okhdfc`). Low-ticket, instant, 24×7.
- **IMPS** → to bank account (IFSC + acct no), instant, ≤ ₹5L, 24×7.
- **NEFT** → to bank account, batched, no upper limit, cheapest.
- **RTGS** → to bank account, ≥ ₹2L, high value.
- **Payout to card** → money lands on the vendor's *credit card* via IMPS/NEFT (a real
  RazorpayX fund-account type).

**B. Funding source (where *your* money comes from)** — a separate product category:

- **Current-account balance** (the default; you prefund a provider-managed current
  account).
- **Your corporate credit card pays the vendor** — "pay any vendor with a credit card."
  Products like **EnKash, Karbon, Volopay, RazorpayX Vendor Payments** charge your
  company card and deposit a *bank transfer* into the vendor's account. Used for
  working-capital float / card rewards, with a convenience fee (~1.5–2%).

> A vendor is almost never *charged a card*. "Cards" in B2B vendor payments means either
> **paying out to a card** (destination rail) or **funding the payout with your card**
> (funding source). Which one is intended must be confirmed — see §10.

## 4. Provider landscape (India)

The market splits cleanly.

**For programmatic bank/UPI payouts (recommended core):**

- **RazorpayX Payouts** — the most polished, best-documented payout API. One REST API →
  IMPS/NEFT/RTGS/UPI/card. Mandatory **idempotency keys** (since 15 Mar 2025), robust
  webhooks, `queue_if_low_balance`. Funds sit in a Razorpay-managed current account at a
  partner bank (ICICI/Axis/RBL/YES). ~₹2–5 per payout. Also has a higher-level **Vendor
  Payments** product (handles vendor master, invoice tracking, **TDS** deduction).
- **Cashfree Payouts** — the strongest pure-payouts competitor, often lowest per-txn
  cost, pays to bank/UPI/wallet 24×7 incl. bank holidays. Functionally equivalent API
  shape (beneficiary → transfer).

**For card-funded vendor payments (only if card-as-source is required):**

- **EnKash / Karbon / Volopay** — spend-management + corporate card platforms that let
  you pay vendors via card; integrate UPI/NEFT/RTGS/cards. APIs are less open/standard
  than RazorpayX; often more dashboard-driven.

**Recommendation:** build the integration against **RazorpayX Payouts** first (cleanest
API, idempotency, webhooks, documented best-practices), behind a **provider-agnostic
interface** so Cashfree (or a card-funding provider) can be added later without touching
the SPM documents.

## 5. Proposed architecture in Odoo

Add a small set of models. Keep the SPM documents thin; isolate all provider/HTTP/secret
logic in a service layer.

```
spm.payout.provider        (config: provider type, key id, key secret/credential,
                            source account_number, environment test/live, active)
        │
spm.payout.method          (per-provider rail config: upi/imps/neft/rtgs/card,
                            limits, fees, default selection rules)
        │
res.partner.bank  +  new fields on res.partner   (vendor VPA, beneficiary/fund-account
                            cache id, KYC/verification status)
        │
spm.payout                 (the transaction record — one per disbursement)
   ├─ source_document (Reference: voucher / reimbursement batch / account.move)
   ├─ partner_id, amount, currency, rail
   ├─ provider_id, idempotency_key (stored, unique)
   ├─ provider_contact_id, provider_fund_account_id, provider_payout_id
   ├─ state: draft→queued→processing→processed→reversed/failed/cancelled
   ├─ failure_reason, utr (bank reference), fees
   └─ account_payment_id  (link to the Odoo journal entry it posts)
        │
spm.payout.webhook.event   (raw inbound webhook log: event id, signature ok?,
                            payload, processed flag — for idempotent replay)
```

Why a dedicated `spm.payout` model rather than overloading `account.payment`:

- A payout has a **lifecycle the bank controls asynchronously** (`processing →
  processed/reversed`) that `account.payment`'s draft/posted model can't represent.
- You need to store provider IDs, idempotency keys, UTR, fees, retry history, and
  reversal handling.
- You still **create an `account.payment`** (and reconcile it) on `processed` so the GL
  stays correct — `spm.payout` *drives* it, doesn't replace it.

## 6. The integration flow (RazorpayX shape, provider-agnostic underneath)

The canonical 3-step model is **Contact → Fund Account → Payout** (or one Composite
call):

1. **On vendor setup / first payout** — create/lookup a **Contact** (the vendor) and a
   **Fund Account** (their bank acct *or* VPA). Cache `provider_contact_id` /
   `provider_fund_account_id` on the partner so they are not recreated.
2. **On "Pay" (only after `approval_state == 'approved'`)** — generate a **stored
   idempotency key** (e.g. the `spm.payout` UUID), call *create payout* with
   `account_number`, `fund_account_id`, `amount`, `mode` (rail),
   `queue_if_low_balance=true`. Persist the returned `payout_id` and move to
   `processing`/`queued`.
3. **Asynchronously** — receive **webhooks** (`payout.processed`, `payout.reversed`,
   `payout.failed`):
   - **Verify the `X-Razorpay-Signature` HMAC** against the raw body using the webhook
     secret. Reject on mismatch.
   - Razorpay is **at-least-once** delivery → **dedupe** on event id via
     `spm.payout.webhook.event`.
   - On `processed`: set `spm.payout` → `processed`, store UTR, **create + post +
     reconcile the `account.payment`** against the vendor bill/voucher.
   - On `reversed`/`failed`: reverse any provisional entry, set state, notify, re-open
     the source document for retry.

Polling the payout status endpoint is the fallback if a webhook is missed.

## 7. Security & compliance (where vendor-payout projects fail)

- **Maker–checker is mandatory.** Reuse the existing `approval.workflow.mixin` so a
  payout can only be *initiated* after full approval. Consider a *second* segregation:
  the person who approves the expense ≠ the person who releases the payout.
- **Webhook authenticity:** always HMAC-verify the raw payload; never trust state
  transitions that arrive only over the webhook without signature.
- **Idempotency everywhere:** mandatory for the payout call (provider rejects without it
  since Mar 2025) *and* for the webhook handler. A double-fire here = double-paying a
  vendor.
- **Secrets:** store API key/secret as Odoo system parameters or env-injected config,
  **never** in source or in `spm.payout.provider` plaintext visible to non-admins.
  Restrict the provider config to a finance-admin group (the module already has group
  infrastructure under `security/`).
- **Regulatory (India):** the provider holds the PA/PA-CB authorization and a **current
  account strictly in your legal entity's name** (RBI Master Directions 2025). You
  inherit **KYC/PMLA** obligations on the *vendor side* (PAN/bank verification) — surface
  a `verification_status` on the partner and block payouts to unverified beneficiaries.
  Use the provider's **penny-drop/VPA validation** before first payout.
- **TDS (Sec 194C/194J etc.):** vendor payouts frequently require tax deduction at
  source. Either deduct in Odoo before calling the payout (pay net), or use RazorpayX
  **Vendor Payments** which computes/holds TDS. Decide explicitly — paying gross when TDS
  was due is a compliance liability.
- **Audit trail:** the module already has an append-only `approval.amendment.log`
  (`approval.py:173`, `unlink` blocked). Mirror that discipline: every payout state
  change logged immutably (who released, idempotency key, provider ids, UTR).

## 8. Edge cases that must be designed for (not bolted on)

- **Low balance** → `queue_if_low_balance=true` so payouts queue rather than fail;
  surface a "balance low / N payouts queued" alert (a cron pattern already exists:
  `_cron_check_replenishment`, `petty_cash.py:36`).
- **Reversal after `processed`** (bank bounce) → must reverse the GL entry and re-open
  the document.
- **Duplicate / out-of-order webhooks** → dedupe + state machine that ignores backward
  transitions.
- **Partial batch failure** in `spm.reimbursement.batch` → per-line payout state, not a
  single batch flag (the current `draft/paid` selection in `expense.py:71` is too
  coarse).
- **Network timeout on create** → status unknown; reconcile by **re-querying with the
  same idempotency key** before retrying (never blind-retry).
- **Currency** — payout APIs are INR-only; guard non-INR documents.

## 9. Suggested phased roadmap

1. **Phase 0 — Foundations (no external calls):** add `spm.payout`,
   `spm.payout.provider`, partner bank/VPA + verification fields, state machine, security
   groups, and the `account.payment` posting/reconciliation logic. Wire the "Pay" button
   on the voucher gated on approval. *Validates the Odoo-side design end-to-end with a
   mock provider.*
2. **Phase 1 — RazorpayX in test mode:** service layer (contact/fund-account/payout),
   idempotency keys, signed-webhook endpoint (`http.Controller`), webhook dedupe + status
   polling fallback. Run against Razorpay **test** keys.
3. **Phase 2 — Hardening:** reversals, queued/low-balance, retries, beneficiary
   verification (penny-drop), TDS handling, audit log, alerts, dashboards (OWL dashboards
   already exist in `static/src/`).
4. **Phase 3 — Provider abstraction & extras:** second provider (Cashfree) behind the
   same interface; optionally card-funded payments (EnKash/Karbon) or payout-to-card;
   extend coverage to standard `account.move` vendor bills.

## 10. Open decisions (needed before a build plan)

These genuinely change the design:

1. **Country/currency** — assumed **India / INR** (from UPI + company domain). A
   non-India target flips the whole provider choice.
2. **"Cards" meaning** — pay *out to* a vendor's card, or *fund payouts with your*
   corporate card? Different providers.
3. **Scope of documents** — only SPM petty-cash vouchers + reimbursements, or also
   standard Odoo vendor bills (full AP)?
4. **TDS** — is tax-at-source deduction required in this feature?

## 11. Sources

- RazorpayX Payouts: <https://razorpay.com/x/payouts/> · Payouts API:
  <https://razorpay.com/docs/api/x/payouts/> · Best Practices:
  <https://razorpay.com/docs/x/payouts/best-practices/> · Idempotency:
  <https://razorpay.com/docs/api/x/payout-idempotency/> · Fund Accounts:
  <https://razorpay.com/docs/x/fund-accounts/> · Composite Payout:
  <https://razorpay.com/docs/api/x/payout-composite/create/bank-account/>
- RazorpayX Webhooks: <https://razorpay.com/docs/x/webhooks/> · Validate & Test:
  <https://razorpay.com/docs/webhooks/validate-test/> · Error Types:
  <https://razorpay.com/docs/errors/x/>
- RazorpayX Vendor Payments (TDS): <https://razorpay.com/x/vendor-payments/> · RazorpayX
  for Indian Teams 2026: <https://productgrowth.in/tools/payments/razorpay-x/>
- Razorpay vs PayU vs Cashfree 2026:
  <https://superlaunch.in/blog/razorpay-vs-payu-vs-cashfree-indian-saas-2026> · EnKash
  Vendor Payments: <https://www.enkash.com/vendor-payment> · RazorpayX alternatives:
  <https://happay.com/blog/best-razorpayx-alternatives-competitors/>
- Odoo 19 Payment Providers (inbound):
  <https://www.odoo.com/documentation/19.0/applications/finance/payment_providers.html> ·
  payment.provider dev ref:
  <https://www.odoo.com/documentation/19.0/developer/reference/standard_modules/payment/payment_provider.html>
  · OCA bank-payment (outbound files): <https://github.com/OCA/bank-payment>
- RBI Master Directions 2025 for Payment Aggregators:
  <https://www.mondaq.com/india/financial-services/1726232/rbi-master-directions-2025-compliance-and-operational-challenges-for-payment-aggregators>
  · RBI PA/KYC compliance: <https://stripe.com/in/guides/rbi-guidelines-kyc-direction>
