# Explore → Plan → Code → Commit: Demo Prompt Vignettes

Data: Ironclad Tire & Rubber Co. (fictional) in `"STREAMLIT-CORTEX-20261018"` (RAW / BRONZE / SILVER / GOLD).
Each vignette has **Explore** prompts (describe the problem, find things) and one **Plan** prompt
(Target · Material · Guardrails · Success). Code and Commit are left to you.

> Tip: The Explore prompts deliberately avoid table names, so the agent has to discover them.
> Run them in order. Each one builds on what the previous one found.

---

## Vignette 1: "Who owes us money?" (net-new Streamlit app)

**Story:** The CFO says DSO is creeping up and wants a collections cockpit. We have nothing today.

### Explore
```
I'm working with our tire manufacturing data in the STREAMLIT-CORTEX-20261018 database.
Finance says our receivables are getting worse. Find where open customer invoices and
their aging live, and tell me which layer (bronze/silver/gold) I should be building on.
```
```
Show me how much is open by aging bucket and which 10 customers have the most past-due
balance. Is any of it tied up in disputes? Save the SQL you used to explore/ar_exploration.sql.
```
```
How is DSO calculated in this data and what's the trend over the last 90 days?
Is it the same across OEM, dealer, and fleet customers?
```

### Plan
```
I want to plan a new Streamlit app. Don't write code yet. Give me a plan I can approve.

TARGET
A "Collections Cockpit" Streamlit app for the AR team in a new folder apps/collections/.

MATERIAL
- Use explore/ar_exploration.sql from my exploration as the starting point for queries.
- Wireframe:
  +------------------------------------------------------------+
  | [Company code v] [Segment v]                   As of: date |
  +-------------+-------------+-------------+------------------+
  | Open AR $   | Past due $  | DSO (days)  | In dispute $     |
  +-------------+-------------+-------------+------------------+
  | Aging bucket bar chart     | DSO trend line (90 days)      |
  +----------------------------+-------------------------------+
  | Top past-due customers table (click a row -> invoices)     |
  +------------------------------------------------------------+

GUARDRAILS
- Read only from the GOLD schema. No writes, no DDL.
- No hard-coded credentials; use the Streamlit Snowflake connection.
- Cache queries; don't re-query on every widget interaction.

SUCCESS
- KPI totals match the gold tables exactly (show me a reconciliation query).
- Filters change every tile.
- Selecting a customer shows its open invoices with days past due and dispute reason.
```

---

## Vignette 2: "Our supplier is slipping" (rebuild an existing dashboard)

**Story:** Procurement has a supplier scorecard in Tableau that nobody trusts. They suspect one carbon black supplier.

### Explore
```
Procurement thinks one of our carbon black suppliers is getting worse at on-time delivery.
Find the data that would prove or disprove that, and tell me who the supplier is.
```
```
For that supplier, show monthly on-time rate, quality reject rate, and average delay vs.
the other carbon black suppliers. Which plants are most exposed to them?
```
```
Are there any materials where we only have one supplier? What's our risk score data
look like, and where does it come from?
```

### Plan
```
Plan a Streamlit supplier scorecard that replaces our Tableau version. Plan only, no code yet.

TARGET
apps/supplier_scorecard/: a supplier performance app procurement can use in the
monthly business review.

MATERIAL
- Screenshot of the current Tableau dashboard: [attach supplier_scorecard_tableau.png]
  (My markup: circled the OTD chart "keep this", crossed out the pie chart "remove",
  note in margin "add quality rejects + risk score").
- Optionally the workbook: [attach Supplier_Scorecard.twbx]

GUARDRAILS
- GOLD schema only, read-only.
- No credentials in code.
- On-time rate must count overdue-but-unreceived PO lines as late.

SUCCESS
- One page: supplier picker, monthly OTD / OTIF / reject rate trends, peer comparison
  within the same material category, single-source materials flagged.
- The declining supplier is obvious within 10 seconds of opening the app.
- Matches the scorecard numbers I saw during exploration.
```

---

## Vignette 3: "Transfer instead of buy" (net-new decision app)

**Story:** Plants place POs while a sister plant is sitting on surplus. Operations wants a daily "move it, don't buy it" list.

### Explore
```
I want to know if our plants are buying raw materials they could have transferred from
another plant. What data do we have about inventory levels, reorder points, plant-to-plant
transfer lanes, and freight cost?
```
```
Which plant/material combinations were below reorder point most often in the last 90 days,
and was there another plant with surplus at the same time? Start with carbon black.
```
```
How much purchase spend could have been avoided if we'd transferred instead of ordering?
Break it down by plant and material and tell me how the recommendation is calculated.
```

### Plan
```
Plan a Streamlit app for daily transfer-vs-reorder decisions. Plan only.

TARGET
apps/transfer_planner/: an operations app that lists today's below-reorder-point items with
a recommended action (transfer vs. buy) and shows the money we left on the table historically.

MATERIAL
- My exploration notes and SQL: explore/transfer_analysis.sql
- Hand-drawn wireframe: [attach transfer_planner_sketch.jpg]
  Top: "Today's actions" table (plant, material, need, best donor plant, transit days,
       freight $, supplier lead time, purchase $, recommendation)
  Bottom left: map or bar chart of plants by shortage count
  Bottom right: "Missed transfers": cumulative $ where we bought instead of moved

GUARDRAILS
- Read only. The app recommends; it does not create POs or transfers.
- No hard-coded credentials or warehouse names.
- Keep recommendation logic in SQL/dbt, not duplicated in Python.

SUCCESS
- Today's list matches the latest day in the gold transfer-vs-reorder table.
- The Valle Alto (P400) carbon black shortage shows up, with a sister plant (e.g. Cedar Bluff P200) as donor.
- A planner can filter by plant and export the list to CSV.
```

---

## Vignette 4: "Add the why" (enhance an existing app)

**Story:** After Vignette 1, collections asks: *why* are these customers paying late? Is it us?

### Explore
```
Look at apps/collections/streamlit_app.py and explain how it's structured: pages,
queries, caching. Then tell me what data we have that connects late deliveries or
short shipments to disputes and late payments.
```
```
Do orders that were delivered late or short-shipped get disputed more often? Show me
OTIF rate for disputed vs non-disputed orders and the top dispute reasons.
```

### Plan
```
Plan an enhancement to the existing Collections Cockpit. Plan only.

TARGET
Add a "Root Cause" tab to apps/collections/streamlit_app.py that links AR problems back to
fulfillment problems (late delivery, short shipment, pricing disputes).

MATERIAL
- Existing app: apps/collections/streamlit_app.py
- Marked-up screenshot of the current app: [attach collections_markup.png]
  (Red box under the top-customers table: "new tab here". Arrow: "click customer ->
  show their late/short orders".)

GUARDRAILS
- Don't break or restyle the existing tabs; reuse the existing connection and cache helpers.
- Read only from GOLD.
- No new credentials or secrets.

SUCCESS
- New tab shows dispute rate by cause, OTIF disputed vs. not, and dispute reasons.
- Clicking a customer shows their orders with delivery delay and dispute status.
- Existing tabs return identical numbers before and after the change.
```

---

## Bonus Explore prompts (quick crowd-pleasers)

```
What's in the STREAMLIT-CORTEX-20261018 database? Give me a one-paragraph tour of each schema.
```
```
Trace the lineage of on-time delivery rate from the gold supplier scorecard back to the raw SAP tables.
```
```
The supplier quality data comes in as JSON. Show me what a payload looks like and how it gets flattened.
```
