"""External API integrations — third-party data sources and clients."""
from app.services.external import aminer_client, sentiment_service, supabase_client, twitter_service

__all__ = ["aminer_client", "sentiment_service", "supabase_client", "twitter_service"]
