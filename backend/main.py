"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from backend.config import settings
from backend.api.routes import spots, histograms, windrose, daily_wind, weather
from backend.api.dependencies import get_histogram_repository
from backend.middleware.activity_log import ActivityLogMiddleware, setup_activity_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload data on startup."""
    get_histogram_repository().preload()
    yield

# Create FastAPI app with orjson for faster JSON serialization
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    redirect_slashes=False,
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request activity logging. Added after CORS so it wraps it and also sees
# requests CORS rejects; OPTIONS preflights are skipped by the middleware.
if settings.activity_log_enabled:
    setup_activity_logging(
        log_file=settings.activity_log_file,
        retention_days=settings.activity_log_retention_days,
        stdout=settings.activity_log_stdout,
    )
    app.add_middleware(
        ActivityLogMiddleware,
        exclude_paths=settings.activity_log_exclude_paths,
        anonymize_ips=settings.activity_log_anonymize_ips,
    )

# Include routers
app.include_router(spots.router)
app.include_router(histograms.router)
app.include_router(windrose.router)
app.include_router(daily_wind.router)
app.include_router(weather.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
