"""Maintainer-only: export every RAW table to data/raw/<TABLE>.parquet so customers can skip the generator.

Usage:  python setup/export_raw.py
Run after `python generator/generate.py` + `dbt build`. Uses the same connection logic as the generator.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generator"))
from generate import Conn  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")
STAGE = "@~/ironclad_raw_export"


def main():
    c = Conn()
    tables = [r[0] for r in c.sql("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                                  "WHERE TABLE_SCHEMA = 'RAW' AND TABLE_TYPE = 'BASE TABLE' ORDER BY 1")]
    os.makedirs(OUT, exist_ok=True)
    c.sql(f"REMOVE {STAGE}")
    tmp = tempfile.mkdtemp()
    for t in tables:
        c.sql(f"COPY INTO {STAGE}/{t}.parquet FROM RAW.{t} FILE_FORMAT = (TYPE = PARQUET) "
              f"HEADER = TRUE SINGLE = TRUE OVERWRITE = TRUE MAX_FILE_SIZE = 268435456")
        c.sql(f"GET {STAGE}/{t}.parquet 'file://{tmp}/'")
        shutil.move(os.path.join(tmp, f"{t}.parquet"), os.path.join(OUT, f"{t}.parquet"))
        print(f"  {t}")
    c.sql(f"REMOVE {STAGE}")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Exported {len(tables)} tables to {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
