"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from backend.config import settings
from backend.api.routes import spots, histograms, windrose, daily_wind
from backend.api.dependencies import get_histogram_repository


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

# Include routers
app.include_router(spots.router)
app.include_router(histograms.router)
app.include_router(windrose.router)
app.include_router(daily_wind.router)


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
