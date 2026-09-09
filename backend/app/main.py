# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.cron.ledger_generator import generate_daily_ledger_entries

settings = get_settings()
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Schedule nightly ledger generation at 23:00
    scheduler.add_job(
        _run_ledger_generator,
        "cron",
        hour=23,
        minute=0,
        id="nightly_ledger_gen",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


def _run_ledger_generator():
    tomorrow = datetime.date.today() + datetime.timedelta(days=1)
    db = SessionLocal()
    try:
        generate_daily_ledger_entries(tomorrow, db)
    finally:
        db.close()


app = FastAPI(
    title="Chronos Ledger API",
    description="Organization Schedule & Attendance Management System",
    version="0.9.0",  # x-release-please-version
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "chronos-ledger"}
