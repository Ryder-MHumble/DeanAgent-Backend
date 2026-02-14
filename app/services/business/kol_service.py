"""Business logic for KOL tracking via Twitter API."""
from __future__ import annotations

import logging

from app.schemas.business.kol import (
    KOLListResponse,
    KOLProfile,
    KOLTweet,
    KOLTweetsResponse,
)
from app.services.twitter_service import twitter_client

logger = logging.getLogger(__name__)

# Curated list of AI KOLs to track
AI_KOLS = [
    {"username": "ylecun", "field": "AI/Deep Learning", "affiliation": "NYU / AMI Labs (Ex-Meta)"},
    {"username": "kaboraAI", "field": "AI/ML", "affiliation": "Ex-Tesla/OpenAI"},
    {"username": "sama", "field": "AI/AGI", "affiliation": "OpenAI CEO"},
    {"username": "demisaboris", "field": "AI/AGI", "affiliation": "Google DeepMind CEO"},
    {"username": "hardmaru", "field": "AI/ML", "affiliation": "Sakana AI"},
    {"username": "DrJimFan", "field": "AI/Robotics", "affiliation": "NVIDIA"},
]


def _influence_level(followers: int) -> str:
    if followers >= 1_000_000:
        return "极高"
    if followers >= 100_000:
        return "高"
    return "中"


async def get_kol_profiles() -> KOLListResponse:
    """Fetch KOL profiles from Twitter."""
    if not twitter_client.is_configured:
        return KOLListResponse(profiles=[], total=0)

    profiles: list[KOLProfile] = []

    for kol in AI_KOLS:
        try:
            user = await twitter_client.get_user_info(kol["username"])
            if not user:
                continue

            profiles.append(KOLProfile(
                id=user.id,
                name=user.name,
                username=user.username,
                affiliation=kol.get("affiliation", user.description[:100]),
                field=kol.get("field", "AI"),
                followers=user.followers,
                influence=_influence_level(user.followers),
                profile_pic=user.profile_pic,
                recent_activity=f"{user.tweet_count} tweets",
                summary=user.description[:200] if user.description else "",
            ))

        except Exception as e:
            logger.warning("Failed to fetch profile for @%s: %s", kol["username"], e)

    profiles.sort(key=lambda x: x.followers, reverse=True)
    return KOLListResponse(profiles=profiles, total=len(profiles))


async def get_kol_tweets(
    username: str | None = None,
    limit: int = 30,
) -> KOLTweetsResponse:
    """
    Get recent tweets from KOLs.

    If username is provided, fetches from that user only.
    Otherwise, fetches from all tracked KOLs.
    """
    if not twitter_client.is_configured:
        return KOLTweetsResponse(tweets=[], total=0)

    all_tweets: list[KOLTweet] = []

    accounts = [username] if username else [k["username"] for k in AI_KOLS]

    for acct in accounts:
        try:
            raw_tweets, _ = await twitter_client.get_user_tweets(acct)
        except Exception as e:
            logger.warning("Failed to fetch tweets for @%s: %s", acct, e)
            continue

        for t in raw_tweets:
            if t.is_reply or t.is_retweet:
                continue
            all_tweets.append(KOLTweet(
                id=t.id,
                text=t.text[:500],
                url=t.url,
                author_name=t.author_name,
                author_username=t.author_username,
                author_followers=t.author_followers,
                created_at=t.created_at.isoformat() if t.created_at else None,
                like_count=t.like_count,
                retweet_count=t.retweet_count,
                view_count=t.view_count,
                lang=t.lang,
            ))

    # Sort by engagement
    all_tweets.sort(key=lambda x: x.like_count, reverse=True)
    all_tweets = all_tweets[:limit]

    return KOLTweetsResponse(tweets=all_tweets, total=len(all_tweets))
