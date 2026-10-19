"""Ironclad Tire & Rubber Co. demo data generator (fictional company).

Usage (from a terminal or Workspace):  python generate.py [--window-days 90] [--validate-only]

How gap-filling works
---------------------
* RAW.GEN_LOAD_LOG records every business day that has been generated.
* Each run targets [today - window, yesterday]; days already in the log are skipped.
* Every document (PO, sales order, transfer) has its whole lifecycle simulated the day it is
  created, using an RNG seeded by the document number. A run only inserts rows whose
  parent-creation day and event day are both "loaded after this run" and were NOT both loaded
  before it. So a PO created Oct 10 gets its goods receipt inserted by the run that fills Oct 17,
  and every child row always has a parent: referential integrity by construction.
"""
import argparse
import json
import math
import os
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta

import pandas as pd

from master_data import (CURRENCY_BY_BUKRS, DECLINE_LEAD_DAYS, DETERIORATING_SUPPLIER, DISCOUNT_BY_SEGMENT, PLANT,
                         Master, crc, rng_for)

DB = '"STREAMLIT-CORTEX-20261018"'
SCHEMA = "RAW"
EPOCH = date(2024, 1, 1)
LOOKBACK_DAYS = 220          # longest lifecycle (order -> late payment after dispute)
BUYERS = ["MKOVAC", "JRIVERA", "SPATEL", "LBRANDT", "TNGUYEN", "AOKAFOR"]
INSPECTORS = ["QI-RDG-07", "QI-CDB-02", "QI-HOL-11", "QI-VAL-04", "QI-RHF-09", "QI-PNH-03"]
# Start of the supplier-decline storyline. Set in main() relative to the first generated day, so the
# story stays inside the demo window whenever the generator is run (and is stable across gap-fill runs).
DECLINE_START = date.today() - timedelta(days=DECLINE_LEAD_DAYS)


