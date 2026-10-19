"""Master data for the Ironclad Tire & Rubber Co. demo (fictional company).

Everything here is deterministic (fixed seed), so keys never change between runs.
The only intentional drift is customer credit limits (KNA1.KLIMK), which change by
ISO week so a dbt snapshot has real SCD2 history to capture.
"""
import math
import zlib
from datetime import date

import numpy as np
import pandas as pd

SEED = 20261018


def crc(s: str) -> int:
    return zlib.crc32(s.encode())


def rng_for(*parts) -> np.random.Generator:
    return np.random.default_rng([SEED] + [p if isinstance(p, int) else crc(str(p)) for p in parts])


COMPANY_CODES = [
    # BUKRS, name, country, currency
    ("1000", "Ironclad Tire & Rubber Co.", "US", "USD"),
    ("2000", "Ironclad Llantas de Mexico S.A. de C.V.", "MX", "MXN"),
    ("3000", "Ironclad Reifen GmbH", "DE", "EUR"),
]
CURRENCY_BY_BUKRS = {c[0]: c[3] for c in COMPANY_CODES}

PLANTS = [
    # WERKS, name, city, region, country, BUKRS, lat, lon, volume weight
    # Fictional towns; coordinates are approximate regional placeholders, not real plant sites.
    ("P100", "Ridgeport Tire Plant", "Ridgeport", "OH", "US", "1000", 40.40, -82.50, 0.24),
    ("P200", "Cedar Bluff Tire Plant", "Cedar Bluff", "OK", "US", "1000", 35.75, -96.60, 0.18),
    ("P300", "Hollis Commercial Tire Plant", "Hollis", "VA", "US", "1000", 37.30, -78.40, 0.14),
    ("P400", "Valle Alto Tire Plant", "Valle Alto", "DUR", "MX", "2000", 24.03, -104.65, 0.16),
    ("P500", "Rheinfeld Tire Plant", "Rheinfeld", "RP", "DE", "3000", 49.60, 7.70, 0.14),
    ("P600", "Pine Hollow Tire Plant", "Pine Hollow", "NC", "US", "1000", 35.70, -80.20, 0.14),
]
PLANT = {p[0]: dict(zip(["WERKS", "NAME1", "ORT01", "REGIO", "LAND1", "BUKRS", "LAT", "LON", "W"], p)) for p in PLANTS}

# MATNR, description, category, UoM, base price USD per UoM, kg per UoM
RAW_MATERIALS = [
    ("RM-NR-001", "Natural Rubber TSR20", "Natural Rubber", "KG", 1.72, 1.0),
    ("RM-NR-002", "Natural Rubber RSS3", "Natural Rubber", "KG", 1.95, 1.0),
    ("RM-SBR-001", "Emulsion SBR 1502", "Synthetic Rubber", "KG", 2.10, 1.0),
    ("RM-SBR-002", "Solution SBR (Low Rolling Resistance)", "Synthetic Rubber", "KG", 2.85, 1.0),
    ("RM-BR-001", "High-cis Polybutadiene BR", "Synthetic Rubber", "KG", 2.40, 1.0),
    ("RM-CB-N234", "Carbon Black N234 (Tread Grade)", "Carbon Black", "KG", 1.28, 1.0),
    ("RM-CB-N330", "Carbon Black N330", "Carbon Black", "KG", 1.15, 1.0),
    ("RM-CB-N550", "Carbon Black N550 (Carcass Grade)", "Carbon Black", "KG", 1.08, 1.0),
    ("RM-SIL-001", "Highly Dispersible Precipitated Silica", "Silica", "KG", 1.60, 1.0),
    ("RM-SC-001", "Steel Cord 3x0.20+6x0.35 HT", "Steel Cord", "KG", 2.95, 1.0),
    ("RM-SC-002", "Steel Cord 2+2x0.25 NT", "Steel Cord", "KG", 2.70, 1.0),
    ("RM-BW-001", "Bronze-coated Bead Wire 1.0mm", "Bead Wire", "KG", 1.85, 1.0),
    ("RM-NY-001", "Nylon 66 Cap Ply Fabric", "Textiles", "M2", 3.40, 0.35),
    ("RM-PE-001", "Polyester Body Ply Fabric", "Textiles", "M2", 2.60, 0.40),
    ("RM-CH-ZNO", "Zinc Oxide", "Chemicals", "KG", 3.10, 1.0),
    ("RM-CH-SUL", "Insoluble Sulfur", "Chemicals", "KG", 1.45, 1.0),
    ("RM-CH-6PPD", "6PPD Antiozonant", "Chemicals", "KG", 4.80, 1.0),
    ("RM-CH-TBBS", "TBBS Accelerator", "Chemicals", "KG", 5.20, 1.0),
    ("RM-CH-STA", "Stearic Acid", "Chemicals", "KG", 1.30, 1.0),
    ("RM-OIL-TDAE", "TDAE Process Oil", "Process Oil", "KG", 1.05, 1.0),
    ("RM-RES-001", "Tackifying Phenolic Resin", "Resins", "KG", 3.90, 1.0),
    ("RM-MRO-001", "Curing Bladder (Passenger)", "MRO", "EA", 185.00, 6.0),
    ("RM-MRO-002", "Semi-permanent Mold Release Agent", "MRO", "EA", 62.00, 20.0),
    ("RM-MRO-003", "Curing Press Hydraulic Seal Kit", "MRO", "EA", 410.00, 4.0),
]

