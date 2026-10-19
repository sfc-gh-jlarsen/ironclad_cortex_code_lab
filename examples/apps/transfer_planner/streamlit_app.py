"""Transfer Planner: daily transfer-vs-reorder decisions for raw materials.

Read only. Recommendations come from GOLD.FCT_TRANSFER_VS_REORDER; this app displays
them and never creates POs or transfers.
"""
import os

import pandas as pd
import streamlit as st

import queries as q

st.set_page_config(page_title="Transfer Planner", page_icon=":truck:", layout="wide")
st.title("Transfer Planner")
st.caption("Move it, don't buy it: today's below-reorder-point raw materials and the best sister-plant donor. "
           "Recommendations only; no POs or transfers are created here.")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))


@st.cache_data(ttl=600, show_spinner=False)
def load(sql: str) -> pd.DataFrame:
    df = conn.query(sql, ttl=0)
    df.columns = [c.lower() for c in df.columns]
    return df


def refresh() -> None:
    load.clear()


with st.spinner("Loading transfer-vs-reorder data..."):
    today = load(q.TODAY_ACTIONS)
    donors = load(q.OTHER_DONORS)
    history = load(q.HISTORY)

history["snapshot_date"] = pd.to_datetime(history["snapshot_date"])
as_of = pd.to_datetime(history["snapshot_date"].max())

# ---- Sidebar filters ----
with st.sidebar:
    st.header("Filters")
    plant_labels = (history[["plant_id", "plant_name"]].drop_duplicates().sort_values("plant_id"))
    plant_options = (plant_labels["plant_id"] + " " + plant_labels["plant_name"]).tolist()
    picked = st.multiselect("Plant", plant_options, placeholder="All plants")
    plants = [p.split(" ", 1)[0] for p in picked] or plant_labels["plant_id"].tolist()
    window = st.select_slider("History window (days)", options=[30, 60, 90], value=90)
    st.button("Refresh data", on_click=refresh, use_container_width=True)
    st.caption(f"Data as of {as_of:%Y-%m-%d}")

today_f = today[today["plant_id"].isin(plants)]
hist_f = history[history["plant_id"].isin(plants)
                 & (history["snapshot_date"] > as_of - pd.Timedelta(days=window))]
missed = hist_f[(hist_f["recommended_action"] == "TRANSFER") & (hist_f["actual_action"] == "PO")]

# ---- KPIs ----
xfer_today = today_f[today_f["recommended_action"] == "TRANSFER"]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Shortages today", len(today_f))
k2.metric("Recommended transfers", len(xfer_today))
k3.metric("Avoidable purchase today", f"${xfer_today['working_capital_avoided_usd'].sum():,.0f}")
k4.metric(f"Missed transfers ({window}d)", f"${missed['working_capital_avoided_usd'].sum():,.0f}",
          help="Days we recommended TRANSFER but placed a PO; net of freight.")

# ---- Today's actions ----
st.subheader(f"Today's actions ({as_of:%Y-%m-%d})")
actions = pd.DataFrame({
    "Plant": today_f["plant_id"] + " " + today_f["plant_name"],
    "Material": today_f["material_id"] + " " + today_f["material_description"],
    "Need": today_f["needed_qty"].astype(float),
    "UoM": today_f["uom"],
    "Best donor": (today_f["donor_plant_id"] + " " + today_f["donor_plant_name"]).fillna("none"),
    "Transit days": today_f["transfer_lead_time_days"],
    "Freight $": today_f["transfer_cost_usd"].astype(float),
    "Supplier lead time (days)": today_f["reorder_lead_time_days"],
    "Purchase $": today_f["reorder_cost_usd"].astype(float),
    "Recommendation": today_f["recommended_action"],
})
st.dataframe(
    actions, hide_index=True, use_container_width=True,
    column_config={
        "Need": st.column_config.NumberColumn(format="%.0f"),
        "Freight $": st.column_config.NumberColumn(format="$%.0f"),
        "Purchase $": st.column_config.NumberColumn(format="$%.0f"),
    },
)
st.download_button("Download CSV", actions.to_csv(index=False).encode("utf-8"),
                   file_name=f"transfer_actions_{as_of:%Y%m%d}.csv", mime="text/csv")

with st.expander("All candidate donors for today's shortages"):
    d = donors[donors["plant_id"].isin(plants)]
    st.dataframe(
        d.rename(columns={"plant_id": "Short plant", "material_id": "Material",
                          "candidate_plant_id": "Donor", "candidate_plant_name": "Donor name",
                          "surplus_qty": "Surplus qty", "transport_mode": "Mode",
                          "transit_days": "Transit days", "cost_per_kg_usd": "$/kg",
                          "handling_fee_usd": "Handling $", "is_best_donor": "Best donor"}),
        hide_index=True, use_container_width=True,
    )
    st.caption("Best donor follows the gold rule: covers >= 50% of need, then shortest transit, then cheapest.")

# ---- Charts ----
left, right = st.columns(2)
with left:
    st.subheader(f"Shortage days by plant ({window}d)")
    counts = (hist_f.groupby("plant_name").size().rename("Shortage days").sort_values(ascending=False))
    st.bar_chart(counts, horizontal=True)
with right:
    st.subheader("Missed transfers: cumulative $")
    if missed.empty:
        st.info("No missed transfers in this window.")
    else:
        cum = (missed.groupby("snapshot_date")["working_capital_avoided_usd"].sum()
               .astype(float).cumsum().rename("Cumulative $"))
        st.area_chart(cum)
