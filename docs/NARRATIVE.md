# Multi-Cloud FinOps on Google Cloud
## A presenter's narrative for Con Edison

*Architecture → Features → Benefits. Twenty-three slides, about fifty minutes, and one
argument carried the whole way through.*

Every figure in this document is computed by `tools/build_deck.py` from the same
engines the product runs on. They describe a **synthetic 24-month utility
estate** shipped with the platform — not Con Edison's bill. Say that out loud on
slide 13, before anyone asks.

---

## The through-line

> **You cannot manage what you cannot compare. Four clouds speak four languages,
> so before you can save a dollar you have to agree what a dollar is.**

Everything else — the warehouse, the agents, the levers — is downstream of that
one sentence. If the room remembers nothing else, it should remember that the
platform's first act is translation, and that the translation is a published
open standard rather than an Infosys invention.

---

## Act I — Architecture
### The situation (slides 1–2)

Con Edison runs four clouds. AWS carries the largest share, Azure the operational
systems, Google Cloud the analytics estate, and OCI the workloads Oracle's
licensing anchors there — the customer information system and ERP.

Four clouds means four billing schemas. AWS calls it a `lineItem`, Azure a
`meter`, Google a `sku`, Oracle a `cost report`. A "reservation" in one is a
"savings plan" in another and a "committed use discount" in a third. None of them
agree on what an amortised dollar is.

The consequence is not that reporting is hard. It is that **reporting is
opinionated**. Somebody, somewhere, wrote a spreadsheet formula that decides
what your Effective Savings Rate is, and nobody has read it in two years.

> *Talk track:* "Ask your team today what your commitment coverage is across all
> four clouds. You'll get an answer. Then ask two people separately."

### The idea (slide 3)

**FOCUS 1.2** — the FinOps Foundation's open specification for cloud billing
data. AWS, Azure, Google and Oracle all emit it natively today. Every source this
platform reads is normalised to FOCUS *on ingest*, and **nothing downstream of a
connector has ever seen a vendor-specific field.**

This is the architectural bet, and it is worth naming as a bet. It buys three
things:

1. **A single definition of every number.** Effective Savings Rate is computed
   once, in one function, from `ListCost` and `EffectiveCost`. There is no second
   opinion.
2. **Vendor neutrality by construction, not by adapter.** If Con Edison procures
   Cloudability or Apptio tomorrow, that is one new connector class and one
   registry line — not a rebuild. Eighteen connectors ship today.
3. **Survivability.** FOCUS deliberately leaves `ProviderName` a free string, so
   the specification outlives the clouds its authors knew about. The platform
   inherits that: a fifth cloud loads, allocates and forecasts on day one.

> *Talk track:* "We did not invent a schema and ask you to trust it. We adopted
> the one the FinOps Foundation published and the four hyperscalers already
> emit."

### What FOCUS actually is (slide 4)

Slide 3 tells the room *who* emits FOCUS and *why* that means no lock-in. It is a
procurement argument, and it leaves nobody understanding the thing itself. Slide
4 shows the translation happening.

The same charge — one committed compute hour — written four ways:

| | the commitment | what you actually pay | the undiscounted price |
|---|---|---|---|
| **AWS** | Savings Plan · Reserved Instance | amortized cost | public on-demand cost |
| **Azure** | Reservation · Savings Plan | amortized cost | pay-as-you-go price |
| **GCP** | Committed Use Discount | cost + credits | list price |
| **OCI** | Annual Universal Credits | amortized cost | unit price × quantity |

Three columns come out the other side, and each sits directly beneath the vendor
column it replaces: **`CommitmentDiscountStatus`** (`Used` | `Unused`),
**`EffectiveCost`**, **`ListCost`**.

Then the payoff, which is the only formula in the deck:

> **Effective Savings Rate = (ListCost − EffectiveCost) / ListCost**
>
> Defined once, in one function, for all four clouds.