TIRE_LINES = [
    # line, segment tag, sizes, base price USD, kg
    ("TrailMaster AT", "LT", ["265/70R17", "275/65R18", "285/70R17"], 205.0, 22.0),
    ("UrbanGlide Touring", "PC", ["205/55R16", "215/60R16", "225/65R17"], 118.0, 10.0),
    ("PerformaSport UHP", "PC", ["225/45R18", "245/40R19", "255/35R20"], 189.0, 11.5),
    ("WinterGrip Ice", "PC", ["205/55R16", "225/65R17"], 142.0, 10.5),
    ("HaulPro Steer", "CT", ["295/75R22.5", "11R22.5"], 398.0, 52.0),
    ("HaulPro Drive", "CT", ["295/75R22.5", "11R22.5"], 425.0, 56.0),
    ("EcoVolt EV", "PC", ["235/45R19", "255/45R20"], 236.0, 13.0),
]


def finished_goods():
    out = []
    for i, (line, seg, sizes, price, kg) in enumerate(TIRE_LINES):
        for j, size in enumerate(sizes):
            matnr = f"FG-{seg}-{i + 1:02d}{j + 1:02d}"
            out.append((matnr, f"Ironclad {line} {size}", f"Tire - {seg}", "EA", round(price * (1 + 0.06 * j), 2), kg, line, size))
    return out


