# 🌱 PlantMyPlanet — Precision AI Garden Planner & Botanical Intelligence

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**PlantMyPlanet** is an end-to-end agro-ecological intelligence platform and personalized garden planner. By synthesizing **ISRIC SoilGrids** geospatial soil chemistry, **NASA POWER** decadal climatology, **Open-Meteo** high-resolution weather forecasts, **Laya** semantic feature classification, and the **FAO EcoCrop** database of 2,500+ crops, PlantMyPlanet provides mathematically verified crop recommendations and generates custom, microclimate-calibrated lifecycle plans powered by Large Language Models.

---

## 📑 Table of Contents
- [Architecture & Deep-Tech Pipeline](#-architecture--deep-tech-pipeline)
- [Key User Features](#-key-user-features)
- [Tech Stack](#-tech-stack)
- [Quick Start Guide](#-quick-start-guide)
  - [Prerequisites](#prerequisites)
  - [1. Clone Repository & Setup Environment](#1-clone-repository--setup-environment)
  - [2. Configure Secrets (.env)](#2-configure-secrets-env)
  - [3. Start PostgreSQL with Docker](#3-start-postgresql-with-docker)
  - [4. Ingest FAO EcoCrop Catalog](#4-ingest-fao-ecocrop-catalog)
  - [5. Run Development Server](#5-run-development-server)
  - [6. Execute Test Suite](#6-execute-test-suite)
- [API Reference](#-api-reference)
- [Security & Environment Variables](#-security--environment-variables)

---

## 🔬 Architecture & Deep-Tech Pipeline

```
              ┌────────────────────────────────────────────────────────┐
              │             User GPS Coordinates / Map Pin             │
              └──────────────────────────┬─────────────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
┌───────────────┐              ┌──────────────────┐              ┌──────────────────┐
│ISRIC SoilGrids│              │   NASA POWER     │              │   Open-Meteo     │
│  REST API     │              │  Climatology     │              │  Live Forecast   │
│ (0-5cm Depth) │              │  (10-Yr Rolling) │              │  (16-Day Window) │
└───────┬───────┘              └────────┬─────────┘              └────────┬─────────┘
        │ Clay, Sand, Silt,             │ Mean Temp (T2M),                │ Shortwave Solar
        │ SOC, Nitrogen, CEC,           │ Annual Rain (PRECTOTCORR),      │ Precip Sum/Peak,
        │ pH-H2O, CFVO                  │ Cloud Cover (CLOUD_AMT)         │ Elevation (m)
        └───────────────────────────────┼─────────────────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │    Laya Semantic Agro-Classification     │
                   │  Zero-Shot Vector Routing: TEXT/FER/DRA │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │ Deterministic Multi-Dimensional Matcher │
                   │ Hard Environmental Bounds + Score Weight│
                   │    FAO EcoCrop Database (2,568 Crops)   │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │   OpenRouter LLM Lifecycle Generator    │
                   │   4-5 Stage Actionable Plan + Tasks     │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │ Grounded Conversational Botanical Agent │
                   └─────────────────────────────────────────┘
```

### 1. Geospatial SoilGrids Rest Query & Layer Transformation
- Queries ISRIC SoilGrids 250m global raster layers at depth `0-5cm`.
- Dynamically parses layer metadata, applies `d_factor` unit normalization, and extracts:
  - **Clay, Sand, Silt** content (`g/kg` $\to$ `%`)
  - **Soil Organic Carbon (SOC)** (`dg/kg` $\to$ `g/kg`)
  - **pH in $H_2O$** (`pH*10` $\to$ raw pH)
  - **Cation Exchange Capacity (CEC)** (`mmol(c)/kg` $\to$ `cmol(c)/kg`)
  - **Nitrogen** & **Coarse Fragments (CFVO)** (`cm³/dm³`)

### 2. Decadal Climatological & Real-Time Meteorological Synthesis
- **NASA POWER Decadal Synthesis:** Queries multi-year agro-climatology across a 10-year rolling window to compute historical median daily precipitation (`PRECTOTCORR`), annual rainfall totals, surface temperatures (`T2M`), and daylight cloud distribution (`CLOUD_AMT`).
- **Open-Meteo High-Resolution Forecast:** Ingests live 16-day forecasting data including daily cumulative precipitation, precipitation peaks, shortwave solar radiation flux (`MJ/m²`), and topographical elevation.

### 3. Laya Semantic Agro-Feature Classification
- Leverages the **Laya semantic router** to map continuous environmental sensor telemetry into discrete EcoCrop agronomic categories:
  - **Soil Texture (`TEXT`):** Classified into `heavy`, `medium`, `light`, `organic`, or `wide`.
  - **Soil Fertility (`FER`):** Ranked into `high`, `moderate`, `low` based on nitrogen and CEC balance.
  - **Drainage Capacity (`DRA`):** Mapped into `well (dry spells)`, `poorly (saturated >50%)`, or `excessive`.
  - **Light Conditions (`LIOPMN`):** Synthesized from cloud fraction into `clear skies`, `very bright`, `light shade`, or `cloudy`.
- *Engineered with deterministic CPU-safe routing to eliminate GPU/Metal command buffer crashes across async thread pools.*

### 4. Deterministic Multi-Dimensional Candidate Ranking
- Performs strict SQL spatial & boundary pruning against the 2,568 cataloged crops in FAO EcoCrop:
  - Absolute latitude bounds: $\text{LATMN} \le |\text{lat}| \le \text{LATMX}$
  - Elevation ceiling: $\text{ALTMX} \ge \text{elevation}$
  - Temperature tolerance: $\text{TMIN} \le T_{2M} \le \text{TMAX}$
  - Annual precipitation tolerance: $\text{RMIN} \le \text{Rainfall} \le \text{RMAX}$
  - Absolute soil pH range: $\text{PHMIN} \le \text{pH} \le \text{PHMAX}$
- Computes an optimal suitability score ($0-100\%$) weighted by optimal intervals (`TOPMN`-`TOPMX`, `ROPMN`-`ROPMX`, `PHOPMN`-`PHOPMX`), soil texture compatibility, drainage matching, and solar radiation thresholds.
- Uses high-performance in-memory geographic caching for instantaneous response times.

### 5. Context-Grounded AI Lifecycle Generator & Botanical Advisor
- Generates tailored, 4–5 stage physiological timelines (Germination, Seedling Establishment, Vegetative Canopy, Flowering/Fruiting, Harvesting) calibrated to active planting dates and growing scale.
- Interactive Botanical Advisor equipped with active growth stage memory, accumulated growing degree metrics, and user-submitted field observations.

---

## 🌿 Key User Features

- **Intuitive Discovery Hub:** Search and filter hundreds of verified candidate crops by categories (*Vegetables*, *Fruits*, *Herbs & Spices*, *Medicinals*, *Grains & Cereals*) with suitability scores.
- **Deep Botanical Morphology Side Panel:** Full breakdown of plant life forms (*Herb*, *Shrub*, *Tree*, *Vine*), growth habits (*Erect*, *Spreading*, *Climbing*, *Prostrate*), lifecycle spans (*Annual*, *Perennial*, *Biennial*), cultivation settings (*Home Bed*, *Container*, *Greenhouse*), and root depth.
- **"Plant It Today" Workflow:** One-click initiation with custom plot scale selection (*Home Garden Bed*, *Patio Container*, *Greenhouse*, *Farm Plot*).
- **Interactive Garden Journal:**
  - Active planting cards showing days elapsed and current physiological stage.
  - Interactive checklists with real-time completion toggles for tasks and stages.
  - Estimated harvest countdown timeline.
- **Field Observation Logging:** Submit real-time notes on germination progress, pests, soil moisture, and leaf health.
- **Markdown-Rendered Botanical Companion Chat:** Chat directly with an AI agronomist that understands your plant's active stage, local microclimate, and field observations, styled with clean headings, bulleted lists, and actionable care instructions.
- **Modern Designer Aesthetics:** Built with a high-contrast neutral slate canvas (`#f8fafc`), crisp white cards, editorial **Playfair Display** typography, and structured color-coded metric badges (Amber, Violet, Sky Blue, Orange).

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn, SQLAlchemy 2.0, Pydantic V2
- **Database:** PostgreSQL 16 (via Docker Compose) with psycopg2
- **Machine Learning & NLP:** Laya Semantic Classifier, PyTorch, OpenRouter LLM (`anthropic/claude-3.5-sonnet` / `meta-llama/llama-3.3-70b-instruct`)
- **Geospatial & Climate APIs:** ISRIC SoilGrids REST API, NASA POWER Agroclimatology API, Open-Meteo Weather API
- **Frontend:** Vanilla HTML5, JavaScript (ES6+), Tailwind CSS (CDN), Marked.js, Material Symbols Outlined, Playfair Display & Plus Jakarta Sans Google Fonts
- **Security:** Bcrypt password hashing, PyJWT authentication tokens
- **Testing:** Pytest, HTTPX TestClient

---

## 🚀 Quick Start Guide

### Prerequisites
Make sure you have the following installed on your machine:
- **Python 3.10+** (Python 3.11, 3.12, 3.13, 3.14 supported)
- **Docker** and **Docker Compose**
- **Git**

---

### 1. Clone Repository & Setup Environment

```bash
# Clone the repository
git clone https://github.com/dkb73/plantTheplanet.git
cd plantTheplanet

# Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

### 2. Configure Secrets (.env)

Copy the sample environment file:

```bash
cp .env.example .env
```

Open `.env` in your text editor and provide your OpenRouter API key (or use the defaults for local testing):

```ini
POSTGRES_USER=plant
POSTGRES_PASSWORD=plant
POSTGRES_DB=planttheplanet
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# OpenRouter API Key for AI Plan Generation & Chat Advisor
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Secret key for JWT Token encoding
SECRET_KEY=garden-planner-secret-key-plantmyplanet
```

*(Note: If no OpenRouter API key is provided, the platform automatically switches to its deterministic agronomic planning fallback without crashing).*

---

### 3. Start PostgreSQL with Docker

Start the containerized PostgreSQL database:

```bash
docker compose up -d
```

Verify that the database container is healthy:

```bash
docker compose ps
```

---

### 4. Ingest FAO EcoCrop Catalog

Populate the database with the 2,568 crop species and agronomic criteria:

```bash
python db/ingest_ecocrop.py
```

*Expected output:*
```text
Connecting to PostgreSQL...
Loading data/data.csv...
Inserted 2568 rows into ecocrop table successfully!
```

---

### 5. Run Development Server

Start the FastAPI application with Uvicorn:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

### 6. Execute Test Suite

Run the automated integration test suite to verify all endpoints, database queries, and ML components:

```bash
pytest tests/test_backend.py -v
```

*All 4 test workflows should pass:*
- `test_health_check` ✅
- `test_auth_workflow` ✅
- `test_discovery_endpoints` ✅
- `test_planting_and_plan_workflow` ✅

---

## 📡 API Reference

All backend endpoints are prefixed with `/api/v1`. Interactive Swagger documentation is accessible at **[http://localhost:8000/docs](http://localhost:8000/docs)**.

### Authentication (`/api/v1/auth`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register new user account (email & password). |
| `POST` | `/auth/login` | Authenticate and obtain JWT access token. |
| `GET` | `/auth/me` | Fetch active user profile and preferences. |

### Plant Discovery (`/api/v1/discovery`)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/discovery/recommendations` | Calculate microclimate suitability score for coordinates. |
| `GET` | `/discovery/crops/{code}` | Retrieve complete botanical morphology & soil tolerances. |
| `GET` | `/discovery/categories` | Retrieve available crop category filters. |

### Plantings & Timelines (`/api/v1/plantings`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/plantings` | List all tracked plants for authenticated user. |
| `POST` | `/plantings` | Initiate "Plant It Today" and generate AI lifecycle plan. |
| `GET` | `/plantings/{id}` | Inspect stages, tasks, observations, and plan summary. |
| `PATCH` | `/plantings/stages/{id}/complete` | Toggle completion status of a growth stage. |
| `PATCH` | `/plantings/tasks/{id}/complete` | Toggle completion status of a specific care checklist task. |
| `POST` | `/plantings/{id}/observations` | Record text observation into plant field journal. |
| `POST` | `/plantings/{id}/retry-plan` | Regenerate personalized lifecycle plan with latest telemetry. |

### Botanical Companion Chat (`/api/v1/plantings/{id}/chat`)
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/plantings/{id}/chat` | Retrieve conversational message history for plant. |
| `POST` | `/plantings/{id}/chat` | Ask botanical questions grounded in active stage and weather. |

---

## 🔐 Security & Environment Variables

- **API Keys & Secrets:** `.env` is explicitly declared in `.gitignore` to prevent any credentials or keys from leaking into version control.
- **Sample Template:** A clean `.env.example` is committed to the repository with placeholders for onboarding.
- **Passwords:** All passwords are salted and hashed using **Bcrypt**.
- **Session Tokens:** Stateless **JWT (JSON Web Tokens)** are signed with HS256 and verified per request.
