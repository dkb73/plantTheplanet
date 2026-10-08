-- EcoCrop land-use table.
-- Types come from pandas profiling of data/data.csv (2568 rows, 55 cols).
-- Column names stay as in the CSV (quoted) so COPY HEADER can match them.
-- Blanks and the token NA are missing; ingest.py turns both into SQL NULL.
-- "TEXT" is quoted because TEXT is a Postgres type name.

CREATE TABLE IF NOT EXISTS ecocrop (
    "EcoPortCode"    INTEGER PRIMARY KEY,   -- 289 .. 400004, unique, never null
    "ScientificName" TEXT NOT NULL,         -- max 46 chars, unique in this file
    "AUTH"           TEXT,                  -- max 63; 212 missing
    "FAMNAME"        TEXT,                  -- max 59; 182 missing
    "SYNO"           TEXT,                  -- max 1024; mostly empty
    "COMNAME"        TEXT,                  -- max 1023; 913 missing

    "LIFO"           TEXT,                  -- 19 values, max 22
    "HABI"           TEXT,                  -- 10 values, max 65
    "LISPA"          TEXT,                  -- 7 values, max 27
    "PHYS"           TEXT,                  -- 45 values, max 72
    "CAT"            TEXT,                  -- 314 values, max 121
    "PLAT"           TEXT,                  -- 12 values, max 66

    "TOPMN"          SMALLINT,              -- C; 5 .. 160 (160 is an outlier); 497 missing
    "TOPMX"          SMALLINT,              -- 14 .. 45
    "TMIN"           SMALLINT,              -- 2 .. 25
    "TMAX"           SMALLINT,              -- 13 .. 58

    "ROPMN"          SMALLINT,              -- mm; 125 .. 9000
    "ROPMX"          SMALLINT,              -- 100 .. 12000
    "RMIN"           SMALLINT,              -- 50 .. 3000
    "RMAX"           SMALLINT,              -- 250 .. 9900

    "PHOPMN"         NUMERIC(4, 1),         -- 4.0 .. 8.0
    "PHOPMX"         NUMERIC(4, 1),         -- 4.5 .. 10.0
    "PHMIN"          NUMERIC(4, 1),         -- 2.7 .. 7.5
    "PHMAX"          NUMERIC(4, 1),         -- 5.0 .. 10.5

    -- LAT* is numeric in the file but not clean latitude (values up to 2400)
    "LATOPMN"        REAL,                  -- 1 .. 700; many NA
    "LATOPMX"        REAL,                  -- 1 .. 700
    "LATMN"          REAL,                  -- 2 .. 2400
    "LATMX"          REAL,                  -- 2 .. 2200
    "ALTMX"          SMALLINT,              -- m; 20 .. 6000

    "LIOPMN"         TEXT,                  -- 5 light labels, max 12
    "LIOPMX"         TEXT,
    "LIMN"           TEXT,
    "LIMX"           TEXT,
    "DEP"            TEXT,                  -- 4 depth labels, max 21
    "DEPR"           TEXT,
    "TEXT"           TEXT,                  -- soil texture lists, max 35
    "TEXTR"          TEXT,
    "FER"            TEXT,                  -- high | moderate | low
    "FERR"           TEXT,
    "TOX"            TEXT,                  -- mostly empty
    "TOXR"           TEXT,
    "SAL"            TEXT,                  -- max 18
    "SALR"           TEXT,
    "DRA"            TEXT,                  -- max 82
    "DRAR"           TEXT,

    "KTMPR"          SMALLINT,              -- C; -50 .. 14; 1411 missing
    "KTMP"           SMALLINT,              -- -20 .. 14

    "PHOTO"          TEXT,                  -- max 70
    "CLIZ"           TEXT,                  -- max 290
    "ABITOL"         TEXT,                  -- max 72
    "ABISUS"         TEXT,                  -- max 34
    "INTRI"          TEXT,                  -- max 58
    "PROSY"          TEXT,                  -- max 86

    "GMIN"           SMALLINT,              -- days; 0 .. 365; 2 missing
    "GMAX"           SMALLINT               -- 0 .. 365; 2 missing
);
