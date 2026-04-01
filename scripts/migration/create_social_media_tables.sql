-- Unified social media tables for KOL posts across platforms (X/LinkedIn/YouTube/小宇宙...).
-- Safe to run repeatedly.

CREATE TABLE IF NOT EXISTS social_accounts (
  id BIGSERIAL PRIMARY KEY,
  platform VARCHAR(32) NOT NULL,
  username VARCHAR(128) NOT NULL,
  username_normalized VARCHAR(128) NOT NULL,
  display_name VARCHAR(256) NULL,
  platform_user_id VARCHAR(128) NULL,
  profile_url TEXT NULL,
  avatar_url TEXT NULL,
  bio TEXT NULL,
  follower_count BIGINT NOT NULL DEFAULT 0,
  following_count BIGINT NOT NULL DEFAULT 0,
  post_count BIGINT NOT NULL DEFAULT 0,
  is_verified BOOLEAN NOT NULL DEFAULT FALSE,
  is_kol BOOLEAN NOT NULL DEFAULT FALSE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  raw_profile JSONB NOT NULL DEFAULT '{}'::jsonb,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_social_accounts_platform_username_norm UNIQUE (platform, username_normalized)
);

CREATE INDEX IF NOT EXISTS idx_social_accounts_platform_kol
  ON social_accounts(platform, is_kol);

CREATE INDEX IF NOT EXISTS idx_social_accounts_platform_followers
  ON social_accounts(platform, follower_count DESC);

CREATE INDEX IF NOT EXISTS idx_social_accounts_platform_last_seen
  ON social_accounts(platform, last_seen_at DESC);


CREATE TABLE IF NOT EXISTS social_posts (
  id BIGSERIAL PRIMARY KEY,
  platform VARCHAR(32) NOT NULL,
  external_post_id VARCHAR(128) NOT NULL,
  account_id BIGINT NULL REFERENCES social_accounts(id) ON DELETE SET NULL,
  author_username VARCHAR(128) NOT NULL,
  author_display_name VARCHAR(256) NULL,
  author_platform_user_id VARCHAR(128) NULL,
  is_kol_author BOOLEAN NOT NULL DEFAULT FALSE,
  post_type VARCHAR(32) NOT NULL DEFAULT 'post',
  content_text TEXT NULL,
  content_lang VARCHAR(16) NULL,
  post_url TEXT NULL,
  published_at TIMESTAMPTZ NULL,
  crawled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  like_count BIGINT NOT NULL DEFAULT 0,
  reply_count BIGINT NOT NULL DEFAULT 0,
  repost_count BIGINT NOT NULL DEFAULT 0,
  quote_count BIGINT NOT NULL DEFAULT 0,
  view_count BIGINT NOT NULL DEFAULT 0,
  bookmark_count BIGINT NOT NULL DEFAULT 0,
  top_replies JSONB NOT NULL DEFAULT '[]'::jsonb,
  top_replies_count BIGINT NOT NULL DEFAULT 0,
  extra JSONB NOT NULL DEFAULT '{}'::jsonb,
  raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_social_posts_platform_external_post UNIQUE (platform, external_post_id),
  CONSTRAINT ck_social_posts_post_type CHECK (post_type IN ('post', 'reply', 'repost', 'quote', 'comment'))
);

-- Compatibility migration for previously created schema versions.
ALTER TABLE social_posts DROP COLUMN IF EXISTS author_username_normalized;
ALTER TABLE social_posts DROP COLUMN IF EXISTS root_post_external_id;
ALTER TABLE social_posts DROP COLUMN IF EXISTS parent_post_external_id;
ALTER TABLE social_posts DROP COLUMN IF EXISTS conversation_id;
ALTER TABLE social_posts DROP COLUMN IF EXISTS post_twitter_url;

ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS top_replies JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE social_posts ADD COLUMN IF NOT EXISTS top_replies_count BIGINT NOT NULL DEFAULT 0;

DROP INDEX IF EXISTS idx_social_posts_platform_author;
DROP INDEX IF EXISTS idx_social_posts_platform_root;
DROP INDEX IF EXISTS idx_social_posts_reply_rank;

CREATE INDEX IF NOT EXISTS idx_social_posts_platform_published
  ON social_posts(platform, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_social_posts_platform_author
  ON social_posts(platform, author_username, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_social_posts_platform_kol_author
  ON social_posts(platform, is_kol_author, published_at DESC);
