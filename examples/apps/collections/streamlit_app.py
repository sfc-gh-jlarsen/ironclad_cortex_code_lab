"""Collections Cockpit - AR health for the collections team.

Read-only: every query is a fixed SELECT on "STREAMLIT-CORTEX-20261018".GOLD
(see queries.py). Results are cached once; filters and row selection work on
the cached frames in pandas, so widget interaction does not re-query.
"""

import os
from datetime import timedelta

import altair as alt
import pandas as pd
import streamlit as st

import queries

st.set_page_config(page_title="Collections Cockpit", page_icon=":material/payments:", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))

CACHE_TTL = 3600
DSO_WINDOW_DAYS = 90
CARD_HEIGHT = 440
CHART_HEIGHT = 300
AGING_31_60 = "2 31-60"

INVOICE_COLUMNS = [
    "ar_document_id", "billing_doc_id", "customer_id", "customer_name", "segment", "company_code",
    "invoice_date", "due_date", "open_amount_usd", "days_past_due", "aging_bucket",
    "is_in_active_dispute", "dispute_reason", "dispute_status", "was_delivered_late", "was_short_shipped",
]
INVOICE_COLUMN_CONFIG = {
    "ar_document_id": "AR document",
    "billing_doc_id": "Billing doc",
    "customer_id": "Customer ID",
    "customer_name": "Customer",
    "segment": "Segment",
    "company_code": "Company code",
    "invoice_date": st.column_config.DateColumn("Invoice date"),
    "due_date": st.column_config.DateColumn("Due date"),
    "open_amount_usd": st.column_config.NumberColumn("Open $", format="dollar"),
    "days_past_due": st.column_config.NumberColumn("Days past due"),
    "aging_bucket": "Aging bucket",
    "is_in_active_dispute": st.column_config.CheckboxColumn("In dispute"),
    "dispute_reason": "Dispute reason",
    "dispute_status": "Dispute status",
    "was_delivered_late": st.column_config.CheckboxColumn("Delivered late"),
    "was_short_shipped": st.column_config.CheckboxColumn("Short shipped"),
}


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_filter_options() -> pd.DataFrame:
    return conn.query(queries.FILTER_OPTIONS, ttl=0)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_open_items() -> pd.DataFrame:
    df = conn.query(queries.OPEN_ITEMS, ttl=0)
    df.columns = [c.lower() for c in df.columns]
    for col in ("invoice_date", "due_date", "as_of_date"):
        df[col] = pd.to_datetime(df[col]).dt.date
    for col in ("is_in_active_dispute", "was_delivered_late", "was_short_shipped"):
        df[col] = df[col].fillna(False).astype(bool)
    for col in ("open_amount", "open_amount_usd"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_daily_balance() -> pd.DataFrame:
    df = conn.query(queries.DAILY_BALANCE, ttl=0)
    df.columns = [c.lower() for c in df.columns]
    df["balance_date"] = pd.to_datetime(df["balance_date"]).dt.date
    # NUMBER columns arrive as Decimal (object dtype); Vega-Lite needs floats.
    for col in ("ar_usd", "overdue_usd", "sales_90d_usd"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_fulfillment() -> pd.DataFrame:
    df = conn.query(queries.FULFILLMENT, ttl=0)
    df.columns = [c.lower() for c in df.columns]
    for col in ("order_date", "requested_delivery_date", "first_goods_issue_date"):
        df[col] = pd.to_datetime(df[col]).dt.date
    for col in ("is_on_time", "is_in_full", "is_otif", "has_dispute"):
        df[col] = df[col].fillna(False).astype(bool)
    for col in ("delivery_delay_days", "fill_rate", "max_days_paid_late", "net_value_usd", "open_ar_usd"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df


def clear_cache() -> None:
    load_filter_options.clear()
    load_open_items.clear()
    load_daily_balance.clear()
    load_fulfillment.clear()


def apply_filters(df: pd.DataFrame, companies: list[str], segments: list[str]) -> pd.DataFrame:
    """Empty selection means 'all'."""
    mask = pd.Series(True, index=df.index)
    if companies:
        mask &= df["company_code"].isin(companies)
    if segments:
        mask &= df["segment"].isin(segments)
    return df[mask]


def dso(ar: float, sales_90d: float) -> float | None:
    return None if not sales_90d else ar / (sales_90d / DSO_WINDOW_DAYS)


def usd(x: float) -> str:
    return f"${x:,.0f}"


# ---------- Header (static UI first) ----------
st.title(":material/payments: Collections Cockpit")

tab_main, tab_disputes, tab_root = st.tabs(
    [":material/dashboard: Dashboard", ":material/gavel: Dispute report", ":material/troubleshoot: Root Cause"]
)

with st.spinner("Loading AR data from GOLD..."):
    options = load_filter_options()
    items_all = load_open_items()
    balance_all = load_daily_balance()
    fulfillment_all = load_fulfillment()

snapshot_date = items_all["as_of_date"].max()
min_bal, max_bal = balance_all["balance_date"].min(), balance_all["balance_date"].max()

with tab_main:
    f1, f2, f3, f4 = st.columns([2, 2, 2, 1], vertical_alignment="bottom")
    companies = f1.multiselect(
        "Company code", sorted(options["COMPANY_CODE"].unique()), placeholder="All company codes"
    )
    segments = f2.multiselect(
        "Segment", sorted(options["SEGMENT"].unique()), placeholder="All segments"
    )
    as_of = f3.date_input(
        "As of (DSO)", value=max_bal, min_value=min_bal, max_value=max_bal,
        help="Sets the DSO KPI date and the end of the 90-day DSO trend. "
             "Open-item tiles use the single aging snapshot.",
    )
    f4.button("Refresh data", icon=":material/refresh:", on_click=clear_cache, width="stretch")

    st.caption(
        f"Open items snapshot: **{snapshot_date}** · Daily balance history: {min_bal} – {max_bal} · "
        f"Filters: {', '.join(companies) or 'all company codes'} / {', '.join(segments) or 'all segments'}"
    )

    items = apply_filters(items_all, companies, segments)
    balance = apply_filters(balance_all, companies, segments)

    # ---------- KPI row ----------
    past_due = items[items["days_past_due"] > 0]
    open_ar = items["open_amount_usd"].sum()
    past_due_usd = past_due["open_amount_usd"].sum()
    disputed_usd = items.loc[items["is_in_active_dispute"], "open_amount_usd"].sum()

    daily = (
        balance.groupby("balance_date", as_index=False)[["ar_usd", "overdue_usd", "sales_90d_usd"]].sum()
        .sort_values("balance_date")
    )
    daily["dso_days"] = [dso(a, s) for a, s in zip(daily["ar_usd"], daily["sales_90d_usd"])]
    on_date = daily[daily["balance_date"] == as_of]
    dso_now = on_date["dso_days"].iloc[0] if not on_date.empty else None

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Open AR $", usd(open_ar), border=True, help=f"{len(items):,} open invoices")
    k2.metric(
        "Past due $", usd(past_due_usd), border=True,
        help=f"{len(past_due):,} invoices · {past_due_usd / open_ar:.1%} of open AR" if open_ar else None,
    )
    k3.metric(
        "DSO (days)", "—" if dso_now is None else f"{dso_now:,.1f}", border=True,
        help=f"SUM(AR) / (SUM(trailing 90d sales) / 90) on {as_of}",
    )
    k4.metric(
        "In dispute $", usd(disputed_usd), border=True,
        help=f"{int(items['is_in_active_dispute'].sum()):,} invoices in active dispute",
    )

    # ---------- Charts ----------
    # Fixed container + chart heights keep the two cards the same size
    # regardless of title wrapping or the caption under the DSO chart.
    c1, c2 = st.columns(2)

    with c1.container(border=True, height=CARD_HEIGHT):
        st.subheader("Open AR by aging bucket")
        buckets = (
            items.assign(status=items["is_in_active_dispute"].map({True: "In dispute", False: "Not disputed"}))
            .groupby(["aging_bucket", "status"], as_index=False)["open_amount_usd"].sum()
        )
        if buckets.empty:
            st.info("No open items for this filter.")
        else:
            st.altair_chart(
                alt.Chart(buckets).mark_bar().encode(
                    x=alt.X("aging_bucket:N", title="Aging bucket", sort="ascending", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("open_amount_usd:Q", title="Open AR (USD)", axis=alt.Axis(format="$,.0s")),
                    color=alt.Color("status:N", title=None,
                                    scale=alt.Scale(domain=["Not disputed", "In dispute"], range=["#29B5E8", "#FF9F36"])),
                    tooltip=["aging_bucket", "status", alt.Tooltip("open_amount_usd:Q", format="$,.0f", title="Open USD")],
                ),
                width="stretch",
                height=CHART_HEIGHT,
            )

    with c2.container(border=True, height=CARD_HEIGHT):
        st.subheader(f"DSO trend ({DSO_WINDOW_DAYS} days to {as_of})")
        trend = daily[
            (daily["balance_date"] > as_of - timedelta(days=DSO_WINDOW_DAYS)) & (daily["balance_date"] <= as_of)
        ].dropna(subset=["dso_days"]).assign(
            balance_date=lambda d: pd.to_datetime(d["balance_date"]),
            dso_days=lambda d: d["dso_days"].astype(float),
        )
        if trend.empty:
            st.info("No balance history for this filter.")
        else:
            st.altair_chart(
                alt.Chart(trend).mark_line(point=False, color="#29B5E8").encode(
                    x=alt.X("balance_date:T", title=None),
                    y=alt.Y("dso_days:Q", title="DSO (days)", scale=alt.Scale(zero=False)),
                    tooltip=[alt.Tooltip("balance_date:T", title="Date"),
                             alt.Tooltip("dso_days:Q", format=",.1f", title="DSO")],
                ),
                width="stretch",
                height=CHART_HEIGHT,
            )
        st.caption(f"History starts {min_bal}; DSO reads ~90 until the book matures.")

    # ---------- 31-60 day aging detail ----------
    aged_31_60 = (
        items[items["aging_bucket"] == AGING_31_60]
        .sort_values("open_amount_usd", ascending=False)
        [INVOICE_COLUMNS]
    )
    with st.expander(
        f"31-60 days aging · {len(aged_31_60):,} invoices · {usd(aged_31_60['open_amount_usd'].sum())} open AR",
        icon=":material/schedule:",
    ):
        if aged_31_60.empty:
            st.info("No invoices aged 31-60 days for this filter.")
        else:
            st.dataframe(aged_31_60, hide_index=True, width="stretch", column_config=INVOICE_COLUMN_CONFIG)

    # ---------- Top past-due customers + drill-down ----------
    with st.container(border=True):
        st.subheader("Top past-due customers")
        top = (
            past_due.assign(disputed=past_due["open_amount_usd"].where(past_due["is_in_active_dispute"], 0))
            .groupby(["customer_id", "customer_name", "segment"], as_index=False, dropna=False)
            .agg(past_due_invoices=("ar_document_id", "count"),
                 past_due_usd=("open_amount_usd", "sum"),
                 max_days_past_due=("days_past_due", "max"),
                 disputed_usd=("disputed", "sum"))
            .sort_values("past_due_usd", ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
        top["pct_disputed"] = (top["disputed_usd"] / top["past_due_usd"]).where(top["past_due_usd"] != 0) * 100

        if top.empty:
            st.info("No past-due customers for this filter.")
        else:
            # Key includes the filters so a stale row selection is dropped when they change.
            event = st.dataframe(
                top,
                key=f"top_{'|'.join(companies)}_{'|'.join(segments)}",
                on_select="rerun",
                selection_mode="single-row",
                hide_index=True,
                width="stretch",
                column_config={
                    "customer_id": "Customer ID",
                    "customer_name": "Customer",
                    "segment": "Segment",
                    "past_due_invoices": st.column_config.NumberColumn("Past-due invoices"),
                    "past_due_usd": st.column_config.NumberColumn("Past due $", format="dollar"),
                    "max_days_past_due": st.column_config.NumberColumn("Max days past due"),
                    "disputed_usd": st.column_config.NumberColumn("Disputed $", format="dollar"),
                    "pct_disputed": st.column_config.ProgressColumn("% disputed", format="%.1f%%", min_value=0, max_value=100),
                },
            )
            rows = event.selection.rows
            if not rows:
                st.caption("Select a customer row to see its open invoices.")
            else:
                cust = top.iloc[rows[0]]
                st.markdown(f"#### Open invoices · {cust['customer_name']} ({cust['customer_id']})")
                inv = (
                    items[items["customer_id"] == cust["customer_id"]]
                    .sort_values(["days_past_due", "open_amount_usd"], ascending=False)
                    [["ar_document_id", "billing_doc_id", "invoice_date", "due_date", "open_amount_usd",
                      "days_past_due", "aging_bucket", "is_in_active_dispute", "dispute_reason",
                      "dispute_status", "was_delivered_late", "was_short_shipped"]]
                )
                st.dataframe(
                    inv,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "ar_document_id": "AR document",
                        "billing_doc_id": "Billing doc",
                        "invoice_date": st.column_config.DateColumn("Invoice date"),
                        "due_date": st.column_config.DateColumn("Due date"),
                        "open_amount_usd": st.column_config.NumberColumn("Open $", format="dollar"),
                        "days_past_due": st.column_config.NumberColumn("Days past due"),
                        "aging_bucket": "Aging bucket",
                        "is_in_active_dispute": st.column_config.CheckboxColumn("In dispute"),
                        "dispute_reason": "Dispute reason",
                        "dispute_status": "Dispute status",
                        "was_delivered_late": st.column_config.CheckboxColumn("Delivered late"),
                        "was_short_shipped": st.column_config.CheckboxColumn("Short shipped"),
                    },
                )
                st.caption(
                    f"{len(inv):,} open invoices · {usd(inv['open_amount_usd'].sum())} open · "
                    f"{int((inv['days_past_due'] > 0).sum()):,} past due"
                )


# ---------- Dispute report tab ----------
# Uses the same company/segment filters set on the Dashboard tab.
with tab_disputes:
    disputes = items[items["is_in_active_dispute"]]
    st.caption(
        f"Open items snapshot: **{snapshot_date}** · "
        f"Filters (set on Dashboard tab): {', '.join(companies) or 'all company codes'} / "
        f"{', '.join(segments) or 'all segments'}"
    )
    if disputes.empty:
        st.info("No invoices in active dispute for this filter.")
    else:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("In dispute $", usd(disputed_usd), border=True)
        d2.metric("Disputed invoices", f"{len(disputes):,}", border=True)
        d3.metric("Customers in dispute", f"{disputes['customer_id'].nunique():,}", border=True)
        d4.metric("% of open AR", f"{disputed_usd / open_ar:.1%}" if open_ar else "—", border=True)

        r1, r2 = st.columns(2)
        for col, field, title in ((r1, "dispute_reason", "By dispute reason"), (r2, "aging_bucket", "By aging bucket")):
            with col.container(border=True, height=CARD_HEIGHT):
                st.subheader(title)
                agg = (
                    disputes.assign(**{field: disputes[field].fillna("(none)")})
                    .groupby(field, as_index=False)
                    .agg(invoices=("ar_document_id", "count"), disputed_usd=("open_amount_usd", "sum"))
                )
                st.altair_chart(
                    alt.Chart(agg).mark_bar(color="#FF9F36").encode(
                        x=alt.X("disputed_usd:Q", title="Disputed (USD)", axis=alt.Axis(format="$,.0s")),
                        y=alt.Y(f"{field}:N", title=None, sort="-x" if field == "dispute_reason" else "ascending"),
                        tooltip=[field, "invoices", alt.Tooltip("disputed_usd:Q", format="$,.0f", title="Disputed USD")],
                    ),
                    width="stretch",
                    height=CHART_HEIGHT,
                )

        with st.container(border=True):
            st.subheader("Disputed invoices")
            st.dataframe(
                disputes.sort_values("open_amount_usd", ascending=False)[INVOICE_COLUMNS],
                hide_index=True,
                width="stretch",
                column_config=INVOICE_COLUMN_CONFIG,
            )


# ---------- Root Cause tab ----------
# Links disputes and late payment back to fulfillment. Shipped order lines only
# (see queries.FULFILLMENT); uses the same company/segment filters as the Dashboard.
CAUSE_ORDER = ["OTIF", "Short only", "Late only", "Late + short"]
FULFILLMENT_REASONS = {"LATE_DELIVERY", "SHORT_SHIPMENT"}


def pct(n: float, d: float) -> str:
    return f"{n / d:.1%}" if d else "—"


with tab_root:
    lines = apply_filters(fulfillment_all, companies, segments)
    st.caption(
        f"Shipped order lines (Delivered / Backordered) · "
        f"Filters (set on Dashboard tab): {', '.join(companies) or 'all company codes'} / "
        f"{', '.join(segments) or 'all segments'}"
    )
    if lines.empty:
        st.info("No shipped order lines for this filter.")
    else:
        otif_lines = lines[lines["is_otif"]]
        miss_lines = lines[~lines["is_otif"]]
        disp = lines[lines["has_dispute"]]
        nodisp = lines[~lines["has_dispute"]]

        # ---------- KPI row ----------
        r1k, r2k, r3k, r4k = st.columns(4)
        r1k.metric("Dispute rate · OTIF lines", pct(otif_lines["has_dispute"].sum(), len(otif_lines)), border=True,
                   help=f"{len(otif_lines):,} OTIF lines")
        r2k.metric("Dispute rate · late/short lines", pct(miss_lines["has_dispute"].sum(), len(miss_lines)), border=True,
                   help=f"{len(miss_lines):,} late or short lines")
        r3k.metric("OTIF % · disputed vs not",
                   f"{pct(disp['is_otif'].sum(), len(disp))} vs {pct(nodisp['is_otif'].sum(), len(nodisp))}", border=True)
        paid_d, paid_n = disp["max_days_paid_late"].mean(), nodisp["max_days_paid_late"].mean()
        r4k.metric("Avg days paid late · disputed vs not",
                   f"{0 if pd.isna(paid_d) else paid_d:,.1f} vs {0 if pd.isna(paid_n) else paid_n:,.1f}", border=True,
                   help="Average of MAX_DAYS_PAID_LATE over paid lines")

        # ---------- Charts ----------
        c1, c2 = st.columns(2)
        with c1.container(border=True, height=CARD_HEIGHT):
            st.subheader("Dispute rate by fulfillment cause")
            by_cause = (
                lines.groupby("cause", as_index=False)
                .agg(lines=("sales_order_line_id", "count"), disputed=("has_dispute", "sum"))
            )
            by_cause["dispute_rate"] = by_cause["disputed"] / by_cause["lines"]
            st.altair_chart(
                alt.Chart(by_cause).mark_bar(color="#FF9F36").encode(
                    x=alt.X("cause:N", title=None, sort=CAUSE_ORDER, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("dispute_rate:Q", title="Dispute rate", axis=alt.Axis(format="%")),
                    tooltip=["cause", "lines", "disputed", alt.Tooltip("dispute_rate:Q", format=".1%", title="Dispute rate")],
                ),
                width="stretch",
                height=CHART_HEIGHT,
            )

        with c2.container(border=True, height=CARD_HEIGHT):
            st.subheader("OTIF: disputed vs not disputed")
            otif_cmp = (
                lines.assign(group=lines["has_dispute"].map({True: "Disputed", False: "Not disputed"}))
                .groupby("group")[["is_otif", "is_on_time", "is_in_full"]].mean()
                .rename(columns={"is_otif": "OTIF", "is_on_time": "On time", "is_in_full": "In full"})
                .reset_index()
                .melt(id_vars="group", var_name="measure", value_name="rate")
            )
            st.altair_chart(
                alt.Chart(otif_cmp).mark_bar().encode(
                    x=alt.X("measure:N", title=None, sort=["OTIF", "On time", "In full"], axis=alt.Axis(labelAngle=0)),
                    xOffset="group:N",
                    y=alt.Y("rate:Q", title="Share of lines", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
                    color=alt.Color("group:N", title=None,
                                    scale=alt.Scale(domain=["Not disputed", "Disputed"], range=["#29B5E8", "#FF9F36"])),
                    tooltip=["group", "measure", alt.Tooltip("rate:Q", format=".1%", title="Rate")],
                ),
                width="stretch",
                height=CHART_HEIGHT,
            )

        with st.container(border=True):
            st.subheader("Dispute reasons")
            if disp.empty:
                st.info("No disputed lines for this filter.")
            else:
                reasons = (
                    disp.assign(dispute_reason=disp["dispute_reason"].fillna("(none)"))
                    .groupby("dispute_reason", as_index=False)
                    .agg(lines=("sales_order_line_id", "count"), value_usd=("net_value_usd", "sum"),
                         days_paid_late=("max_days_paid_late", "mean"))
                )
                reasons["share"] = reasons["lines"] / reasons["lines"].sum()
                reasons["type"] = reasons["dispute_reason"].map(
                    lambda r: "Fulfillment (late/short)" if r in FULFILLMENT_REASONS else "Billing / quality"
                )
                st.altair_chart(
                    alt.Chart(reasons).mark_bar().encode(
                        x=alt.X("lines:Q", title="Disputed lines"),
                        y=alt.Y("dispute_reason:N", title=None, sort="-x"),
                        color=alt.Color("type:N", title=None,
                                        scale=alt.Scale(domain=["Fulfillment (late/short)", "Billing / quality"],
                                                        range=["#FF9F36", "#8A96A3"])),
                        tooltip=["dispute_reason", "lines", alt.Tooltip("share:Q", format=".1%", title="Share"),
                                 alt.Tooltip("value_usd:Q", format="$,.0f", title="Order value"),
                                 alt.Tooltip("days_paid_late:Q", format=",.1f", title="Avg days paid late")],
                    ),
                    width="stretch",
                    height=CHART_HEIGHT - 80,
                )
                st.caption("Reason codes come from the dispute record; the cause chart above uses the actual line flags.")

        # ---------- Customers + order-line drill-down ----------
        with st.container(border=True):
            st.subheader("Customers with late, short or disputed orders")
            cust_rc = (
                lines.assign(missed=~lines["is_otif"])
                .groupby(["customer_id", "customer_name", "segment"], as_index=False, dropna=False)
                .agg(shipped_lines=("sales_order_line_id", "count"),
                     late_short_lines=("missed", "sum"),
                     disputed_lines=("has_dispute", "sum"),
                     open_ar_usd=("open_ar_usd", "sum"),
                     max_days_paid_late=("max_days_paid_late", "max"))
            )
            cust_rc = (
                cust_rc[(cust_rc["late_short_lines"] > 0) | (cust_rc["disputed_lines"] > 0)]
                .sort_values(["disputed_lines", "late_short_lines"], ascending=False)
                .reset_index(drop=True)
            )
            cust_rc["dispute_rate"] = cust_rc["disputed_lines"] / cust_rc["shipped_lines"] * 100

            if cust_rc.empty:
                st.info("No customers with late, short or disputed orders for this filter.")
            else:
                # Key includes the filters so a stale row selection is dropped when they change.
                rc_event = st.dataframe(
                    cust_rc,
                    key=f"rc_{'|'.join(companies)}_{'|'.join(segments)}",
                    on_select="rerun",
                    selection_mode="single-row",
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "customer_id": "Customer ID",
                        "customer_name": "Customer",
                        "segment": "Segment",
                        "shipped_lines": st.column_config.NumberColumn("Shipped lines"),
                        "late_short_lines": st.column_config.NumberColumn("Late/short lines"),
                        "disputed_lines": st.column_config.NumberColumn("Disputed lines"),
                        "open_ar_usd": st.column_config.NumberColumn("Open AR $", format="dollar"),
                        "max_days_paid_late": st.column_config.NumberColumn("Max days paid late"),
                        "dispute_rate": st.column_config.ProgressColumn("Dispute rate", format="%.1f%%", min_value=0, max_value=100),
                    },
                )
                rc_rows = rc_event.selection.rows
                if not rc_rows:
                    st.caption("Select a customer row to see their late, short or disputed order lines.")
                else:
                    cust = cust_rc.iloc[rc_rows[0]]
                    st.markdown(f"#### Late / short / disputed orders · {cust['customer_name']} ({cust['customer_id']})")
                    orders = (
                        lines[(lines["customer_id"] == cust["customer_id"]) & (~lines["is_otif"] | lines["has_dispute"])]
                        .sort_values(["has_dispute", "delivery_delay_days"], ascending=False)
                        [["sales_order_id", "sales_order_line_id", "order_date", "requested_delivery_date",
                          "first_goods_issue_date", "delivery_delay_days", "fill_rate", "cause", "is_on_time",
                          "is_in_full", "has_dispute", "dispute_reason", "max_days_paid_late", "open_ar_usd"]]
                    )
                    st.dataframe(
                        orders,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "sales_order_id": "Sales order",
                            "sales_order_line_id": "Order line",
                            "order_date": st.column_config.DateColumn("Order date"),
                            "requested_delivery_date": st.column_config.DateColumn("Requested"),
                            "first_goods_issue_date": st.column_config.DateColumn("Goods issue"),
                            "delivery_delay_days": st.column_config.NumberColumn("Delay (days)"),
                            "fill_rate": st.column_config.NumberColumn("Fill rate", format="percent"),
                            "cause": "Cause",
                            "is_on_time": st.column_config.CheckboxColumn("On time"),
                            "is_in_full": st.column_config.CheckboxColumn("In full"),
                            "has_dispute": st.column_config.CheckboxColumn("Disputed"),
                            "dispute_reason": "Dispute reason",
                            "max_days_paid_late": st.column_config.NumberColumn("Days paid late"),
                            "open_ar_usd": st.column_config.NumberColumn("Open AR $", format="dollar"),
                        },
                    )
                    st.caption(
                        f"{len(orders):,} lines · {int(orders['has_dispute'].sum()):,} disputed · "
                        f"{int((~orders['is_on_time']).sum()):,} late · {int((~orders['is_in_full']).sum()):,} short"
                    )