SUPPLIERS = [
    # LIFNR, name, country, city, categories, on-time base, reject base, price bias
    ("0000100001", "Equatorial Rubber Holdings", "MY", "Kuala Lumpur", ["Natural Rubber"], 0.88, 0.010, 0.00),
    ("0000100002", "Siam Latex Trading Co.", "TH", "Bangkok", ["Natural Rubber"], 0.82, 0.020, -0.02),
    ("0000100003", "Cote d'Ivoire Hevea Export", "CI", "Abidjan", ["Natural Rubber"], 0.74, 0.035, -0.05),
    ("0000100004", "Gulf Coast Elastomers", "US", "Baton Rouge", ["Synthetic Rubber"], 0.93, 0.008, 0.01),
    ("0000100005", "Rhein Polymer Werke AG", "DE", "Ludwigshafen", ["Synthetic Rubber", "Chemicals"], 0.95, 0.005, 0.03),
    ("0000100006", "Meridian Carbon Solutions", "US", "Borger", ["Carbon Black"], 0.93, 0.010, -0.01),
    ("0000100007", "Atlas Carbon Black Ltd.", "US", "Pampa", ["Carbon Black"], 0.90, 0.014, 0.03),
    ("0000100008", "Negro de Humo del Norte", "MX", "Monterrey", ["Carbon Black"], 0.85, 0.020, -0.03),
    ("0000100009", "Northstar Silica Corp.", "US", "Augusta", ["Silica"], 0.94, 0.006, 0.02),
    ("0000100010", "Kestrel Steel Cord Inc.", "US", "Rome", ["Steel Cord", "Bead Wire"], 0.90, 0.010, 0.04),
    ("0000100011", "Lakeshore Industrial Textiles", "US", "Spartanburg", ["Textiles"], 0.89, 0.012, 0.00),
    ("0000100012", "Bavaria Technische Gewebe GmbH", "DE", "Augsburg", ["Textiles"], 0.93, 0.007, 0.02),
    ("0000100013", "Pinnacle Specialty Chemicals", "US", "Canton", ["Chemicals"], 0.92, 0.009, 0.01),
    ("0000100014", "Quimica Industrial del Bajio", "MX", "Leon", ["Chemicals", "Process Oil"], 0.84, 0.020, -0.04),
    ("0000100015", "Harborline Petroleum Products", "US", "Houston", ["Process Oil"], 0.90, 0.010, 0.00),
    ("0000100016", "Resinex Performance Materials", "DE", "Marl", ["Resins", "Chemicals"], 0.94, 0.006, 0.03),
    ("0000100017", "Midwest MRO Supply", "US", "Cleveland", ["MRO"], 0.87, 0.015, 0.05),
    ("0000100018", "Precision Bladder Technologies", "US", "Lima", ["MRO"], 0.85, 0.020, 0.02),
    ("0000100019", "Iberia Steel Wire S.L.", "ES", "Bilbao", ["Bead Wire"], 0.88, 0.012, 0.01),
    ("0000100020", "Sumatra Agro Rubber", "ID", "Medan", ["Natural Rubber"], 0.80, 0.025, -0.04),
]
DETERIORATING_SUPPLIER = "0000100006"   # Meridian: on-time drops from DECLINE_LEAD_DAYS before the run date
DECLINE_LEAD_DAYS = 110
SUPPLIER_LEAD_DAYS = {"US": (5, 10), "MX": (7, 12), "DE": (6, 12), "ES": (25, 35), "MY": (38, 50),
                      "TH": (38, 52), "CI": (40, 55), "ID": (40, 55)}

OEMS = [("Northfield Motors", "US", "Detroit", "MI"), ("Cascade Automotive Group", "US", "Smyrna", "TN"),
        ("Valtor Trucks", "US", "Greensboro", "NC"), ("Aurelia Motor Works", "US", "Spartanburg", "SC"),
        ("Pacifica EV Corp", "US", "Fremont", "CA"), ("Ironwood Heavy Equipment", "US", "Peoria", "IL"),
        ("Autos Sierra Madre S.A.", "MX", "Saltillo", "COA"), ("Kronberg Fahrzeugbau AG", "DE", "Stuttgart", "BW")]
US_CITIES = [("Columbus", "OH"), ("Dallas", "TX"), ("Houston", "TX"), ("Phoenix", "AZ"), ("Denver", "CO"),
             ("Atlanta", "GA"), ("Nashville", "TN"), ("Charlotte", "NC"), ("Indianapolis", "IN"), ("Omaha", "NE"),
             ("Tulsa", "OK"), ("Memphis", "TN"), ("Louisville", "KY"), ("Kansas City", "MO"), ("St. Louis", "MO"),
             ("Milwaukee", "WI"), ("Minneapolis", "MN"), ("Boise", "ID"), ("Salt Lake City", "UT"), ("Reno", "NV"),
             ("Sacramento", "CA"), ("Fresno", "CA"), ("Portland", "OR"), ("Spokane", "WA"), ("Albuquerque", "NM"),
             ("El Paso", "TX"), ("San Antonio", "TX"), ("Jacksonville", "FL"), ("Tampa", "FL"), ("Richmond", "VA"),
             ("Pittsburgh", "PA"), ("Buffalo", "NY"), ("Hartford", "CT"), ("Birmingham", "AL"), ("Little Rock", "AR")]
