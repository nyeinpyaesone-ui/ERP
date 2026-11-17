"""
Main FastAPI Application Entry Point
ERP System - Complete Business Management Platform
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

# Import routers that have actual implementations
from app.routers.bulk_import_export import router as bulk_import_export_router
from app.routers.migrations import router as migrations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("🚀 Starting ERP System...")
    yield
    # Shutdown
    print("🛑 Shutting down ERP System...")


app = FastAPI(
    title="ERP System",
    description="Complete Enterprise Resource Planning System with BI, POS, MRP, and E-commerce",
    version="2.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://yourdomain.com",
        "*"  # Remove in production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
if os.path.exists("/workspace/backend/static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Include implemented routers
app.include_router(bulk_import_export_router)
app.include_router(migrations_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to ERP System API",
        "version": "2.1.0",
        "docs": "/api/docs",
        "health": "/api/health"
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "erp-api",
        "version": "2.1.0"
    }


@app.get("/api/status")
async def system_status():
    """System status with component health"""
    return {
        "api": "operational",
        "database": "pending",
        "redis": "pending",
        "elasticsearch": "pending",
        "version": "2.1.0"
    }