And one more thing the room should hear: `CommitmentDiscountStatus = 'Unused'` is
**waste the bill states outright** — $346K on this estate. Not a model, not an
estimate. The invoice says you bought capacity and used none of it.

> *Talk track:* "Every one of those four rows is a different team, in a different
> tool, using a different word for the same dollar. Nothing downstream of the
> connector in this platform has ever seen any of them."

If an architect pushes on the vendor column names: the slide is deliberately
concept-level. Google is mid-schema-change on its detailed export as of July
2026, and one stale column string in front of their architects costs more
credibility than the specificity buys. The exact mappings are in the connector
source, and we will walk them through it.

### The architecture (slides 5–8)

Four diagrams, deliberately in this order. Each is written for two readers at once:
the bold line is the story, the grey line beneath it is the engineering name. Each ships as **editable SVG** in
`docs/diagrams/` — the labels are real text, so your architects can open them in
Figma and retype a box.

**Slide 5 — High level design.** Six layers, read downward, and each one carries
a grey line saying in plain English what it is *for* — where the bills come from,
how we are allowed to read them, and so on. Read those five sentences and you have
the system. The shape of the argument: everything narrows to one FOCUS table, and
everything above that table is provider-blind.

**Slide 6 — End user view.** Five personas, nine pages. Leadership does not want
the same page as an engineer, and neither of them should have to construct a
query to get an answer. One scope — cloud, application, business unit,
environment, period — governs every panel on a page, so no two charts on the same
screen can disagree.

**Slide 7 — Low level design.** Not the plumbing. Two stories, side by side.

The blue row is someone opening a dashboard: they pick what they are looking at,
the app turns that into one carefully-checked question, the warehouse reads only
that slice, the finance maths runs, and they get a chart with the table behind
it.

The green row is someone asking the Copilot: they ask in plain English, a cheap
model picks the right specialist, that specialist may only call eleven approved
questions and **cannot write a database query**, those questions run the same
maths, and the answer names the tool each figure came from.

Then point at the dashed line joining the two rows. **Step 4 is literally the
same function.** That is the whole trust argument in one line: the Copilot cannot
quote a number the dashboard disagrees with, because it *is* the same number.

Underneath sit three safety rules, and two of them are about *failure*:

- **It cannot invent a column.** A filter name is checked against an approved
  list before it ever reaches the database. Unchecked strings in an identifier
  position are injection.
- **It cannot forget the dates.** A query with no date range is refused, not run.
  That is a $5 bill instead of a $500 one.
- **The AI cannot do arithmetic.** It can only ask for numbers that already
  exist.

Each step carries the engineering name in grey beneath the plain sentence, so an
architect gets the module map without the executive having to sit through it. The
full module-level diagram ships as `docs/diagrams/lld_technical.svg` for anyone
who wants it.

> *Talk track:* "Vendors boast about what their system does. Almost nobody boasts
> about what it refuses to do." 

**Slide 8 — Connecting the clouds.** The question every CIO asks: *how many
credentials?* Answer: **one per payer, not one per account.** One AWS
organisation, one Azure billing account, one GCP billing account, one OCI
tenancy. A second credential means a second *payer* — which a regulated utility
does have, because regulated and unregulated entities cannot share a bill.

> *Be straight about OCI here.* AWS and Azure federate through Workload Identity —
> nothing to store, nothing to rotate. **OCI has no such path.** Its SDK signs
> every request with an RSA key, so exactly one key exists, it lives in Secret
> Manager, and somebody has to rotate it. And its cost reports sit in a bucket
> Oracle owns, not Con Edison's — tenancy admin is not enough; you must grant an
> `endorse` policy into Oracle's reporting tenancy.
>
> Saying this unprompted buys more credibility than any slide in the deck.

### Why Google Cloud, and why a rebuild (slides 9–10)

There is a Streamlit reference implementation of this platform. It works. The
rebuild was **never about the user interface.**