MX_CITIES = [("Monterrey", "NL"), ("Guadalajara", "JAL"), ("Queretaro", "QRO"), ("Puebla", "PUE"), ("Leon", "GUA")]
DE_CITIES = [("Frankfurt", "HE"), ("Koeln", "NW"), ("Hamburg", "HH"), ("Muenchen", "BY"), ("Leipzig", "SN")]
DEALER_SUFFIX = ["Tire & Auto", "Tire Center", "Wheel & Tire", "Tire Pros", "Auto Service", "Discount Tire Depot"]
FLEET_PREFIX = ["Blue Ridge", "Lone Star", "Great Lakes", "Red Rock", "Silverline", "Prairie", "Coastal", "Summit",
                "Granite", "Evergreen", "Keystone", "Frontier", "Harbor", "Canyon", "Iron Horse", "Pioneer"]
FLEET_SUFFIX = ["Logistics", "Freight Lines", "Transport", "Haulers", "Fleet Services"]
TERMS_BY_SEGMENT = {"OEM": ("NT60", 60), "DEALER": ("NT30", 30), "FLEET": ("NT45", 45)}
DISCOUNT_BY_SEGMENT = {"OEM": 0.18, "DEALER": 0.0, "FLEET": 0.08}


def haversine_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, [a["LAT"], a["LON"], b["LAT"], b["LON"]])
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


