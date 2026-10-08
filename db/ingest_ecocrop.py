"""Load repo-root data/data.csv into the Docker Postgres `ecocrop` table.

FAO EcoCrop uses blank cells and the token NA for missing values.
COPY cannot treat both as NULL in one pass, so pandas normalizes first,
then Postgres COPY FROM STDIN loads the cleaned CSV.

COPY: https://www.postgresql.org/docs/current/sql-copy.html
"""

from __future__ import annotations

import os
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import psycopg2

_DB_DIR = Path(__file__).resolve().parent
CSV_PATH = _DB_DIR.parent / "data" / "data.csv"
SCHEMA_PATH = _DB_DIR / "schema.sql"

# Tokens that pandas should treat as missing (keep_default_na still catches NaN).
NA_VALUES = ["", "NA", "na", "NULL", "null", "None"]


def connect():
    """Retry until Postgres is accepting connections (compose healthcheck lag)."""
    cfg = dict(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "plant"),
        password=os.getenv("POSTGRES_PASSWORD", "plant"),
        dbname=os.getenv("POSTGRES_DB", "planttheplanet"),
    )
    last = None
    for _ in range(30):
        try:
            return psycopg2.connect(**cfg)
        except psycopg2.OperationalError as exc:
            last = exc
            time.sleep(1)
    raise last


def main() -> None:
    # dtype=str then to_numeric in COPY: let Postgres cast using the table types.
    df = pd.read_csv(
        CSV_PATH,
        encoding="utf-8",
        dtype=str,
        keep_default_na=True,
        na_values=NA_VALUES,
    )
    print(f"read {len(df)} rows, {len(df.columns)} columns from {CSV_PATH}")

    buf = StringIO()
    df.to_csv(buf, index=False, na_rep="")  # empty field -> SQL NULL via COPY NULL ''
    buf.seek(0)

    conn = connect()
    conn.autocommit = True
    with conn, conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        cur.execute("TRUNCATE ecocrop")
        # HEADER true matches CSV column names to table columns.
        # NULL '' turns the empty cells we just wrote into SQL NULL.
        cur.copy_expert(
            """
            COPY ecocrop FROM STDIN WITH (
                FORMAT csv,
                HEADER true,
                NULL ''
            )
            """,
            buf,
        )
        cur.execute("SELECT COUNT(*) FROM ecocrop")
        n = cur.fetchone()[0]
    conn.close()
    print(f"loaded {n} rows into ecocrop")


if __name__ == "__main__":
    main()
