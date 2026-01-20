# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Kiteapp is a kitesurfing spot finder that uses 10 years of ERA5 wind data from Copernicus Climate Data Store to identify optimal surfing locations. Three components: data pipelines, FastAPI backend, and React frontend.

## Commands

### Backend
```bash
.\venv\Scripts\activate                              # Activate venv (Windows)
.\venv\Scripts\uvicorn backend.main:app --reload     # Start backend (port 8000)
pytest tests/                                        # Run all tests
pytest tests/backend/                                # Backend tests only
```

### Frontend
```bash
cd frontend
npm install                    # Install dependencies
npm run dev                    # Start dev server (port 5173)
npm run build                  # TypeScript compile + Vite build
npm run lint                   # ESLint
```

### Data Pipeline
```bash
.\venv\Scripts\python -m data_pipelines.enrich_spots           # One-time: add country info to spots
.\venv\Scripts\python -m data_pipelines.main --max-cells 1     # Test with 1 grid cell
.\venv\Scripts\python -m data_pipelines.main --cleanup         # Full run, delete raw files after
.\venv\Scripts\python -m data_pipelines.main --source arco     # Use ARCO (Google Cloud) instead of CDS
```

Pipeline flags: `--max-cells N`, `--cleanup`, `--force-download`, `--force-process`, `--source [cds|arco]`

## Architecture

### Three-Layer Backend (backend/)
- **Routes** (`api/routes/`) - FastAPI endpoints for spots, histograms, windrose
- **Services** (`services/`) - Business logic: filtering, histogram processing, windrose calculation
- **Repositories** (`data/`) - Data access layer loading pickle files
- **Schemas** (`schemas/`) - Pydantic models for API contracts

### Data Pipeline (data_pipelines/)
- `PipelineOrchestrator` in `main.py` coordinates the workflow
- Divides globe into 90°×60° grid cells (12 total, ~6-8 cells with spots)
- Downloads ERA5 data via CDS API (Copernicus, default) or ARCO (Google Cloud)
- Processes wind components (u,v) to strength/direction
- Builds daily histograms: 1D (strength only) and 2D (strength × direction)
- Wind bins: 2.5 knot increments (0-35 + infinity), direction: 10-degree increments

### Frontend (frontend/src/)
- **State**: Zustand stores in `store/` (filterStore, spotStore)
- **API**: Axios clients in `api/` (spotApi, histogramApi)
- **Components**: Map (Leaflet), HamburgerMenu (filters), SpotModal (charts carousel)
- **Charts**: Chart.js for line graph, histogram, and wind rose

### Data Flow
1. Frontend proxies `/api/*` to backend (Vite config)
2. Backend reads `data/processed/spots.pkl` and `data/processed/histograms_*/`
3. Filtering applies wind range, date range, country, min kiteable percentage

## Key Files

| File | Purpose |
|------|---------|
| `backend/config.py` | Settings, paths, CORS origins, filter defaults |
| `data_pipelines/config.py` | Wind bins, direction bins, grid size, ERA5 config |
| `frontend/vite.config.ts` | API proxy configuration |
| `data/processed/spots.pkl` | Enriched spot data (tracked in git) |

## Wind Data Details

- Wind strength: converted from m/s to knots, combined from u/v components
- Wind direction: "going to" compass direction (90° = wind from west going east)
- Histogram shapes: 1D is 365×16, 2D is 365×16×36

## ERA5 Data Sources

### CDS API (Default)
Downloads directly to disk (no RAM constraints). Requires `~/.cdsapirc` (or `%USERPROFILE%\.cdsapirc`) with Copernicus credentials:
```
url: https://cds.climate.copernicus.eu/api
key: <uid>:<api-key>
```
Uses larger 90°×60° grid cells to reduce queue requests (~60-80 total vs 1000+).

### ARCO ERA5 (Alternative)
Uses Google Cloud's Analysis-Ready Cloud-Optimized ERA5 dataset. No credentials needed, no queue wait times.
- Direct Zarr access via `gs://gcp-public-data-arco-era5/`
- Requires `gcsfs` package (included in requirements.txt)
- Note: Zarr chunking downloads ~12GB to extract ~14MB useful data per cell
- Use `--source arco` flag to use ARCO instead of CDS