class Master:
    """Builds all master data tables plus lookup structures used by the daily generator."""

    def __init__(self, today: date):
        r = rng_for("master")
        self.plants = PLANT
        self.plant_ids = [p[0] for p in PLANTS]
        self.plant_w = np.array([p[8] for p in PLANTS]) / sum(p[8] for p in PLANTS)

        # Materials
        self.mat = {}
        for m in RAW_MATERIALS:
            self.mat[m[0]] = dict(MATNR=m[0], MAKTX=m[1], MATKL=m[2], MTART="ROH", MEINS=m[3], BASE_PRICE_USD=m[4],
                                  NTGEW_KG=m[5], PRODUCT_LINE="", TIRE_SIZE="")
        for m in finished_goods():
            self.mat[m[0]] = dict(MATNR=m[0], MAKTX=m[1], MATKL=m[2], MTART="FERT", MEINS=m[3], BASE_PRICE_USD=m[4],
                                  NTGEW_KG=m[5], PRODUCT_LINE=m[6], TIRE_SIZE=m[7])
        self.raw_ids = [m[0] for m in RAW_MATERIALS]
        self.fg_ids = [k for k, v in self.mat.items() if v["MTART"] == "FERT"]

        # Plant/material settings (MARC). Every plant stocks every raw material (except
        # P300 which builds commercial tires only); FG is produced at 2-3 plants.
        self.marc = {}
        self.fg_plants = {}
        for m in self.raw_ids:
            for w in self.plant_ids:
                if w == "P300" and m in ("RM-SBR-002", "RM-SIL-001", "RM-NY-001"):
                    continue
                uom = self.mat[m]["MEINS"]
                scale = PLANT[w]["W"] / 0.16
                minbe = (r.integers(8, 60) * 1000 if uom in ("KG", "M2") else r.integers(10, 60)) * scale
                self.marc[(w, m)] = dict(WERKS=w, MATNR=m, MINBE=round(float(minbe), 0),
                                         EISBE=round(float(minbe) * 0.4, 0), PLIFZ=int(r.integers(5, 15)),
                                         DISMM="VB", BESKZ="F")
        for m in self.fg_ids:
            pool = ["P300", "P400", "P100"] if "-CT-" in m else [w for w in self.plant_ids if w != "P300"]
            k = 2 if "-CT-" in m else int(r.integers(2, 4))
            plants = list(r.choice(pool, size=min(k, len(pool)), replace=False))
            if "-CT-" not in m and "P500" not in plants and r.random() < 0.5:
                plants.append("P500")
            self.fg_plants[m] = plants
            for w in plants:
                minbe = float(r.integers(5, 40) * 100)
                self.marc[(w, m)] = dict(WERKS=w, MATNR=m, MINBE=minbe, EISBE=round(minbe * 0.35, 0),
                                         PLIFZ=int(r.integers(2, 6)), DISMM="VB", BESKZ="E")
        self.raw_at_plant = {w: [m for m in self.raw_ids if (w, m) in self.marc] for w in self.plant_ids}

        # Suppliers and purchasing info records (EINA/EINE combined)
        self.sup = {}
        for s in SUPPLIERS:
            self.sup[s[0]] = dict(LIFNR=s[0], NAME1=s[1], LAND1=s[2], ORT01=s[3], CATEGORIES=s[4], OT=s[5],
                                  REJ=s[6], BIAS=s[7])
        self.eina = []
        self.eina_by_mat, self.eina_by_sup = {}, {}
        for m in self.raw_ids:
            cat = self.mat[m]["MATKL"]
            cands = [s for s in SUPPLIERS if cat in s[4]]
            # carbon black: Meridian is the primary source for tread grade
            primary = "0000100006" if m == "RM-CB-N234" else cands[int(r.integers(0, len(cands)))][0]
            for s in cands:
                lo, hi = SUPPLIER_LEAD_DAYS[s[2]]
                rec = dict(INFNR=f"53{len(self.eina) + 1:08d}", LIFNR=s[0], MATNR=m,
                           NETPR_USD=round(self.mat[m]["BASE_PRICE_USD"] * (1 + s[7] + r.normal(0, 0.02)), 4),
                           APLFZ=int(r.integers(lo, hi + 1)), IS_PRIMARY=s[0] == primary,
                           VALID_FROM=date(2025, 1, 1), VALID_TO=date(2027, 12, 31))
                self.eina.append(rec)
                self.eina_by_mat.setdefault(m, []).append(rec)
                self.eina_by_sup.setdefault(s[0], []).append(rec)

        # Customers
        self.cust = {}
        n = 0

        def add(name, seg, land, city, regio, w):
            nonlocal n
            n += 1
            kunnr = f"{200000 + n:010d}"
            bukrs = {"US": "1000", "MX": "2000", "DE": "3000"}[land]
            self.cust[kunnr] = dict(KUNNR=kunnr, NAME1=name, SEGMENT=seg, LAND1=land, ORT01=city, REGIO=regio,
                                    BUKRS=bukrs, ZTERM=TERMS_BY_SEGMENT[seg][0], TERMS_DAYS=TERMS_BY_SEGMENT[seg][1],
                                    W=w, BASE_KLIMK=float({"OEM": 5_000_000, "DEALER": 150_000, "FLEET": 600_000}[seg]
                                                          * r.uniform(0.6, 1.6)),
                                    ERDAT=date(2015, 1, 1) + pd.Timedelta(days=int(r.integers(0, 3500))).to_pytimedelta())
        for name, land, city, regio in OEMS:
            add(name, "OEM", land, city, regio, 6.0)
        used = set()
        for city, regio in US_CITIES + MX_CITIES + DE_CITIES:
            for _ in range(int(r.integers(2, 4))):
                suf = DEALER_SUFFIX[int(r.integers(0, len(DEALER_SUFFIX)))]
                if suf == "Tire Pros" and (city, regio) in MX_CITIES:
                    suf = "Llantas y Servicio"
                if (city, regio) in DE_CITIES:
                    suf = "Reifen Service"
                nm = f"{city} {suf}"
                if nm in used:
                    continue
                used.add(nm)
                land = "MX" if (city, regio) in MX_CITIES else "DE" if (city, regio) in DE_CITIES else "US"
                add(nm, "DEALER", land, city, regio, 1.0)
        for i in range(40):
            nm = f"{FLEET_PREFIX[i % len(FLEET_PREFIX)]} {FLEET_SUFFIX[(i * 7) % len(FLEET_SUFFIX)]}"
            if nm in used:
                continue
            used.add(nm)
            city, regio = US_CITIES[int(r.integers(0, len(US_CITIES)))]
            add(nm, "FLEET", "US", city, regio, 2.0)
        self.cust_ids = list(self.cust)
        w = np.array([self.cust[k]["W"] for k in self.cust_ids])
        self.cust_w = w / w.sum()
        # Hidden payment behavior (not exposed in KNA1): a few slow payers drive the AR story
        self.pay_profile = {k: (2.0, 6.0) for k in self.cust_ids}
        dealers = [k for k in self.cust_ids if self.cust[k]["SEGMENT"] == "DEALER"]
        fleets = [k for k in self.cust_ids if self.cust[k]["SEGMENT"] == "FLEET"]
        slow = [k for k in self.cust_ids if self.cust[k]["NAME1"] == "Valtor Trucks"] + [fleets[3], dealers[5], dealers[23]]
        for k in slow:
            self.pay_profile[k] = (55.0, 15.0)
        for k in self.cust_ids[::11]:
            if k not in slow:
                self.pay_profile[k] = (14.0, 8.0)   # moderately late
        self.slow_payers = slow
        self.today = today

        # Plant-to-plant lanes (WMS)
        self.lanes = {}
        for a in self.plant_ids:
            for b in self.plant_ids:
                if a == b:
                    continue
                pa, pb = PLANT[a], PLANT[b]
                km = haversine_km(pa, pb)
                ocean = pa["LAND1"] == "DE" or pb["LAND1"] == "DE"
                border = pa["LAND1"] != pb["LAND1"]
                transit = (18 + int(km // 2500)) if ocean else 1 + math.ceil(km / 700) + (2 if border else 0)
                cost = 0.05 + km * 0.000045 + (0.12 if ocean else 0.04 if border else 0)
                self.lanes[(a, b)] = dict(LANE_ID=f"L-{a}-{b}", FROM_PLANT=a, TO_PLANT=b, DISTANCE_KM=round(km, 1),
                                          MODE="OCEAN+TRUCK" if ocean else "TRUCK", TRANSIT_DAYS=int(transit),
                                          COST_PER_KG_USD=round(cost, 4), HANDLING_FEE_USD=350.0 if ocean else 120.0)

    # ---- table builders -------------------------------------------------
    def tables(self):
        iso_week = self.today.isocalendar()[1]
        kna1 = []
        for k, c in self.cust.items():
            klimk = c["BASE_KLIMK"]
            if crc(k) % 7 == 0:   # ~15% of customers get weekly credit reviews
                klimk *= 1 + 0.25 * ((iso_week + crc(k)) % 3 - 1)
            kna1.append(dict(KUNNR=k, NAME1=c["NAME1"], ORT01=c["ORT01"], REGIO=c["REGIO"], LAND1=c["LAND1"],
                             KTOKD={"OEM": "ZOEM", "DEALER": "ZDLR", "FLEET": "ZFLT"}[c["SEGMENT"]],
                             BUKRS=c["BUKRS"], ZTERM=c["ZTERM"], KLIMK=round(klimk, -3),
                             ERDAT=c["ERDAT"], LOADED_AT=pd.Timestamp.utcnow().tz_localize(None)))
        return {
            "T001": pd.DataFrame([dict(BUKRS=b, BUTXT=n, LAND1=l, WAERS=w) for b, n, l, w in COMPANY_CODES]),
            "T001W": pd.DataFrame([{k: v for k, v in p.items() if k != "W"} for p in PLANT.values()]),
            "MARA": pd.DataFrame(list(self.mat.values())),
            "MARC": pd.DataFrame(list(self.marc.values())),
            "LFA1": pd.DataFrame([dict(LIFNR=s["LIFNR"], NAME1=s["NAME1"], LAND1=s["LAND1"], ORT01=s["ORT01"],
                                       KTOKK="ZRAW" if s["CATEGORIES"] != ["MRO"] else "ZMRO",
                                       PRIMARY_CATEGORY=s["CATEGORIES"][0]) for s in self.sup.values()]),
            "EINA": pd.DataFrame(self.eina),
            "KNA1": pd.DataFrame(kna1),
            "WMS_TRANSFER_LANES": pd.DataFrame(list(self.lanes.values())),
        }
