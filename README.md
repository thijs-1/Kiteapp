# Kiteapp

A kitesurfing application to identify optimal surfing locations based on historical wind data from the Copernicus Climate Data Store (ERA5).

## Overview

The app has three main components:
- **Data Pipelines**: Downloads and processes 10 years of wind data for ~9,600 kite spots worldwide
- **Backend**: FastAPI REST API serving filtered spots and wind statistics
- **Frontend**: Interactive map with filters and charts

## Prerequisites

- Python 3.10+
- Node.js 18+
- Copernicus CDS API account and credentials

### CDS API Setup

1. Register at https://cds.climate.copernicus.eu
2. Get your API key from your profile page
3. Create `~/.cdsapirc` (or `%USERPROFILE%\.cdsapirc` on Windows):
```
url: https://cds.climate.copernicus.eu/api
key: <your-uid>:<your-api-key>
```

## Installation

### Backend & Data Pipelines

```bash
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Running the Application

### 1. Enrich Spots Data (one-time)

This adds country information to the kite spots:

```bash
.\venv\Scripts\python -m data_pipelines.enrich_spots
```

### 2. Run Data Pipeline

Download and process wind data from CDS:

```bash
# Test with 1 grid cell first
.\venv\Scripts\python -m data_pipelines.main --max-cells 1

# Run full pipeline with cleanup (recommended - saves disk space)
.\venv\Scripts\python -m data_pipelines.main --cleanup

# Force re-download and re-process
.\venv\Scripts\python -m data_pipelines.main --force-download --force-process --cleanup
```

**Pipeline Options:**
| Flag | Description |
|------|-------------|
| `--max-cells N` | Process only N grid cells (for testing) |
| `--cleanup` | Delete raw NetCDF files after processing (~3GB saved per cell) |
| `--force-download` | Re-download even if files exist |
| `--force-process` | Re-process spots even if histograms exist |

**Disk Space Requirements:**
| With --cleanup | Without --cleanup |
|----------------|-------------------|
| ~4 GB during processing | ~120-160 GB |
| ~8 GB final output | ~8 GB final output |

### 3. Start Backend

```bash
.\venv\Scripts\uvicorn backend.main:app --reload
```

The API will be available at http://localhost:8000

API Documentation: http://localhost:8000/docs

### 4. Start Frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

The app will be available at http://localhost:5173

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /spots` | Get filtered spots |
| `GET /spots/all` | Get all spots without filtering |
| `GET /spots/countries` | Get list of countries |
| `GET /spots/{id}` | Get single spot |
| `GET /spots/{id}/histograms/daily` | Get daily wind histograms |
| `GET /spots/{id}/histograms/moving-average` | Get smoothed histograms |
| `GET /spots/{id}/histograms/kiteable-percentage` | Get daily kiteable % |
| `GET /spots/{id}/windrose` | Get wind rose data |

**Filter Parameters for `/spots`:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `wind_min` | 0 | Minimum wind speed (knots) |
| `wind_max` | 100 | Maximum wind speed (100 = infinity) |
| `start_date` | 01-01 | Start date (MM-DD) |
| `end_date` | 12-31 | End date (MM-DD) |
| `country` | - | Filter by country code |
| `name` | - | Filter by spot name |
| `min_percentage` | 75 | Minimum kiteable percentage |

## Project Structure

```
Kiteapp3/
├── data_pipelines/          # Wind data processing
│   ├── config.py            # Constants and paths
│   ├── enrich_spots.py      # Add country to spots
│   ├── main.py              # Pipeline orchestrator
│   ├── models/              # Data models
│   ├── services/            # Business logic
│   └── utils/               # Utilities
│
├── backend/                 # FastAPI REST API
│   ├── main.py              # App entry point
│   ├── api/routes/          # API endpoints
│   ├── schemas/             # Pydantic models
│   ├── services/            # Business logic
│   └── data/                # Data repositories
│
├── frontend/                # React + Leaflet + Chart.js
│   ├── src/api/             # API client
│   ├── src/components/      # React components
│   ├── src/store/           # Zustand state
│   └── src/hooks/           # Custom hooks
│
├── data/
│   ├── raw/                 # Downloaded NetCDF files
│   └── processed/           # Histogram pickles
│
├── windguru_spots.pkl       # Input: raw spot data
├── requirements.txt         # Python dependencies
└── design.md                # Design specification
```

## Tech Stack

**Backend:**
- Python 3.13
- FastAPI
- Pandas, NumPy, xarray
- CDS API (Copernicus Climate Data Store)

**Frontend:**
- React 18 + TypeScript
- Vite
- Leaflet + react-leaflet
- Chart.js + react-chartjs-2
- Zustand (state management)
- TailwindCSS

## Troubleshooting

### CDS API Connection Issues

```bash
# Test connectivity
ping cds.climate.copernicus.eu

# Test API
.\venv\Scripts\python -c "import cdsapi; c = cdsapi.Client(); print('Connected!')"
```

Check:
- Your `.cdsapirc` file exists and has correct credentials
- You're not behind a firewall/VPN blocking the connection
- CDS service status at https://cds.climate.copernicus.eu

### Frontend Can't Connect to Backend

Ensure the backend is running on port 8000. The frontend dev server proxies `/api` requests to `localhost:8000`.

### Missing Histogram Data

If charts show "No data available", the data pipeline hasn't been run yet. Run:
```bash
.\venv\Scripts\python -m data_pipelines.main --max-cells 1
```
