"""Supplier Scorecard - monthly supplier performance for the procurement business review.

Replaces the Tableau scorecard. Read-only: every query is a fixed SELECT on
"STREAMLIT-CORTEX-20261018".GOLD (see queries.py). Results are cached once; the
supplier and plant filters work on the cached frames in pandas.

Rate definitions (recomputed from line counts after filtering, never averaged):
  OTD %    = on_time_lines / (received_lines + overdue_open_lines)   overdue-unreceived = late
  OTIF %   = otif_lines    / (received_lines + overdue_open_lines)
  Reject % = rejected_qty  / received_qty
  Delay    = total_delay_days / received_lines
"""

import os

import altair as alt
import pandas as pd
import streamlit as st

import queries

st.set_page_config(page_title="Supplier Scorecard", page_icon=":material/local_shipping:", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))

CACHE_TTL = 3600
RECENT_MONTHS = 2          # watchlist compares the latest 2 months with all earlier months
MIN_LINES = 20             # minimum OTD-base lines in each period to be ranked
RED_DROP_PTS = -15.0
AMBER_DROP_PTS = -5.0
CHART_HEIGHT = 230
SUPPLIER_COLOR = "#E5484D"
PEER_COLOR = "#8B8D98"

COUNT_COLS = [
    "po_lines", "spend_usd", "received_lines", "on_time_lines", "otif_lines",
    "overdue_open_lines", "total_delay_days", "received_qty", "rejected_qty",
]


def _numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    # NUMBER columns arrive as Decimal (object dtype); Vega-Lite and pandas math need floats.
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_scorecard() -> pd.DataFrame:
    df = conn.query(queries.SCORECARD, ttl=0)
    df.columns = [c.lower() for c in df.columns]
    df["month_start_date"] = pd.to_datetime(df["month_start_date"])
    return _numeric(df, COUNT_COLS + ["avg_risk_score", "avg_delivery_risk_score"])


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_suppliers() -> pd.DataFrame:
    df = conn.query(queries.SUPPLIERS, ttl=0)
    df.columns = [c.lower() for c in df.columns]
    return _numeric(df, ["overall_risk_score", "financial_score", "geopolitical_score",
                         "esg_score", "delivery_score", "risk_alert_count"])


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def load_single_source() -> pd.DataFrame:
    df = conn.query(queries.SINGLE_SOURCE, ttl=0)
    df.columns = [c.lower() for c in df.columns]
    df["is_critical_material"] = df["is_critical_material"].fillna(False).astype(bool)
    return _numeric(df, ["plants", "po_value_usd"])


def clear_cache() -> None:
    load_scorecard.clear()
    load_suppliers.clear()
    load_single_source.clear()


def div(n: float, d: float) -> float | None:
    return None if not d else n / d