It was pandas. The demo estate is 63,000 rows at roughly 650 bytes each. Con
Edison at ~500,000 line-items a month across 24 months is about **8 GB in a
single process**, and Streamlit loads the whole frame on every session. At 2M
line-items a month it is 31 GB. There is no version of that which works.

BigQuery pushes the aggregation into SQL. A query for "last month" reads one
month's partition.

What *doesn't* change is the part that matters: **the same ~9,100 lines** of
FOCUS normalisation, KPI formulae, forecasting, allocation and the optimization
detectors run in both. They were written without a single Streamlit import, so
they lifted into an installable package untouched. The Streamlit app stays as the
reference implementation and the demo surface — and a bug fixed in one is fixed
in both.

---

## Act II — Features
### The agents (slides 11–12)

A coordinator on `gemini-3.1-flash-lite` routes; four specialists on
`gemini-3.5-flash` reason. **Analyst** (what was spent, where), **Forecaster**
(where it is heading), **Optimizer** (what to do about it), **Governor**
(tagging, chargeback readiness).

Two design decisions to defend, because they are the ones that make this
trustworthy rather than merely impressive:

**The specialists are tools, not sub-agents.** Handing control to a sub-agent
means the last specialist to speak writes the final answer, in its own register.
A FinOps question spans domains; the answer must arrive in one voice, pitched at
one persona. So the coordinator holds the floor and calls specialists as tools.

**The agents are never given SQL.** ADK ships a BigQuery `execute_sql` toolset.
We deliberately do not use it. Hand a language model a SQL prompt and it will
invent its own Effective Savings Rate — drop the on-demand denominator, count
Purchase rows — and the number it returns will be plausible, wrong, and
uncaught. Instead the model gets **eleven typed tools** that call the same engine
functions the REST endpoints call. **It cannot compute. It can only ask.**

The consequence is the sentence to say aloud: *the Copilot cannot quote a number
the dashboard disagrees with, because they are the same number.*

And the cost is measured, not guessed: **$0.026 per question, about $116/month**
at 4,400 questions.

> *If asked "why not GPT-5?":* On this workload Gemini is roughly 10% *more*
> expensive per question than the gpt-5 setup. We chose it for the Vertex
> identity story — Application Default Credentials on the service account, so
> **no model API key exists anywhere to leak**. That is worth $10 a month.

### What it tells you (slides 13–16)

On the synthetic estate:

| | |
|---|---|
| 24-month spend | **$32.65M** — AWS $15.71M, Azure $7.76M, GCP $4.67M, OCI $4.50M |
| Effective Savings Rate | **21.6%** |
| Commitment coverage / utilisation | **42.0% / 95.6%** |
| Cost of waste | **$2.52M**, 7.7% of spend |
| Allocation coverage | **82.6%** — $5.69M with no owner |
| 24-month forecast | **$48.85M** |

Four features, and what each one is *for*:

**The executive view.** Coverage at 42% with utilisation at 95.6% is the whole
FinOps conversation in two numbers. You are using well what little you have
committed. You have not committed enough.

**The forecast, and the cliff.** The trend model says $48.85M over 24 months. The
platform also overlays **commitment expiry**: in **July 2026** a term ends and the
rate snaps back to on-demand. Actual exposure is **$53.79M** — a **$4.94M**
difference a trend line walks straight through without seeing. Forecast accuracy
is a 4.74% WAPE, which the FinOps Framework grades best-in-class.

> *Talk track:* "Every forecasting tool you have been shown draws this line. Ask
> the next vendor what happens to it in July 2026."

**Optimization.** **$5.52M identified across 36 opportunities** — 34% of annual
run-rate — and if fully taken, Effective Savings Rate moves from 21.6% to 40.2%.
Fifty-nine levers, detected from the bill itself. The top five:

| Lever | Cloud | Annual | Effort / Risk |
|---|---|---|---|
| AWS Compute Savings Plan | AWS | $1.19M | Low / Low |
| Schedule / park non-prod | all four | $787K | Low / Low |
| Azure Reservations | Azure | $745K | Low / Medium |
| GCP Flexible CUD | GCP | $462K | Low / Low |
| OCI Annual Universal Credits | OCI | $340K | Low / Low |

Note that the top item on every cloud is a *rate* lever, and every one of them is
low effort. **The first million dollars requires no engineer to change any code.**

Two OCI levers are worth calling out because they are genuinely Oracle-specific
and no generic tool models them: **BYOL to OCI** — the actual economic argument
for running Oracle workloads on Oracle's cloud — and **Oracle Support Rewards**,
which accrues against the Oracle *support* invoice rather than the cloud bill. We
surface it because the money is real. We never net it off cloud spend, because it
is a different budget line and often a different owner.

**Anomaly detection.** 23 anomalies, not 300. A point must be *both*
statistically odd *and* financially material — STL decomposition, a modified
z-score on the residual, and a dollar floor. The largest: **Analytics, 20 May
2026, 489% above expected.**

> *This is the credibility slide.* An earlier build flagged 347 anomalies and
> graded 318 of them "good", because it took the statistical test from one method
> and the severity from another and never reconciled them. In a low-variance
> series a 5% wobble scores a z of 6. We found it, and it is why the number on
> this slide is 23.

---

## Act III — Benefits
### What it is worth (slides 17–19)

Order these by who in the room cares.

**For the CFO — a number you can defend.** $5.52M identified, $4.94M of forecast
exposure made visible, and every figure traceable to one function in one file.
When the auditor asks how Effective Savings Rate was computed, there is exactly
one answer.

**For the CIO — no new lock-in.** The contract is an open specification, not our
schema. Eighteen connectors, and a procured FinOps tool is one class. Read-only
throughout. Federated identity for AWS and Azure; one signing key for OCI, in
Secret Manager. Cost-bounded by construction: a runaway query fails rather than
bills.

**For the FinOps team — the argument ends.** One scope, one definition, a table
view behind every chart, and a CSV behind every table. No number is reachable
only through a tooltip.

**For the business units — a bill they recognise.** 82.6% allocation coverage
today, and the platform names the $5.69M that has no owner rather than silently
spreading it. Chargeback where the tags support it; showback on the remainder.

**Run cost.** The platform costs on the order of **$116/month in model
inference**, plus Cloud Run that scales to zero and a BigQuery bill bounded by a
partition filter. Against $16M of annual cloud spend.

### Effort and plan (slides 20–21)

Two slides the client will study harder than any architecture diagram.

**Slide 20 — Effort estimation.** 26.5 person-months of base effort, **70%
offshore**, plus 15% contingency held by the delivery lead: **30.5 in total**.
Stated in person-months, never in dollars. Say why, because you will be asked: a
day rate we invented on a slide would be the least defensible number in the pack.
These multiply by whatever rate card Con Edison actually has.

The shape *is* the argument. Month 1 is five FTE and buys almost no code — it
buys read credentials on four payers and four FOCUS exports. In a regulated
utility that is the long pole, not the build. The team peaks at 8.25 FTE in month
3 and no month exceeds it, so nobody works a weekend to hit this plan.

Onshore is deliberately the client-facing and judgement work: the architect who
sets the tag taxonomy, the analyst who reconciles our numbers against theirs, the
security lead. Offshore is the build and the test.

> *If they push for three months:* the compressible part is not engineering, it
> is access. Offer to start the credential and export work before the contract
> closes. That is the only thing that genuinely pulls the date in.

**Slide 21 — Delivery plan.** Twenty-six activities, sixteen weeks, four gates.
Blue bars are onshore, teal offshore. Walk the *gates*, not the bars:

