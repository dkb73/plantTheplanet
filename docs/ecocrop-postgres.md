# EcoCrop Postgres cheat sheet

FAO EcoCrop crop parameters live in Postgres for local lookup. Source CSV: [OpenCLIM/ecocrop](https://github.com/OpenCLIM/ecocrop) (`EcoCrop_DB.csv`), copied to `data/data.csv`.

No ORM. Query with `psql` inside Docker, or pandas + `psycopg2` from the host.

---

## Layout

| Path | Role |
|------|------|
| `compose.yaml` | Postgres 16 container + named volume (keep at repo root so the existing volume still attaches) |
| `db/schema.sql` | `ecocrop` table (runs on **first** empty volume only) |
| `db/ingest_ecocrop.py` | Pandas cleanup + `COPY` into `ecocrop` |
| `data/data.csv` | Source rows (~2568) |
| `.env.example` | Copy to `.env` at repo root to override defaults |
| `soilgrid/` | SoilGrids REST client + `soilgrids.yaml` (unrelated to Postgres) |

Run Compose commands from the repo root (`PlantThePlanet`), where `compose.yaml` sits.

---

## Defaults

| Item | Value |
|------|--------|
| User | `plant` |
| Password | `plant` |
| Database | `planttheplanet` |
| Host (from your machine) | `localhost` |
| Port | `5432` |
| Table | `ecocrop` |
| Service name in Compose | `db` |

These match `POSTGRES_*` in `compose.yaml` / `.env.example`.

---

## Start, load, stop

```bash
docker compose up -d              # start Postgres (does not load CSV)
python db/ingest_ecocrop.py       # load / reload CSV (required at least once)
docker compose stop           # stop container; data stays
docker compose up -d          # start again; data still there
docker compose down           # remove container; volume (data) stays
docker compose down -v        # wipe volume → empty DB on next up
```

`up -d`: `-d` means **detached** (background), not database.

**Ingest is not automatic.** `up` only starts the server. Schema is created when the data volume is empty (`/docker-entrypoint-initdb.d/01_schema.sql`). Rows appear only after `python db/ingest_ecocrop.py`.

**Re-running ingest:** truncate then copy. No duplicates. Full replace from `data/data.csv`. If it dies after truncate and before copy, the table can be empty until you run it again.

**Stop/restart:** do **not** re-ingest. Data is on volume `postgres_data`. Re-ingest after `down -v` (or if you changed the CSV and want a reload).

**Ingest does not filter rows.** It only maps blanks/`NA`/`null` tokens to SQL `NULL`, then `COPY`s everything. The retry loop is “wait until Postgres is up,” not a data rule.

---

## Command templates

Two tools stacked: Compose runs a program **inside** the running `db` container; that program is `psql`.

```text
docker compose exec [exec-flags] <service> <program> [program-flags] [program-args]
```

```text
docker compose exec [-T] db psql -U <user> -d <database> [psql-flags]
```

Interactive (type SQL, quit with `\q`):

```bash
docker compose exec db psql -U plant -d planttheplanet
```

One-shot (PowerShell-friendly; `-T` = no TTY):

```bash
docker compose exec -T db psql -U plant -d planttheplanet -c "SELECT COUNT(*) FROM ecocrop;"
```

From a file:

```bash
docker compose exec -T db psql -U plant -d planttheplanet -f query.sql
```

If `psql` is installed on Windows (not required):

```bash
psql -h localhost -p 5432 -U plant -d planttheplanet
```

---

## Flag glossary

### `docker compose`

| Token | Meaning |
|--------|--------|
| `docker compose` | Read `compose.yaml` in the current directory |
| `exec` | Run a command in an **already running** container |
| `-T` | No TTY. Use for `-c` / `-f` / pipes. Omit for an interactive prompt |
| `db` | Service name (`services.db` in `compose.yaml`) |
| `up -d` | Create/start services in the background |
| `ps` | List services |
| `logs db` | Container logs |
| `down` | Stop and remove containers |
| `down -v` | Also delete named volumes (wipes the DB) |

### `psql`

| Flag | Long form | Meaning |
|------|-----------|--------|
| `-U plant` | `--username` | Role (must match `POSTGRES_USER`) |
| `-d planttheplanet` | `--dbname` | Database (must match `POSTGRES_DB`) |
| `-h localhost` | `--host` | Host. Omit inside the container (Unix socket) |
| `-p 5432` | `--port` | Port |
| `-c "SQL"` | `--command` | One statement, then exit |
| `-f file.sql` | `--file` | Run a file, then exit |
| `-W` | `--password` | Prompt for password |

Inside the container, local socket auth is typically trust, so `-U` is enough. From the host (pandas/`psql`), send user **and** password.

Inside `psql`: SQL ends with `;`. Meta-commands start with `\` and do not need `;`.

```text
\dt           list tables
\d ecocrop    table definition
\d+ ecocrop   definition + comments
\x auto       wrap wide rows
\q            quit
```

---

## This table: quoted column names

Columns were created quoted to match the CSV (`"EcoPortCode"`, `"TEXT"`, …). Postgres keeps mixed case. **Always double-quote column names.**

```sql
SELECT "ScientificName" FROM ecocrop;   -- works
SELECT ScientificName FROM ecocrop;     -- fails (folded to scientificname)
```

- Double quotes `"..."` → identifiers (table/column names)
- Single quotes `'...'` → string values

```sql
WHERE "CAT" = 'vegetables'    -- correct
WHERE "CAT" = "vegetables"    -- looks for a column named vegetables
```

`"TEXT"` is quoted because `TEXT` is also a Postgres type name (soil texture column).

---

## Lookups

### Head

Postgres: `LIMIT`, not SQL Server `TOP`.

```sql
SELECT * FROM ecocrop LIMIT 5;
```

### Particular columns

```sql
SELECT "EcoPortCode", "ScientificName", "TOPMN", "TOPMX", "TMIN", "TMAX"
FROM ecocrop
LIMIT 10;
```

### Filter

```sql
-- exact
SELECT "EcoPortCode", "ScientificName", "CAT"
FROM ecocrop
WHERE "ScientificName" = 'Abelmoschus esculentus';

-- substring (pandas str.contains)
SELECT "ScientificName", "CAT"
FROM ecocrop
WHERE "CAT" LIKE '%vegetables%';

-- case-insensitive (Postgres; MySQL LIKE is often already case-insensitive)
SELECT "ScientificName"
FROM ecocrop
WHERE "ScientificName" ILIKE '%wheat%';

-- numbers
SELECT "ScientificName", "TMIN", "TMAX"
FROM ecocrop
WHERE "TMIN" >= 10 AND "TMAX" <= 35;

-- missing (ingest stored blanks and NA as NULL)
SELECT COUNT(*) FROM ecocrop WHERE "KTMP" IS NULL;
SELECT COUNT(*) FROM ecocrop WHERE "KTMP" IS NOT NULL;
-- wrong: WHERE "KTMP" = NULL

WHERE "LIFO" IN ('herb', 'tree', 'shrub')
WHERE "GMIN" BETWEEN 50 AND 180
WHERE "TOPMN" IS NULL OR "TOPMN" >= 20
WHERE "PHOPMN" >= 5.5
```

---

## Pandas (optional)

```python
import pandas as pd
import psycopg2

conn = psycopg2.connect(
    host="localhost", port=5432,
    user="plant", password="plant", dbname="planttheplanet",
)
df = pd.read_sql('SELECT * FROM ecocrop LIMIT 5', conn)
df = pd.read_sql(
    'SELECT "ScientificName", "TOPMN" FROM ecocrop WHERE "CAT" ILIKE %s LIMIT 20',
    conn,
    params=["%vegetables%"],
)
conn.close()
```

Use `%s` + `params` when the filter is a variable.

Pandas analogues: `df.head(5)`, `df[["EcoPortCode", "ScientificName"]]`, `df[df["KTMP"].isna()]`.

---

## SQL you know → Postgres (what bites here)

| Habit | Postgres |
|--------|----------|
| `TOP 10` / `ROWNUM` | `LIMIT 10` (`OFFSET` to skip) |
| `"vegetables"` as a string | `'vegetables'` |
| Unquoted `ScientificName` | `"ScientificName"` on this table |
| Backticks `` `col` `` (MySQL) | `"col"` |
| `LIKE` case-insensitive | `ILIKE` or `LOWER(col) LIKE LOWER(...)` |
| `= NULL` | `IS NULL` / `IS NOT NULL` |
| Loose `'10' = 10` | Stricter casts (`SMALLINT`, `NUMERIC`, `REAL`) |
| Concat with `+` | `'a' \|\| 'b'` |
| Cast | `"TOPMN"::int` or `CAST("TOPMN" AS int)` |

Types in `db/schema.sql` (from a pandas profile of the CSV):

- `EcoPortCode` `INTEGER` PK
- Climate ints `SMALLINT` (temps, rain, altitude, `KTMP*`, `GMIN`/`GMAX`; killing temp can be negative)
- pH `NUMERIC(4,1)`
- `LAT*` `REAL` — numeric in the file, **not** clean latitude (values up to 2400)
- Everything else `TEXT`
- `TOPMN` has a **160** outlier in the source data

---

## Why ingest uses pandas at all

Postgres `COPY` accepts only **one** NULL token. The CSV uses both empty cells and `NA`. Pandas maps those to missing, writes empty fields, then:

```sql
COPY ecocrop FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')
```

See [COPY](https://www.postgresql.org/docs/current/sql-copy.html). Image/env: [postgres Docker Hub](https://hub.docker.com/_/postgres). PG 16 data dir: `/var/lib/postgresql/data` (PG 18 changed this; do not copy PG 18 volume paths onto this compose file).