def add_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Add rate columns to a frame of summed line counts."""
    base = df["received_lines"] + df["overdue_open_lines"]
    df = df.copy()
    df["otd_pct"] = 100 * df["on_time_lines"] / base.where(base > 0)
    df["otif_pct"] = 100 * df["otif_lines"] / base.where(base > 0)
    df["reject_pct"] = 100 * df["rejected_qty"] / df["received_qty"].where(df["received_qty"] > 0)
    df["avg_delay_days"] = df["total_delay_days"] / df["received_lines"].where(df["received_lines"] > 0)
    df["otd_base"] = base
    return df


def monthly(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    return add_rates(df.groupby(keys, as_index=False)[COUNT_COLS].sum())


def build_watchlist(sc: pd.DataFrame, months: list[pd.Timestamp]) -> pd.DataFrame:
    """OTD in the latest RECENT_MONTHS vs earlier months, per supplier.

    Ranked by 'extra late lines' = OTD drop x recent volume, so a small supplier
    with a handful of lines can't outrank a high-volume one that is clearly slipping.
    """
    recent_start = months[-RECENT_MONTHS]
    sc = sc.assign(period=sc["month_start_date"].ge(recent_start).map({True: "recent", False: "early"}))
    p = monthly(sc, ["supplier_id", "supplier_name", "category", "period"])
    w = p.pivot_table(index=["supplier_id", "supplier_name", "category"], columns="period",
                      values=["otd_pct", "otd_base"]).reset_index()
    w.columns = ["_".join(c).strip("_") for c in w.columns]
    w["otd_change_pts"] = w["otd_pct_recent"] - w["otd_pct_early"]
    ranked = (w["otd_base_early"] >= MIN_LINES) & (w["otd_base_recent"] >= MIN_LINES)
    w["extra_late_lines"] = (-w["otd_change_pts"] / 100 * w["otd_base_recent"]).where(ranked)
    w["status"] = "Low volume"
    w.loc[ranked, "status"] = "Stable"
    w.loc[ranked & (w["otd_change_pts"] <= AMBER_DROP_PTS), "status"] = "Watch"
    w.loc[ranked & (w["otd_change_pts"] <= RED_DROP_PTS), "status"] = "Declining"

    trend = monthly(sc, ["supplier_id", "month_start_date"]).sort_values("month_start_date")
    w = w.merge(trend.groupby("supplier_id")["otd_pct"].agg(list).rename("otd_trend"), on="supplier_id")
    return w.sort_values(["extra_late_lines", "otd_change_pts"], ascending=[False, True], na_position="last")


def trend_chart(df: pd.DataFrame, field: str, title: str, fmt: str, partial_month: pd.Timestamp | None):
    df = df.assign(partial=df["month_start_date"].eq(partial_month))
    color = alt.Color("group:N", title=None, legend=alt.Legend(orient="top"),
                      scale=alt.Scale(domain=list(df["group"].unique()),
                                      range=[SUPPLIER_COLOR, PEER_COLOR]))
    base = alt.Chart(df).encode(
        x=alt.X("yearmonth(month_start_date):T", title=None, axis=alt.Axis(format="%b %Y")),
        y=alt.Y(f"{field}:Q", title=title),
        color=color,
    )
    lines = base.mark_line(strokeWidth=3)
    points = base.mark_point(size=80, filled=True).encode(
        opacity=alt.condition("datum.partial", alt.value(0.35), alt.value(1)),
        tooltip=[
            alt.Tooltip("group:N", title="Group"),
            alt.Tooltip("yearmonth(month_start_date):T", title="Month", format="%b %Y"),
            alt.Tooltip(f"{field}:Q", title=title, format=fmt),
            alt.Tooltip("po_lines:Q", title="PO lines"),
            alt.Tooltip("overdue_open_lines:Q", title="Overdue open lines"),
        ],
    )
    return (lines + points).properties(height=CHART_HEIGHT, title=title)


def fmt_pct(x: float | None) -> str:
    return "—" if x is None or pd.isna(x) else f"{x:.1f}%"


# ---------- Header (static UI first) ----------
st.title(":material/local_shipping: Supplier Scorecard")

with st.spinner("Loading supplier data from GOLD..."):
    sc_all = load_scorecard()
    suppliers = load_suppliers()
    single_source = load_single_source()

months = sorted(sc_all["month_start_date"].unique())
today_month = pd.Timestamp.today().normalize().replace(day=1)
partial_month = months[-1] if months[-1] >= today_month else None
watch = build_watchlist(sc_all, months)

# Supplier picker defaults to the top of the watchlist (biggest volume-weighted OTD decline).
supplier_ids = watch["supplier_id"].tolist()
labels = dict(zip(watch["supplier_id"], watch["supplier_name"] + " · " + watch["category"]))

f1, f2, f3 = st.columns([3, 3, 1], vertical_alignment="bottom")
supplier_id = f1.selectbox("Supplier", supplier_ids, index=0, format_func=labels.get,
                           help="Defaults to the supplier with the largest volume-weighted OTD decline.")
sup = suppliers.set_index("supplier_id").loc[supplier_id]
category = sup["category"]
plant_opts = sorted(sc_all.loc[sc_all["category"] == category, "plant_name"].dropna().unique())
plants = f2.multiselect("Plant", plant_opts, placeholder="All plants",
                        help="Filters trends and KPIs. Plant exposure always shows every plant.")
f3.button("Refresh data", icon=":material/refresh:", on_click=clear_cache, width="stretch")

st.caption(
    f"Source: GOLD.FCT_SUPPLIER_SCORECARD_MONTHLY · {months[0]:%b %Y} – {months[-1]:%b %Y}"
    + (f" (**{months[-1]:%b %Y} is month-to-date**, shown faded)" if partial_month is not None else "")
    + " · OTD counts overdue-but-unreceived PO lines as late."
)

# ---------- Watchlist ----------
with st.container(border=True):
    st.subheader("Watchlist: on-time delivery, latest 2 months vs. earlier")
    view = watch[
        ["status", "supplier_name", "category", "otd_pct_early", "otd_pct_recent",
         "otd_change_pts", "extra_late_lines", "otd_trend"]
    ]
    st.dataframe(
        view.head(8), hide_index=True, width="stretch",
        column_config={
            "status": "Status",
            "supplier_name": "Supplier",
            "category": "Category",
            "otd_pct_early": st.column_config.NumberColumn("OTD earlier", format="%.1f%%"),
            "otd_pct_recent": st.column_config.NumberColumn("OTD latest 2 mo", format="%.1f%%"),
            "otd_change_pts": st.column_config.NumberColumn("Change (pts)", format="%+.1f"),
            "extra_late_lines": st.column_config.NumberColumn(
                "Extra late lines", format="%.0f",
                help=f"OTD drop × recent lines. Blank when either period has < {MIN_LINES} lines."),
            "otd_trend": st.column_config.LineChartColumn("Monthly OTD", y_min=0, y_max=100),
        },
    )

# ---------- Selected supplier vs. peers ----------
sc = sc_all[sc_all["category"] == category]
if plants:
    sc = sc[sc["plant_name"].isin(plants)]
sc = sc.assign(group=sc["supplier_id"].eq(supplier_id).map({True: sup["supplier_name"], False: f"Other {category}"}))
trend = monthly(sc, ["group", "month_start_date"]).sort_values("month_start_date")
mine = trend[trend["group"] == sup["supplier_name"]]
peers = trend[trend["group"] != sup["supplier_name"]]
has_peers = not peers.empty

st.subheader(f"{sup['supplier_name']} vs. other {category} suppliers")
if not has_peers:
    st.info(f"{sup['supplier_name']} is the only {category} supplier, so there is no peer comparison.",
            icon=":material/info:")

if mine.empty:
    st.warning("No PO lines for this supplier at the selected plants.")
    st.stop()

first, last = mine.iloc[0], mine.iloc[-1]
peer_last = peers[peers["month_start_date"] == last["month_start_date"]]
peer_last = peer_last.iloc[0] if not peer_last.empty else None
last_label = f"{last['month_start_date']:%b %Y}" + (" MTD" if last["month_start_date"] == partial_month else "")


def kpi(col, label: str, field: str, unit: str, inverse: bool) -> None:
    val, start = last[field], first[field]
    peer = None if peer_last is None else peer_last[field]
    delta = None if pd.isna(val) or pd.isna(start) else val - start
    col.metric(
        f"{label} ({last_label})",
        "—" if pd.isna(val) else f"{val:.1f}{unit}",
        None if delta is None else f"{delta:+.1f}{' pts' if unit == '%' else unit} vs {first['month_start_date']:%b}",
        delta_color="inverse" if inverse else "normal",
        border=True,
        help=None if peer is None or pd.isna(peer) else f"Peers same month: {peer:.1f}{unit}",
    )


k1, k2, k3, k4, k5 = st.columns(5)
kpi(k1, "On-time", "otd_pct", "%", inverse=False)
kpi(k2, "OTIF", "otif_pct", "%", inverse=False)
kpi(k3, "Reject rate", "reject_pct", "%", inverse=True)
kpi(k4, "Avg delay", "avg_delay_days", " d", inverse=True)
k5.metric(
    f"Risk score ({sup['risk_tier']} risk)",
    "—" if pd.isna(sup["overall_risk_score"]) else f"{sup['overall_risk_score']:.1f}",
    border=True,
    help=f"Third-party feed, scored {sup['risk_score_date']}. Higher = healthier. "
         f"Delivery sub-score {sup['delivery_score']:.1f} · {int(sup['risk_alert_count'] or 0)} active alert(s).",
)

c1, c2 = st.columns(2)
charts = [
    ("otd_pct", "On-time delivery %", ".1f"),
    ("otif_pct", "OTIF %", ".1f"),
    ("reject_pct", "Quality reject %", ".2f"),
    ("avg_delay_days", "Avg receipt delay (days)", ".2f"),
]
for i, (field, title, fmt) in enumerate(charts):
    with (c1 if i % 2 == 0 else c2).container(border=True):
        st.altair_chart(trend_chart(trend, field, title, fmt, partial_month), width="stretch")

# ---------- Plant exposure / risk + single source ----------
b1, b2 = st.columns(2)

with b1.container(border=True):
    st.subheader("Plant exposure")
    cat_all = sc_all[sc_all["category"] == category]
    by_plant = cat_all.groupby(["plant_id", "plant_name"], as_index=False)["spend_usd"].sum().rename(
        columns={"spend_usd": "category_spend_usd"})
    sup_plant = monthly(cat_all[cat_all["supplier_id"] == supplier_id], ["plant_id"])
    exp = by_plant.merge(sup_plant[["plant_id", "spend_usd", "po_lines", "overdue_open_lines", "otd_pct"]],
                         on="plant_id")
    exp["share_pct"] = 100 * exp["spend_usd"] / exp["category_spend_usd"]
    exp = exp.sort_values(["share_pct", "spend_usd"], ascending=False)
    st.caption(f"Share of each plant's {category} spend that goes to {sup['supplier_name']}. All plants, all months.")
    st.dataframe(
        exp[["plant_id", "plant_name", "share_pct", "spend_usd", "po_lines", "overdue_open_lines", "otd_pct"]],
        hide_index=True, width="stretch",
        column_config={
            "plant_id": "Plant",
            "plant_name": "Name",
            "share_pct": st.column_config.ProgressColumn("Share of category spend", format="%.1f%%",
                                                         min_value=0, max_value=100),
            "spend_usd": st.column_config.NumberColumn("Spend", format="dollar"),
            "po_lines": st.column_config.NumberColumn("PO lines"),
            "overdue_open_lines": st.column_config.NumberColumn("Overdue open"),
            "otd_pct": st.column_config.NumberColumn("OTD", format="%.1f%%"),
        },
    )

with b2.container(border=True):
    st.subheader("Risk score")
    r1, r2, r3, r4 = st.columns(4)
    for col, label, field in [(r1, "Delivery", "delivery_score"), (r2, "Financial", "financial_score"),
                              (r3, "Geopolitical", "geopolitical_score"), (r4, "ESG", "esg_score")]:
        col.metric(label, "—" if pd.isna(sup[field]) else f"{sup[field]:.1f}")
    risk = (sc_all[sc_all["supplier_id"] == supplier_id]
            .groupby("month_start_date", as_index=False)[["avg_risk_score", "avg_delivery_risk_score"]].first()
            .melt("month_start_date", var_name="score", value_name="value")
            .replace({"score": {"avg_risk_score": "Overall", "avg_delivery_risk_score": "Delivery"}}))
    st.altair_chart(
        alt.Chart(risk).mark_line(point=True).encode(
            x=alt.X("yearmonth(month_start_date):T", title=None, axis=alt.Axis(format="%b %Y")),
            y=alt.Y("value:Q", title="Monthly avg score", scale=alt.Scale(zero=False)),
            color=alt.Color("score:N", title=None, legend=alt.Legend(orient="top")),
            tooltip=["score", alt.Tooltip("value:Q", format=".1f")],
        ).properties(height=170),
        width="stretch",
    )
    st.caption("Weekly third-party risk feed (RAW.SUP_RISK_SCORES), averaged by month in GOLD. "
               "Higher = healthier · High risk < 70 ≤ Medium < 80 ≤ Low.")

    st.subheader("Single-source materials")
    sole = single_source[single_source["supplier_id"] == supplier_id]
    if not sole.empty:
        st.error(f"{sup['supplier_name']} is the only supplier for {len(sole)} material(s): "
                 + ", ".join(sole["material_id"]), icon=":material/warning:")
    st.dataframe(
        single_source.assign(selected=single_source["supplier_id"].eq(supplier_id))[
            ["is_critical_material", "material_id", "material_description", "material_category",
             "supplier_name", "plants", "po_value_usd", "selected"]],
        hide_index=True, width="stretch",
        column_config={
            "is_critical_material": st.column_config.CheckboxColumn("Critical"),
            "material_id": "Material",
            "material_description": "Description",
            "material_category": "Category",
            "supplier_name": "Only supplier",
            "plants": st.column_config.NumberColumn("Plants"),
            "po_value_usd": st.column_config.NumberColumn("PO value", format="dollar"),
            "selected": st.column_config.CheckboxColumn("Selected supplier"),
        },
    )