| Gate | Week | What must be true | Owner |
|---|---|---|---|
| **G1** | 4 | Access granted, exports enabled | **Con Edison** |
| **G2** | 9 | Real FOCUS data in the warehouse | Joint |
| **G3** | 14 | Dashboards and Copilot on real data | Infosys |
| **G4** | 16 | Cutover and handover | Joint |

G2 is the first moment any number in this deck stops being synthetic.

Three sequencing decisions worth defending. The frontend does not start until the
API contract is stable, or it gets built twice. The agents do not start until the
engines and real data exist, because an agent with nothing true to say is a demo,
not a product. And KPI parity against Con Edison's own reporting runs for a full
month — if our Effective Savings Rate disagrees with theirs, we need time to find
out who is right.

Note what sits on the *client's* critical path: the credentials, the exports, the
OCI endorse policy, the tag taxonomy, and UAT. Say that plainly. Most slippage in
an engagement like this is not ours.

A working `.xlsx` accompanies these slides. Every total is a live formula, the
day-rate cells ship empty, and typing a rate populates the cost columns.

---

### What this does not claim (slide 22)

Spend real time on this slide. It is the one that wins the room.

- **The numbers are synthetic.** They describe a 24-month utility estate we
  generated. Nothing here is Con Edison's bill. Wave 1 replaces them.
- **AWS Cost Explorer does not expose list price.** On that ingest path
  `ListCost` is set equal to `BilledCost`, so Effective Savings Rate comes out
  *understated*. Use a FOCUS Data Export instead. We would rather tell you the
  number is conservative than have you discover it.
- **Sign-in is target state.** IAP is not in the Terraform, and the API ships
  today with no auth. It goes in before any real bill does.
- **The OCI connector has never run against a live tenancy.** Its shape is
  tested; its network path is not.
- **A cloud bill cannot contain a budget or a business driver.** Those come from
  Con Edison. `budgets()` and `drivers()` return empty frames on purpose rather
  than inventing plausible ones.

> *Talk track:* "Everything on the previous slides is real code producing real
> numbers from a fake estate. Here is precisely what we have not proven."

### The ask (slide 23)

1. **Read access to one payer per cloud.** Not per account. Four credentials.
2. **Enable a FOCUS export where one exists** — AWS Data Exports, Azure
   `FocusCost`, the GCP billing export, OCI's FOCUS reports. This is what makes
   the savings-rate number correct rather than conservative.
3. **A GCP project**, Workload Identity Federation to AWS and Azure, and an
   `endorse` policy into Oracle's reporting tenancy.
4. **Two names**: who owns the tag taxonomy, and who owns the commitment
   portfolio. The platform will tell them what to do. It cannot tell them it is
   their job.

Wave 1 is the executive view and allocation on real data. The forecast needs
history, and the optimizer needs the forecast.

---

## The closing line

> "We are not asking you to trust our schema, our savings estimate, or our
> agents. We are asking you to point four read-only credentials at a warehouse
> whose every number is computed once, in code you can read, against a standard
> you did not have to take our word for."

---

### Appendix — questions to expect

**"How is this different from Cloudability / Apptio / CloudHealth?"**
It isn't a competitor. Those are sources. If you procure one, it becomes a
connector, and the FOCUS frame downstream is identical. What this adds is the
single definition, the commitment-cliff overlay, and the agent layer that cannot
contradict the dashboard.

**"Why should I trust an LLM with my cost data?"**
You aren't. The model cannot query the warehouse. It calls eleven typed functions
that return the same numbers the REST API returns, and it names the tool behind
every figure it quotes. If it cannot get a number from a tool, it says what data
would be needed.

**"What happens when we add a fifth cloud?"**
It loads, allocates, forecasts and gets anomaly detection on day one, because
those are provider-agnostic. What it does not get is a rate lever, because we
will not invent a commitment instrument we cannot name. That is a deliberate
refusal, and there is a test that enforces it.

**"How long until we see a number?"**
Wave 1 is the executive view on real data. The constraint is not engineering — it
is how long it takes to get read access to four payers and enable four exports.
