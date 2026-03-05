"""Supabase client singleton for social media sentiment data."""

from __future__ import annotations

import logging

from supabase import Client, create_client

from app.config import settings

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_supabase() -> Client:
    """Return a shared Supabase client instance (lazy-init)."""
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set in .env "
                "to use sentiment monitoring features"
            )
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("Supabase client initialized for %s", settings.SUPABASE_URL)
    return _client
