# Small Payment Management — Workflow Diagrams

End-to-end process for the `small_payment_management` module. Diagrams use
[Mermaid](https://mermaid.js.org/) and render directly on GitHub. Section
references (§) point to `odoo19-petty-cash-expense-solution-report.md`.

---

## Pain points addressed

These flows exist to remove specific operational pain; each maps to the diagrams below.

| Pain point | Removed by |
|---|---|
| Manual, untracked petty cash & reconciliation gaps | Diagram 5 (imprest cycle) + Diagram 1 |
| Slow, opaque, unauditable approvals; "approve low, raise later" | Diagrams 1 & 3 (matrix + lifecycle) |
| Approver away / needs info / chain must change mid-flow | Diagram 3 (RFI, delegation, live amendment) |
| Overspend found only after posting | Diagram 4 (pre-commitment budget) |
| Records edited/deleted to hide history; no segregation of duties | Diagram 2 (engine-guarded states) + Diagram 3 (immutable amendments) |
| Vendor payments made manually, double-paid, unreconciled | Diagram 6 (electronic payout: idempotent create, signed webhook, reconciled `account.payment`) |

---

## 1. End-to-end process

```mermaid
flowchart TD
    subgraph CFG["1 - Configuration (Admin)"]
        A1["Branches"]
        A2["Expense Types & Categories<br/>(budget-check flags)"]
        A3["Policy Rules"]
        A4["Approval Matrices<br/>(company / branch / type / amount)"]
        A5["Budgets"]
    end

    subgraph CAP["2 - Capture"]
        B1["Petty Cash Voucher"]
        B2["Expense / Expense Report"]
        B3["Cash Advance"]
        B4["Float Top-up"]
        B5["Float Reconciliation"]
    end

    CFG --> CAP
    CAP --> C{"3 - Submit"}
    C --> D["Policy checks<br/>(limits, duplicates, receipts)"]
    D --> E{"Budget check<br/>required?"}
    E -- "off / within budget" --> F["Resolve approval matrix"]
    E -- "warn (proceed, flag)" --> F
    E -- "block & over budget" --> X1["Blocked:<br/>fix or cancel"]
    F --> G["Generate approver chain"]
    G --> H[["Dynamic approval<br/>(see Diagram 3)"]]
    H -- approved --> I["Reserve budget"]
    I --> J["Post journal entry"]
    J --> K{"Payment mode"}
    K -- "petty cash" --> K1["Cr Petty Cash / Dr Expense"]
    K -- "reimburse" --> K2["Pay employee / batch"]
    K -- "electronic payout<br/>(UPI / card / bank)" --> K3[["Vendor payout integration<br/>(see Diagram 6)"]]
    K1 --> L["Consume reservation<br/>update utilization"]
    K2 --> L
    K3 --> L
    H -- rejected --> X2["Rejected:<br/>reason + notify"]
    L --> M[("Dashboards & Reports")]
```

---

## 2. Document lifecycle (shared state pattern, §6.2)

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> submitted: submit
    submitted --> under_approval: matrix resolved
    under_approval --> under_approval: tier approved (activate next)
    under_approval --> info_requested: request info
    info_requested --> under_approval: answer received
    under_approval --> approved: last tier approved
    approved --> posted: post journal entry
    posted --> paid: register payment (manual / cash)
    posted --> paying: initiate electronic payout (UPI / card / bank)
    paying --> paid: payout processed (signed webhook + reconcile)
    paying --> payout_failed: failed / reversed
    payout_failed --> paying: retry (same idempotency key family)
    paid --> [*]

    submitted --> rejected: reject
    under_approval --> rejected: reject
    draft --> cancelled: cancel
    submitted --> cancelled: cancel
    rejected --> draft: resubmit (restart/resume)
    rejected --> [*]
    cancelled --> [*]
```

> Users never edit `state` directly — transitions are guarded by the engine.
> Submitted documents are never deleted: cancel-with-reason instead (§12.3).
> The `paying`/`payout_failed` sub-states are driven by the external payout
> provider asynchronously (see Diagram 6); the document only reaches `paid` once
> a signed `payout.processed` webhook is received and the `account.payment` is
> reconciled.

---

## 3. Dynamic approval engine (§7)

```mermaid
flowchart TD
    S["Submit document"] --> R["Resolve matrix<br/>most specific by dimensions + amount band"]
    R -- "no match" --> ERR["Error:<br/>no matrix configured"]
    R --> G["Build ordered approver chain<br/>(roles &rarr; users, apply standing delegations)"]
    G --> T["Activate tier n<br/>(activity + email + dashboard card)"]
    T --> N{"Approver action"}

    N -- "Approve" --> Q{"Tier satisfied?<br/>(single / all / quorum)"}
    Q -- "no" --> T
    Q -- "yes" --> NX{"More tiers?"}
    NX -- "yes" --> T
    NX -- "no" --> AP["Approved<br/>&rarr; post & pay"]

    N -- "Reject" --> RJ["Rejected + mandatory reason<br/>notify requester"]
    N -- "Request Info" --> RFI["Pause SLA clock<br/>ask requester / earlier approver"]
    RFI -- "answer received" --> N
    N -- "Delegate" --> DG["Reassign to delegate<br/>(both identities logged)"]
    DG --> N
    N -- "SLA timeout" --> ES["Reminder 50% &rarr; escalate 100%<br/>to approver's manager"]
    ES --> N

    ADM["Admin: add / remove approver<br/>(reason, guardrails, audit log)"] -. "live amendment" .-> T
```

Guardrails (enforced in code, §7.7–7.8): cannot alter an already-approved tier,
cannot remove the last path to completion, no self-approval / SoD violation,
every amendment is reason-mandatory and written to the immutable amendment log.

---

## 4. Budget control & utilization (§8)

```mermaid
flowchart LR
    PL["Planned amount"] --> AV["Available =<br/>Planned - Reserved - Utilized"]
    SUB["Submit / Final approval"] --> CHK{"Available >= amount?"}
    CHK -- "yes" --> RSV["Reserve at final approval<br/>(reservation ledger)"]
    CHK -- "no - warn mode" --> WARN["Flag over-budget<br/>(approvers see badge + bar)"]
    CHK -- "no - block mode" --> BLK["Block submission/approval"]
    WARN --> RSV
    RSV --> POST["Post journal entry"]
    POST --> CONS["Consume reservation<br/>&rarr; Utilized"]
    REJ["Reject / Cancel"] --> REL["Release reservation"]
```

> Checked at submit (early feedback) and re-checked at final approval with row
> locking (race-safe). The "tick in masters" (`budget_check_required`) decides
> whether the gate engages at all (§6 R6, §8.3).

---

## 5. Petty cash imprest cycle (§6.3)

```mermaid
flowchart TD
    F["Float created<br/>(limit + threshold + custodian)"] --> V["Disbursement vouchers<br/>(reduce balance)"]
    V --> BC{"Balance &lt; threshold?"}
    BC -- "no" --> V
    BC -- "yes" --> TU["Top-up request<br/>(auto-suggested by cron)"]
    TU --> AP["Approval matrix"]
    AP --> PR["Post Dr Petty Cash / Cr Bank<br/>(replenish to limit)"]
    PR --> F

    REC["Periodic reconciliation<br/>(cash count vs book)"] --> VAR{"Variance?"}
    VAR -- "yes" --> VP["Post over/short<br/>(stricter approval)"]
    VAR -- "no" --> OKR["Confirmed"]
```

---

## 6. Vendor electronic payout integration (UPI / cards / bank)

Pays vendors from approved documents (petty-cash vouchers with `payee_type =
vendor`, reimbursement batches, and optionally `account.move` vendor bills) by
calling an external **payouts API** (e.g. RazorpayX / Cashfree). This is an
**outbound disbursement** path — distinct from Odoo's inbound `payment.provider`
framework. Full design: [`vendor-payout-integration-research.md`](vendor-payout-integration-research.md).

```mermaid
flowchart TD
    A["Approved &amp; posted document"] --> REL{"Release payout<br/>(SoD: releaser &ne; approver)"}
    REL -- "hold" --> HLD["Stays posted<br/>(awaiting release)"]
    REL -- "release" --> KYC{"Beneficiary verified?<br/>(PAN / penny-drop / VPA check)"}
    KYC -- "no" --> BLK["Blocked:<br/>verify beneficiary first"]
    KYC -- "yes" --> FA["Ensure Contact + Fund Account<br/>(cached on partner; bank acct or UPI VPA)"]
    FA --> RAIL["Select rail<br/>UPI / IMPS / NEFT / RTGS / to-card"]
    RAIL --> PO["Create payout (spm.payout)<br/>stored idempotency key,<br/>queue_if_low_balance = true"]
    PO --> ST{"Provider response"}
    ST -- "low balance" --> Q["queued<br/>(alert finance to fund account)"]
    Q --> PROC
    ST -- "accepted" --> PROC["processing"]

    PROC --> WH[["Webhook (async)<br/>verify X-Razorpay-Signature,<br/>dedupe on event id"]]
    WH -- "payout.processed" --> OK["Store UTR + fees<br/>create &amp; reconcile account.payment<br/>&rarr; document = paid"]
    WH -- "payout.reversed / failed" --> FAIL["Reverse provisional entry<br/>notify + reopen for retry"]
    PROC -. "no webhook in SLA" .-> POLL["Status poll fallback<br/>(re-query by payout id)"]
    POLL --> WH
    FAIL --> REL
    OK --> DONE[("Dashboards &amp; payout register")]
```

**Payout entity (`spm.payout`) state machine:**

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> queued: low balance (queue_if_low_balance)
    draft --> processing: submitted to provider
    queued --> processing: account funded
    processing --> processed: payout.processed (signed webhook)
    processing --> reversed: payout.reversed
    processing --> failed: payout.failed
    processed --> [*]
    reversed --> draft: retry
    failed --> draft: retry
    draft --> cancelled: cancel before submit
    cancelled --> [*]
    reversed --> [*]
    failed --> [*]
```

Controls (enforced in code, see research doc §7–§8): payout only after
`approval_state = approved`; **maker–checker / SoD** between approver and
releaser; **idempotency key mandatory** on every create (and on webhook
handling — at-least-once delivery); **HMAC-verify** every webhook before acting;
secrets stored as restricted system parameters, never in source; INR-only guard;
optional **TDS** deduction (pay net) before disbursing; immutable audit of every
state change (who released, idempotency key, provider ids, UTR).

---

## Roles in the flow (§12.1)

| Role | Acts at |
|---|---|
| Employee / Custodian | Capture & submit (vouchers, expenses, advances, top-ups) |
| Approver | Approve / reject / RFI / delegate within the resolved matrix |
| Branch Finance | Branch-wide read, reimbursement prep, registers |
| Finance Manager | Post / pay, budget edit |
| Payout Releaser | Release approved electronic payouts (UPI/card/bank); must differ from the approver (SoD) — see Diagram 6 |
| Administrator | Masters, matrices, budgets, payout-provider credentials, live approval amendments (no posting — SoD) |
| Auditor | Read-everything via the amendment log & reports |