# ---------------------------------------------------------------- connection
class Conn:
    """Works inside a Snowflake Workspace (active Snowpark session) or with an OAuth token file."""

    def __init__(self):
        try:
            from snowflake.snowpark.context import get_active_session
            self.session = get_active_session()
            self.kind = "snowpark"
        except Exception:
            import snowflake.connector
            token = open(os.environ.get("SNOWFLAKE_TOKEN_FILE_PATH", "/snowflake/session/token")).read().strip()
            self.cn = snowflake.connector.connect(
                account=os.environ["SNOWFLAKE_ACCOUNT"], host=os.environ.get("SNOWFLAKE_HOST"),
                authenticator="oauth", token=token, role=os.environ.get("SNOWFLAKE_ROLE"),
                warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"))
            self.kind = "connector"
        self.sql(f"USE DATABASE {DB}")
        self.sql(f"USE SCHEMA {SCHEMA}")

    def sql(self, q):
        if self.kind == "snowpark":
            return [tuple(r) for r in self.session.sql(q).collect()]
        cur = self.cn.cursor()
        cur.execute(q)
        return cur.fetchall() if cur.description else []

    def write(self, df: pd.DataFrame, table: str, overwrite=False) -> int:
        if df.empty:
            return 0
        df.columns = [c.upper() for c in df.columns]
        # database/schema come from the session (USE above); the DB name contains hyphens
        if self.kind == "snowpark":
            self.session.write_pandas(df, table, auto_create_table=True, overwrite=overwrite,
                                      quote_identifiers=False, use_logical_type=True)
        else:
            from snowflake.connector.pandas_tools import write_pandas
            write_pandas(self.cn, df, table, auto_create_table=True, overwrite=overwrite,
                         quote_identifiers=False, use_logical_type=True)
        return len(df)


# ---------------------------------------------------------------- deterministic signals
def ix_of(d: date) -> int:
    return (d - EPOCH).days


def fx(d: date, cur: str) -> float:
    """Units of `cur` per 1 USD."""
    if cur == "USD":
        return 1.0
    i = ix_of(d)
    noise = rng_for("fx", cur, i).normal(0, 0.004)
    if cur == "MXN":
        return 17.6 + 0.7 * math.sin(i / 23) + 0.3 * math.sin(i / 7.3) + 17.6 * noise
    return 0.915 + 0.025 * math.sin(i / 31) + 0.915 * noise


def stock_level(d: date, w: str, m: str) -> float:
    """On-hand stock as a multiple of the reorder point (MARC.MINBE). Deterministic per day."""
    h, i = crc(w + m), ix_of(d)
    lvl = 1.75 + 0.55 * math.sin(2 * math.pi * (i + h % 37) / (24 + h % 19)) + rng_for("stk", w, m, i).normal(0, 0.12)
    if h % 13 == 0:                     # chronically tight items
        lvl -= 0.8
    # Scenario: tread-grade carbon black shortage at Valle Alto (P400) while Ridgeport (P100) and
    # Pine Hollow (P600) sit on surplus.
    # 50-day cycle: slow 44-day burn-down below reorder point, then a 6-day recovery.
    if m == "RM-CB-N234" and w == "P400":
        ph = i % 50
        lvl = 1.35 - 0.028 * ph if ph < 44 else 0.12 + 0.35 * (ph - 43)
    if m == "RM-CB-N234" and w in ("P100", "P600"):
        lvl += 1.2
    # Finished-tire scenario: EV tire demand outruns supply everywhere
    if m.startswith("FG-PC-07"):
        lvl -= 0.75
    return max(round(lvl, 4), 0.03)


def supplier_ontime(lifnr: str, d: date, base: float) -> float:
    if lifnr == DETERIORATING_SUPPLIER:
        k = (d - DECLINE_START).days
        return base if k <= 0 else max(0.45, base - 0.0042 * k)
    return base


def supplier_reject(lifnr: str, d: date, base: float) -> float:
    if lifnr == DETERIORATING_SUPPLIER:
        k = (d - DECLINE_START).days
        return base if k <= 0 else min(0.09, base + 0.0006 * k)
    return base


def ts(d: date, r, start_h=7, end_h=18) -> datetime:
    return datetime(d.year, d.month, d.day) + timedelta(seconds=int(r.integers(start_h * 3600, end_h * 3600)))


def biz_day(d: date) -> date:
    """Roll weekend dates forward to Monday (payments, receipts)."""
    return d + timedelta(days=(7 - d.weekday()) % 7) if d.weekday() >= 5 else d


# ---------------------------------------------------------------- daily simulation
def gen_day(d: date, M: Master) -> dict:
    """All rows for documents created on day d (including their future lifecycle events)
    plus daily snapshots for day d. Every row carries _P (parent day) and _D (event day)."""
    out = defaultdict(list)
    i, wd = ix_of(d), d.weekday()

    def emit(table, event_day, **row):
        row["_P"], row["_D"] = d, event_day
        out[table].append(row)

    # ---- reference: FX
    for cur, src in (("MXN", "BANXICO_FIX"), ("EUR", "ECB_REFERENCE")):
        emit("FX_RATES", d, RATE_DATE=d, FROM_CURRENCY="USD", TO_CURRENCY=cur, EXCHANGE_RATE=round(fx(d, cur), 5),
             RATE_SOURCE=src)

    # ---- inventory snapshot (MARD)
    levels = {}
    for (w, m), mc in M.marc.items():
        lvl = stock_level(d, w, m)
        levels[(w, m)] = lvl
        qi = rng_for("insme", w, m, i)
        emit("MARD", d, SNAPSHOT_DATE=d, MATNR=m, WERKS=w, LGORT="0001", LABST=round(lvl * mc["MINBE"], 3),
             INSME=round(float(mc["MINBE"] * qi.uniform(0, 0.04)), 3), MEINS=M.mat[m]["MEINS"])

    # ---- inter-plant stock transfers (WMS). Only ~30% of transfer opportunities get executed;
    # the rest are covered by new POs, which is the "transfer vs reorder" story.
    r = rng_for("sto", i)
    n_tr = 0
    for m in M.raw_ids:
        lv = {w: levels[(w, m)] for w in M.plant_ids if (w, m) in levels}
        highs = [w for w, l in lv.items() if l > 2.2]
        for w in [w for w, l in lv.items() if l < 1.0]:
            if not highs or r.random() >= 0.30:
                continue
            src = max(highs, key=lambda x: lv[x] - (0.6 if M.lanes[(x, w)]["MODE"] != "TRUCK" else 0))
            lane = M.lanes[(src, w)]
            qty = round(float(M.marc[(w, m)]["MINBE"] * r.uniform(0.4, 0.8)), 0)
            tid = f"TR{i:05d}{n_tr:03d}"
            n_tr += 1
            arrive = d + timedelta(days=lane["TRANSIT_DAYS"] + int(r.integers(0, 3)))
            kg = qty * M.mat[m]["NTGEW_KG"]
            emit("WMS_STOCK_TRANSFERS", d, TRANSFER_ID=tid, CREATED_TS=ts(d, r), FROM_PLANT=src, TO_PLANT=w,
                 MATERIAL_ID=m, QUANTITY=qty, UOM=M.mat[m]["MEINS"], LANE_ID=lane["LANE_ID"], SHIP_DATE=d,
                 PLANNED_ARRIVAL_DATE=d + timedelta(days=lane["TRANSIT_DAYS"]),
                 FREIGHT_COST_USD=round(kg * lane["COST_PER_KG_USD"] + lane["HANDLING_FEE_USD"], 2),
                 REQUESTED_BY=BUYERS[int(r.integers(0, len(BUYERS)))])
            emit("WMS_TRANSFER_RECEIPTS", arrive, RECEIPT_ID=f"RC{i:05d}{n_tr:03d}", TRANSFER_ID=tid,
                 TO_PLANT=w, RECEIVED_DATE=arrive, RECEIVED_QTY=round(qty * (1 - float(r.uniform(0, 0.01))), 0),
                 CONDITION_CODE="OK" if r.random() > 0.04 else "DAMAGED_PARTIAL")

    # ---- purchasing: EKKO/EKPO -> EKBE (GR) + quality inspections -> RBKP/RSEG (supplier invoice)
    r = rng_for("po", i)
    n_po = int(r.integers(20, 31)) if wd < 5 else int(r.integers(4, 9))
    for n in range(n_po):
        ebeln = str(4500000000 + i * 100 + n)
        w = str(r.choice(M.plant_ids, p=M.plant_w))
        low = [m for m in M.raw_at_plant[w] if levels[(w, m)] < 1.0]
        m0 = str(r.choice(low)) if low and r.random() < 0.6 else str(r.choice(M.raw_at_plant[w]))
        cands = M.eina_by_mat[m0]
        prim = [c for c in cands if c["IS_PRIMARY"]]
        rec0 = prim[0] if prim and r.random() < 0.7 else cands[int(r.integers(0, len(cands)))]
        lifnr = rec0["LIFNR"]
        sup = M.sup[lifnr]
        extra = [c for c in M.eina_by_sup[lifnr] if c["MATNR"] != m0 and (w, c["MATNR"]) in M.marc]
        recs = [rec0] + [extra[k] for k in r.permutation(len(extra))[: int(r.integers(0, 3))]]
        bukrs = PLANT[w]["BUKRS"]
        cur = CURRENCY_BY_BUKRS[bukrs]
        rate = fx(d, cur)
        lines = []
        for li, rec in enumerate(recs):
            m = rec["MATNR"]
            qty = round(float(M.marc[(w, m)]["MINBE"] * r.uniform(0.3, 0.9)), -1 if M.mat[m]["MEINS"] != "EA" else 0)
            qty = max(qty, 1.0)
            netpr = round(rec["NETPR_USD"] * rate * (1 + r.normal(0, 0.012)), 4)
            lines.append(dict(EBELN=ebeln, EBELP=10 * (li + 1), MATNR=m, WERKS=w, MENGE=qty,
                              MEINS=M.mat[m]["MEINS"], NETPR=netpr, NETWR=round(qty * netpr, 2),
                              EINDT=d + timedelta(days=rec["APLFZ"]), INFNR=rec["INFNR"]))
        emit("EKKO", d, EBELN=ebeln, BUKRS=bukrs, BSART="NB", LIFNR=lifnr, EKORG=f"PO{bukrs}", BEDAT=d,
             WAERS=cur, ERNAM=BUYERS[int(r.integers(0, len(BUYERS)))], CREATED_TS=ts(d, r))
        for ln in lines:
            emit("EKPO", d, **ln)

        # lifecycle
        rl = rng_for("polc", int(ebeln))
        last_gr = d
        received = {}
        for ln in lines:
            ot = supplier_ontime(lifnr, d, sup["OT"])
            delay = int(rl.integers(-2, 1)) if rl.random() < ot else int(rl.integers(2, 16))
            gr1 = biz_day(ln["EINDT"] + timedelta(days=delay))
            partial = rl.random() < 0.15
            q1 = ln["MENGE"] if not partial else round(ln["MENGE"] * float(rl.uniform(0.5, 0.85)), 0)
            grs = [(gr1, q1)] + ([(biz_day(gr1 + timedelta(days=int(rl.integers(3, 12)))), ln["MENGE"] - q1)]
                                 if partial else [])
            for k, (gd, q) in enumerate(grs):
                mblnr = f"50{i:05d}{n:02d}{ln['EBELP'] // 10}{k}"
                emit("EKBE", gd, BELNR=mblnr, GJAHR=gd.year, BUZEI=1, EBELN=ebeln, EBELP=ln["EBELP"], VGABE="1",
                     BWART="101", BUDAT=gd, MENGE=q, DMBTR=round(q * ln["NETPR"], 2), WAERS=cur)
                rej_rate = supplier_reject(lifnr, gd, sup["REJ"])
                bad = rl.random() < rej_rate * 6
                rejected = round(q * float(rl.uniform(0.02, 0.25)), 0) if bad else 0.0
                defects = ([{"code": str(rl.choice(["CONTAMINATION", "MOISTURE", "SPEC_VISCOSITY", "PACKAGING",
                                                    "PARTICLE_SIZE", "DIMENSIONAL"])),
                             "count": int(rl.integers(1, 9))}] if bad else [])
                payload = {"inspection_lot": f"IL{mblnr}", "material_document": mblnr, "po_number": ebeln,
                           "po_item": ln["EBELP"], "supplier_id": lifnr, "material_id": ln["MATNR"], "plant": w,
                           "received_qty": q, "sample_size": int(rl.integers(3, 20)), "defects": defects,
                           "result": ("REJECT" if rejected > q * 0.15 else "CONDITIONAL") if bad else "ACCEPT",
                           "rejected_qty": rejected, "inspector": INSPECTORS[M.plant_ids.index(w)],
                           "inspected_at": ts(gd, rl).isoformat()}
                emit("SUP_QUALITY_INSPECTIONS", gd, INSPECTION_LOT=f"IL{mblnr}", SOURCE_SYSTEM="SUPPLIER_PORTAL",
                     PAYLOAD=json.dumps(payload), INGESTED_AT=ts(gd, rl, 18, 23))
                received[ln["EBELP"]] = received.get(ln["EBELP"], 0) + q
                last_gr = max(last_gr, gd)
        # supplier invoice (3-way match source). ~20% of invoices from biased suppliers over-bill.
        inv_d = last_gr + timedelta(days=int(rl.integers(1, 8)))
        over = 1 + float(rl.uniform(0.01, 0.06)) if rl.random() < (0.12 + max(sup["BIAS"], 0) * 3) else 1.0
        belnr = f"51{i:05d}{n:03d}"
        total = 0.0
        for k, ln in enumerate(lines):
            amt = round(received[ln["EBELP"]] * ln["NETPR"] * over, 2)
            total += amt
            emit("RSEG", inv_d, BELNR=belnr, GJAHR=inv_d.year, BUZEI=k + 1, EBELN=ebeln, EBELP=ln["EBELP"],
                 MATNR=ln["MATNR"], MENGE=received[ln["EBELP"]], WRBTR=amt)
        emit("RBKP", inv_d, BELNR=belnr, GJAHR=inv_d.year, BUKRS=bukrs, LIFNR=lifnr, BLDAT=inv_d,
             BUDAT=inv_d + timedelta(days=1), RMWWR=round(total, 2), WAERS=cur,
             XBLNR=f"INV-{crc(belnr) % 900000 + 100000}", ZTERM="NT45")

    # ---- sales: VBAK/VBAP -> LIKP/LIPS -> VBRK/VBRP -> BSID_BSAD -> PAYMENTS (+ AR_DISPUTES)
    r = rng_for("so", i)
    n_so = int(r.integers(34, 47)) if wd < 5 else int(r.integers(5, 11))
    for n in range(n_so):
        vbeln = str(1000000000 + i * 100 + n)
        kunnr = str(r.choice(M.cust_ids, p=M.cust_w))
        c = M.cust[kunnr]
        seg, bukrs = c["SEGMENT"], c["BUKRS"]
        cur = CURRENCY_BY_BUKRS[bukrs]
        rate = fx(d, cur)
        pool = [m for m in M.fg_ids if ("-CT-" in m) == (seg == "FLEET" and r.random() < 0.8)] or M.fg_ids
        skus = list(r.choice(pool, size=min(int(r.integers(1, 5)), len(pool)), replace=False))
        requested = d + timedelta(days=int(r.integers(3, 15)))
        lines = []
        for li, m in enumerate(skus):
            m = str(m)
            plants = [p for p in M.fg_plants[m] if PLANT[p]["BUKRS"] == bukrs] or M.fg_plants[m]
            w = str(plants[int(r.integers(0, len(plants)))])
            lo, hi = {"OEM": (200, 1500), "DEALER": (8, 80), "FLEET": (20, 240)}[seg]
            qty = float(r.integers(lo, hi))
            netpr = round(M.mat[m]["BASE_PRICE_USD"] * (1 - DISCOUNT_BY_SEGMENT[seg]) * (1 + r.normal(0, 0.02)) * rate, 2)
            lines.append(dict(VBELN=vbeln, POSNR=10 * (li + 1), MATNR=m, WERKS=w, KWMENG=qty, VRKME="EA",
                              NETPR=netpr, NETWR=round(qty * netpr, 2)))
        emit("VBAK", d, VBELN=vbeln, AUART="ZOEM" if seg == "OEM" else "ZOR", ERDAT=d, ERZET=ts(d, r),
             KUNNR=kunnr, VKORG=bukrs, VTWEG={"OEM": "10", "DEALER": "20", "FLEET": "30"}[seg],
             VDATU=requested, WAERK=cur, NETWR=round(sum(l["NETWR"] for l in lines), 2),
             BSTNK=f"PO-{crc(vbeln) % 9000000 + 1000000}")
        for ln in lines:
            emit("VBAP", d, **ln)

        rl = rng_for("solc", int(vbeln))
        # deliveries: one per shipping plant, plus a backorder wave for short-shipped lines
        waves = defaultdict(list)       # (plant, wave) -> [(line, qty, short)]
        plant_gi = {}
        for ln in lines:
            w = ln["WERKS"]
            short = levels.get((w, ln["MATNR"]), 2) < 1.0 and rl.random() < 0.6
            if w not in plant_gi:
                slip = int(rl.integers(-1, 2)) if rl.random() < 0.85 else int(rl.integers(3, 9))
                plant_gi[w] = requested + timedelta(days=slip)
            if short:
                plant_gi[w] = max(plant_gi[w], requested + timedelta(days=int(rl.integers(2, 8))))
            q1 = ln["KWMENG"] if not short else round(ln["KWMENG"] * float(rl.uniform(0.5, 0.9)), 0)
            waves[(w, 0)].append((ln, q1, short))
            if short and rl.random() < 0.65:
                waves[(w, 1)].append((ln, ln["KWMENG"] - q1, False))
        for k, ((w, wave), items) in enumerate(sorted(waves.items())):
            gi = plant_gi[w] if wave == 0 else plant_gi[w] + timedelta(days=int(rl.integers(5, 16)))
            gi = max(gi, d + timedelta(days=1))
            suffix = f"{i:05d}{n:02d}{k:02d}"
            dlv, bil, acc = f"80{suffix}", f"90{suffix}", f"18{suffix}"
            emit("LIKP", gi, VBELN=dlv, LFART="LF", VSTEL=w, KUNNR=kunnr, LFDAT=requested, WADAT_IST=gi,
                 ROUTE=f"R{w[1:]}{c['LAND1']}")
            amt = 0.0
            for p, (ln, q, _) in enumerate(items):
                emit("LIPS", gi, VBELN=dlv, POSNR=10 * (p + 1), VGBEL=vbeln, VGPOS=ln["POSNR"], MATNR=ln["MATNR"],
                     WERKS=w, LFIMG=q, VRKME="EA")
                line_amt = round(q * ln["NETPR"], 2)
                amt += line_amt
                emit("VBRP", gi, VBELN=bil, POSNR=10 * (p + 1), VGBEL=dlv, VGPOS=10 * (p + 1), AUBEL=vbeln,
                     AUPOS=ln["POSNR"], MATNR=ln["MATNR"], WERKS=w, FKIMG=q, NETWR=line_amt)
            amt = round(amt, 2)
            emit("VBRK", gi, VBELN=bil, FKART="F2", FKDAT=gi, KUNAG=kunnr, BUKRS=bukrs, NETWR=amt, WAERK=cur,
                 ZTERM=c["ZTERM"])
            emit("BSID_BSAD", gi, BELNR=acc, BUKRS=bukrs, GJAHR=gi.year, BUZEI=1, KUNNR=kunnr, BLART="RV",
                 BSCHL="01", BLDAT=gi, BUDAT=gi, ZFBDT=gi, ZBD1T=c["TERMS_DAYS"], DMBTR=amt, WAERS=cur,
                 VBELN=bil)

            # disputes
            late = gi > requested + timedelta(days=2)
            shorted = any(s for _, _, s in items)
            p_disp = 0.03 + (0.15 if late else 0) + (0.22 if shorted else 0) + (0.08 if kunnr in M.slow_payers else 0)
            credit, resolved_d, disputed = 0.0, None, rl.random() < p_disp
            if disputed:
                reason = ("SHORT_SHIPMENT" if shorted else "LATE_DELIVERY" if late else
                          str(rl.choice(["PRICING_DISCREPANCY", "DAMAGED_GOODS", "DUPLICATE_BILLING"])))
                d_amt = round(amt * float(rl.uniform(0.05, 0.4)), 2)
                opened = gi + timedelta(days=int(rl.integers(4, 21)))
                did = f"DSP{suffix}"
                emit("AR_DISPUTES", opened, DISPUTE_ID=did, EVENT_TS=ts(opened, rl), BELNR=acc, BILLING_DOC=bil,
                     KUNNR=kunnr, REASON_CODE=reason, STATUS="OPEN", DISPUTED_AMOUNT=d_amt, CREDIT_AMOUNT=0.0,
                     WAERS=cur, OWNER="COLLECTIONS")
                rev = opened + timedelta(days=int(rl.integers(2, 9)))
                emit("AR_DISPUTES", rev, DISPUTE_ID=did, EVENT_TS=ts(rev, rl), BELNR=acc, BILLING_DOC=bil,
                     KUNNR=kunnr, REASON_CODE=reason, STATUS="IN_REVIEW", DISPUTED_AMOUNT=d_amt, CREDIT_AMOUNT=0.0,
                     WAERS=cur, OWNER=str(rl.choice(["SALES_OPS", "LOGISTICS", "PRICING"])))
                if rl.random() < 0.75:
                    resolved_d = rev + timedelta(days=int(rl.integers(6, 40)))
                    credit = round(d_amt * float(rl.choice([0.0, 0.5, 1.0], p=[0.3, 0.3, 0.4])), 2)
                    emit("AR_DISPUTES", resolved_d, DISPUTE_ID=did, EVENT_TS=ts(resolved_d, rl), BELNR=acc,
                         BILLING_DOC=bil, KUNNR=kunnr, REASON_CODE=reason, STATUS="RESOLVED", DISPUTED_AMOUNT=d_amt,
                         CREDIT_AMOUNT=credit, WAERS=cur, OWNER="COLLECTIONS")

            # payment
            mu, sd = M.pay_profile[kunnr]
            never_pays = 0.12 if kunnr in M.slow_payers else 0.025
            if rl.random() < never_pays or (disputed and resolved_d is None):
                continue                                    # stays open (write-off candidate / unresolved)
            due = gi + timedelta(days=c["TERMS_DAYS"])
            pay = due + timedelta(days=int(round(rl.normal(mu, sd))))
            if disputed:
                pay = max(pay, resolved_d + timedelta(days=int(rl.integers(2, 12))))
            pay = biz_day(max(pay, gi + timedelta(days=3)))
            emit("PAYMENTS", pay, PAYMENT_ID=f"PY{suffix}", BUKRS=bukrs, KUNNR=kunnr, PAYMENT_DATE=pay,
                 AMOUNT=round(amt - credit, 2), WAERS=cur, CLEARED_BELNR=acc,
                 PAYMENT_METHOD=str(rl.choice(["ACH", "WIRE", "CHECK"], p=[0.6, 0.3, 0.1])),
                 BANK_REF=f"BR{crc(acc) % 10**9:09d}")

    # ---- weekly supplier risk feed (JSON) every Monday
    if wd == 0:
        for lifnr, s in M.sup.items():
            rr = rng_for("risk", lifnr, i)
            ot = supplier_ontime(lifnr, d, s["OT"])
            scores = {"financial": round(float(rr.uniform(55, 95)), 1),
                      "geopolitical": round(float({"US": 88, "DE": 90, "ES": 86, "MX": 74}.get(s["LAND1"], 62)
                                                  + rr.normal(0, 4)), 1),
                      "esg": round(float(rr.uniform(50, 92)), 1),
                      "delivery": round(ot * 100 + float(rr.normal(0, 3)), 1)}
            overall = round(sum(scores.values()) / 4, 1)
            alerts = []
            if scores["delivery"] < 75:
                alerts.append({"type": "DELIVERY_PERFORMANCE", "severity": "HIGH" if scores["delivery"] < 65 else "MEDIUM"})
            if s["CATEGORIES"][0] == "Steel Cord":
                alerts.append({"type": "SINGLE_SOURCE_DEPENDENCY", "severity": "HIGH"})
            emit("SUP_RISK_SCORES", d, FEED_ID=f"RSK{i:05d}{lifnr[-3:]}", SOURCE_SYSTEM="RISK_INTEL_VENDOR",
                 PAYLOAD=json.dumps({"supplier_id": lifnr, "supplier_name": s["NAME1"], "as_of": d.isoformat(),
                                     "scores": scores, "overall_score": overall, "alerts": alerts}),
                 INGESTED_AT=ts(d, rr, 5, 7))
    return out


# ---------------------------------------------------------------- integrity checks
CHECKS = {
    "EKKO->LFA1": "SELECT COUNT(*) FROM EKKO h LEFT JOIN LFA1 s ON h.LIFNR=s.LIFNR WHERE s.LIFNR IS NULL",
    "EKPO->EKKO": "SELECT COUNT(*) FROM EKPO l LEFT JOIN EKKO h ON l.EBELN=h.EBELN WHERE h.EBELN IS NULL",
    "EKPO->MARA": "SELECT COUNT(*) FROM EKPO l LEFT JOIN MARA m ON l.MATNR=m.MATNR WHERE m.MATNR IS NULL",
    "EKBE->EKPO": "SELECT COUNT(*) FROM EKBE g LEFT JOIN EKPO l ON g.EBELN=l.EBELN AND g.EBELP=l.EBELP WHERE l.EBELN IS NULL",
    "RSEG->EKPO": "SELECT COUNT(*) FROM RSEG g LEFT JOIN EKPO l ON g.EBELN=l.EBELN AND g.EBELP=l.EBELP WHERE l.EBELN IS NULL",
    "RSEG->RBKP": "SELECT COUNT(*) FROM RSEG g LEFT JOIN RBKP h ON g.BELNR=h.BELNR WHERE h.BELNR IS NULL",
    "VBAK->KNA1": "SELECT COUNT(*) FROM VBAK h LEFT JOIN KNA1 c ON h.KUNNR=c.KUNNR WHERE c.KUNNR IS NULL",
    "VBAP->VBAK": "SELECT COUNT(*) FROM VBAP l LEFT JOIN VBAK h ON l.VBELN=h.VBELN WHERE h.VBELN IS NULL",
    "LIPS->VBAP": "SELECT COUNT(*) FROM LIPS d LEFT JOIN VBAP l ON d.VGBEL=l.VBELN AND d.VGPOS=l.POSNR WHERE l.VBELN IS NULL",
    "LIPS->LIKP": "SELECT COUNT(*) FROM LIPS d LEFT JOIN LIKP h ON d.VBELN=h.VBELN WHERE h.VBELN IS NULL",
    "VBRP->LIKP": "SELECT COUNT(*) FROM VBRP b LEFT JOIN LIKP h ON b.VGBEL=h.VBELN WHERE h.VBELN IS NULL",
    "VBRK->KNA1": "SELECT COUNT(*) FROM VBRK h LEFT JOIN KNA1 c ON h.KUNAG=c.KUNNR WHERE c.KUNNR IS NULL",
    "BSID->VBRK": "SELECT COUNT(*) FROM BSID_BSAD a LEFT JOIN VBRK b ON a.VBELN=b.VBELN WHERE b.VBELN IS NULL",
    "PAYMENTS->BSID": "SELECT COUNT(*) FROM PAYMENTS p LEFT JOIN BSID_BSAD a ON p.CLEARED_BELNR=a.BELNR WHERE a.BELNR IS NULL",
    "DISPUTES->BSID": "SELECT COUNT(*) FROM AR_DISPUTES x LEFT JOIN BSID_BSAD a ON x.BELNR=a.BELNR WHERE a.BELNR IS NULL",
    "RECEIPTS->TRANSFERS": "SELECT COUNT(*) FROM WMS_TRANSFER_RECEIPTS r LEFT JOIN WMS_STOCK_TRANSFERS t ON r.TRANSFER_ID=t.TRANSFER_ID WHERE t.TRANSFER_ID IS NULL",
    "DUP EKPO": "SELECT COUNT(*) FROM (SELECT EBELN,EBELP FROM EKPO GROUP BY 1,2 HAVING COUNT(*)>1)",
    "DUP VBRK": "SELECT COUNT(*) FROM (SELECT VBELN FROM VBRK GROUP BY 1 HAVING COUNT(*)>1)",
    "DUP MARD": "SELECT COUNT(*) FROM (SELECT SNAPSHOT_DATE,WERKS,MATNR FROM MARD GROUP BY 1,2,3 HAVING COUNT(*)>1)",
}


def validate(c: Conn) -> bool:
    ok = True
    print("\nIntegrity checks (expect 0):")
    for name, q in CHECKS.items():
        try:
            v = c.sql(q)[0][0]
        except Exception as e:      # table not created yet
            v = f"n/a ({str(e).splitlines()[0][:60]})"
        ok &= v == 0
        print(f"  {name:<22} {v}")
    return ok


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window-days", type=int, default=90)
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    c = Conn()
    if args.validate_only:
        return validate(c)
    today = date.today()
    yesterday, start = today - timedelta(days=1), today - timedelta(days=args.window_days)
    run_id = uuid.uuid4().hex[:12]

    M = Master(today)
    for t, df in M.tables().items():           # deterministic, so a full replace is idempotent
        c.write(df, t, overwrite=True)
    print(f"Master data refreshed ({len(M.cust)} customers, {len(M.sup)} suppliers, {len(M.mat)} materials).")

    c.sql("CREATE TABLE IF NOT EXISTS GEN_LOAD_LOG (LOAD_DATE DATE, LOADED_AT TIMESTAMP_NTZ, RUN_ID STRING)")
    loaded = {r[0] for r in c.sql("SELECT DISTINCT LOAD_DATE FROM GEN_LOAD_LOG")}
    fill = [start + timedelta(days=k) for k in range((yesterday - start).days + 1)
            if start + timedelta(days=k) not in loaded]
    if not fill:
        print(f"Nothing to generate: {start}..{yesterday} already loaded.")
        validate(c)
        return
    print(f"Filling {len(fill)} day(s): {fill[0]} .. {fill[-1]}")
    after = loaded | set(fill)
    global DECLINE_START
    DECLINE_START = min(after) + timedelta(days=args.window_days - DECLINE_LEAD_DAYS)
    lo = min(fill) - timedelta(days=LOOKBACK_DAYS)
    parents = sorted(x for x in after if lo <= x <= max(fill))

    buckets = defaultdict(list)
    for d in parents:
        for table, rows in gen_day(d, M).items():
            for row in rows:
                p, e = row.pop("_P"), row.pop("_D")
                if p in after and e in after and not (p in loaded and e in loaded):
                    buckets[table].append(row)

    for table in sorted(buckets):
        n = c.write(pd.DataFrame(buckets[table]), table)
        print(f"  {table:<24} +{n:,}")
    c.write(pd.DataFrame([dict(LOAD_DATE=x, LOADED_AT=datetime.utcnow(), RUN_ID=run_id) for x in fill]),
            "GEN_LOAD_LOG")
    validate(c)


if __name__ == "__main__":
    main()
