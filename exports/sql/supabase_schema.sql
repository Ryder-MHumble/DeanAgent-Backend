-- Generated from Supabase OpenAPI introspection
-- Note: indexes, triggers, policies, functions are not included in this export.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS "articles" (
  "url_hash" VARCHAR(64) NOT NULL,
  "source_id" VARCHAR(128) NOT NULL,
  "dimension" VARCHAR(64) NOT NULL,
  "group_name" VARCHAR(128) NULL,
  "url" TEXT NOT NULL,
  "title" TEXT NULL,
  "author" VARCHAR(512) NULL,
  "published_at" TIMESTAMPTZ NULL,
  "content" TEXT NULL,
  "content_html" TEXT NULL,
  "content_hash" VARCHAR(64) NULL,
  "tags" TEXT[] NULL,
  "extra" JSONB NULL,
  "crawled_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "first_crawled_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "is_new" BOOLEAN DEFAULT TRUE NOT NULL,
  "is_read" BOOLEAN DEFAULT FALSE NOT NULL,
  "importance" SMALLINT DEFAULT 0 NOT NULL,
  "custom_fields" JSONB NULL,
  PRIMARY KEY ("url_hash")
);

CREATE TABLE IF NOT EXISTS "crawl_logs" (
  "id" BIGINT NOT NULL,
  "source_id" VARCHAR(128) NOT NULL,
  "status" VARCHAR(32) NOT NULL,
  "items_total" INTEGER DEFAULT 0 NOT NULL,
  "items_new" INTEGER DEFAULT 0 NOT NULL,
  "error_message" TEXT NULL,
  "started_at" TIMESTAMPTZ NOT NULL,
  "finished_at" TIMESTAMPTZ NULL,
  "duration_seconds" DOUBLE PRECISION NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "event_scholars" (
  "event_id" VARCHAR(64) NOT NULL,
  "scholar_id" VARCHAR(64) NOT NULL,
  "role" VARCHAR(64) NULL,
  PRIMARY KEY ("event_id", "scholar_id")
);

CREATE TABLE IF NOT EXISTS "event_taxonomy" (
  "id" UUID DEFAULT gen_random_uuid() NOT NULL,
  "level" INTEGER NOT NULL,
  "name" TEXT NOT NULL,
  "parent_id" UUID NULL,
  "sort_order" INTEGER DEFAULT 0 NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "events" (
  "id" VARCHAR(64) DEFAULT (gen_random_uuid())::text NOT NULL,
  "event_type" VARCHAR(64) NULL,
  "title" TEXT NOT NULL,
  "series_number" INTEGER NULL,
  "speaker_name" VARCHAR(256) NULL,
  "speaker_title" VARCHAR(256) NULL,
  "speaker_organization" VARCHAR(256) NULL,
  "speaker_bio" TEXT NULL,
  "speaker_photo_url" TEXT NULL,
  "event_date" DATE NULL,
  "event_time" VARCHAR(64) NULL,
  "location" VARCHAR(512) NULL,
  "online_link" TEXT NULL,
  "registration_url" TEXT NULL,
  "poster_url" TEXT NULL,
  "description" TEXT NULL,
  "organizer" VARCHAR(256) NULL,
  "scholar_ids" TEXT[] NULL,
  "is_past" BOOLEAN DEFAULT FALSE NOT NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "custom_fields" JSONB NULL,
  "series" VARCHAR DEFAULT '' NULL,
  "category" TEXT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "institutions" (
  "id" VARCHAR(128) NOT NULL,
  "name" VARCHAR(256) NOT NULL,
  "type" VARCHAR(32) NOT NULL,
  "parent_id" VARCHAR(128) NULL,
  "org_name" VARCHAR(256) NULL,
  "category" VARCHAR(64) NULL,
  "priority" SMALLINT DEFAULT 3 NULL,
  "scholar_count" INTEGER DEFAULT 0 NOT NULL,
  "mentor_count" INTEGER DEFAULT 0 NOT NULL,
  "student_count_24" INTEGER NULL,
  "student_count_25" INTEGER NULL,
  "student_count_total" INTEGER NULL,
  "resident_leaders" JSONB NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "degree_committee" JSONB NULL,
  "teaching_committee" JSONB NULL,
  "university_leaders" JSONB NULL,
  "notable_scholars" JSONB NULL,
  "entity_type" VARCHAR NULL,
  "region" VARCHAR NULL,
  "org_type" VARCHAR NULL,
  "classification" VARCHAR NULL,
  "sub_classification" VARCHAR NULL,
  "avatar" TEXT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "intel_cache" (
  "id" BIGINT NOT NULL,
  "intel_type" VARCHAR(64) NOT NULL,
  "generated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "pipeline_run_id" VARCHAR(64) NULL,
  "data" JSONB NOT NULL,
  "meta" JSONB NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "scholar_awards" (
  "id" BIGINT NOT NULL,
  "scholar_id" VARCHAR(64) NOT NULL,
  "title" TEXT NOT NULL,
  "year" SMALLINT NULL,
  "level" VARCHAR(64) NULL,
  "grantor" VARCHAR(256) NULL,
  "description" TEXT NULL,
  "added_by" VARCHAR(128) NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "scholar_dynamic_updates" (
  "id" BIGINT NOT NULL,
  "scholar_id" VARCHAR(64) NOT NULL,
  "update_type" VARCHAR(64) NULL,
  "title" TEXT NULL,
  "content" TEXT NULL,
  "source_url" TEXT NULL,
  "published_at" TIMESTAMPTZ NULL,
  "crawled_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "added_by" VARCHAR(128) NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "scholar_education" (
  "id" BIGINT NOT NULL,
  "scholar_id" VARCHAR(64) NOT NULL,
  "degree" VARCHAR(64) NULL,
  "institution" VARCHAR(256) NULL,
  "year" SMALLINT NULL,
  "major" VARCHAR(256) NULL,
  "sort_order" SMALLINT DEFAULT 0 NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "scholar_patents" (
  "id" BIGINT NOT NULL,
  "scholar_id" VARCHAR(64) NOT NULL,
  "title" TEXT NOT NULL,
  "patent_no" VARCHAR(128) NULL,
  "year" SMALLINT NULL,
  "inventors" TEXT[] NULL,
  "patent_type" VARCHAR(64) NULL,
  "status" VARCHAR(64) NULL,
  "added_by" VARCHAR(128) NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "scholar_publications" (
  "id" BIGINT NOT NULL,
  "scholar_id" VARCHAR(64) NOT NULL,
  "title" TEXT NOT NULL,
  "venue" VARCHAR(256) NULL,
  "year" SMALLINT NULL,
  "authors" TEXT[] NULL,
  "url" TEXT NULL,
  "citation_count" INTEGER DEFAULT 0 NULL,
  "is_corresponding" BOOLEAN DEFAULT FALSE NULL,
  "added_by" VARCHAR(128) NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "scholars" (
  "id" VARCHAR(64) NOT NULL,
  "name" VARCHAR(256) NOT NULL,
  "name_en" VARCHAR(256) NULL,
  "gender" VARCHAR(16) NULL,
  "photo_url" TEXT NULL,
  "university" VARCHAR(256) NULL,
  "department" VARCHAR(256) NULL,
  "secondary_departments" TEXT[] NULL,
  "position" VARCHAR(256) NULL,
  "academic_titles" TEXT[] NULL,
  "is_academician" BOOLEAN DEFAULT FALSE NOT NULL,
  "research_areas" TEXT[] NULL,
  "keywords" TEXT[] NULL,
  "bio" TEXT NULL,
  "bio_en" TEXT NULL,
  "email" VARCHAR(256) NULL,
  "phone" VARCHAR(64) NULL,
  "office" VARCHAR(256) NULL,
  "profile_url" TEXT NULL,
  "lab_url" TEXT NULL,
  "google_scholar_url" TEXT NULL,
  "dblp_url" TEXT NULL,
  "orcid" VARCHAR(64) NULL,
  "phd_institution" VARCHAR(256) NULL,
  "phd_year" SMALLINT NULL,
  "publications_count" INTEGER DEFAULT 0 NULL,
  "h_index" SMALLINT DEFAULT 0 NULL,
  "citations_count" INTEGER DEFAULT 0 NULL,
  "metrics_updated_at" TIMESTAMPTZ NULL,
  "is_advisor_committee" BOOLEAN NULL,
  "is_potential_recruit" BOOLEAN NULL,
  "adjunct_supervisor" JSONB NULL,
  "joint_research_projects" JSONB NULL,
  "joint_management_roles" JSONB NULL,
  "academic_exchange_records" JSONB NULL,
  "institute_relation_notes" TEXT NULL,
  "relation_updated_by" VARCHAR(128) NULL,
  "relation_updated_at" TIMESTAMPTZ NULL,
  "source_id" VARCHAR(128) NULL,
  "source_url" TEXT NULL,
  "crawled_at" TIMESTAMPTZ NULL,
  "first_seen_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "last_seen_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "is_active" BOOLEAN DEFAULT TRUE NOT NULL,
  "data_completeness" DOUBLE PRECISION DEFAULT 0.0 NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "content" TEXT DEFAULT '' NULL,
  "tags" TEXT[] NULL,
  "representative_publications" JSONB NULL,
  "patents" JSONB NULL,
  "awards" JSONB NULL,
  "education" JSONB NULL,
  "recent_updates" JSONB NULL,
  "supervised_students" JSONB NULL,
  "custom_fields" JSONB NULL,
  "project_category" TEXT DEFAULT '' NULL,
  "project_subcategory" TEXT DEFAULT '' NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "sentiment_comments" (
  "id" BIGINT NOT NULL,
  "platform" VARCHAR(32) NOT NULL,
  "comment_id" VARCHAR(256) NOT NULL,
  "content_id" VARCHAR(256) NOT NULL,
  "parent_comment_id" VARCHAR(256) NULL,
  "content" TEXT NULL,
  "pictures" TEXT NULL,
  "user_id" VARCHAR(256) NULL,
  "nickname" VARCHAR(256) NULL,
  "avatar" TEXT NULL,
  "ip_location" VARCHAR(256) NULL,
  "like_count" INTEGER DEFAULT 0 NULL,
  "dislike_count" INTEGER DEFAULT 0 NULL,
  "sub_comment_count" INTEGER DEFAULT 0 NULL,
  "platform_data" JSONB NULL,
  "publish_time" BIGINT NULL,
  "add_ts" BIGINT NULL,
  "last_modify_ts" BIGINT NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "sentiment_contents" (
  "id" BIGINT NOT NULL,
  "platform" VARCHAR(32) NOT NULL,
  "content_id" VARCHAR(256) NOT NULL,
  "content_type" VARCHAR(32) NULL,
  "title" TEXT NULL,
  "description" TEXT NULL,
  "content_url" TEXT NULL,
  "cover_url" TEXT NULL,
  "user_id" VARCHAR(256) NULL,
  "nickname" VARCHAR(256) NULL,
  "avatar" TEXT NULL,
  "ip_location" VARCHAR(256) NULL,
  "liked_count" INTEGER DEFAULT 0 NULL,
  "comment_count" INTEGER DEFAULT 0 NULL,
  "share_count" INTEGER DEFAULT 0 NULL,
  "collected_count" INTEGER DEFAULT 0 NULL,
  "platform_data" JSONB NULL,
  "source_keyword" VARCHAR(512) NULL,
  "crawl_task_id" VARCHAR(256) NULL,
  "publish_time" BIGINT NULL,
  "add_ts" BIGINT NULL,
  "last_modify_ts" BIGINT NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "sentiment_creators" (
  "id" BIGINT NOT NULL,
  "platform" VARCHAR(32) NOT NULL,
  "user_id" VARCHAR(256) NOT NULL,
  "nickname" VARCHAR(256) NULL,
  "avatar" TEXT NULL,
  "description" TEXT NULL,
  "gender" VARCHAR(16) NULL,
  "ip_location" VARCHAR(256) NULL,
  "follows_count" INTEGER DEFAULT 0 NULL,
  "fans_count" INTEGER DEFAULT 0 NULL,
  "interaction_count" INTEGER DEFAULT 0 NULL,
  "platform_data" JSONB NULL,
  "add_ts" BIGINT NULL,
  "last_modify_ts" BIGINT NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "snapshots" (
  "source_id" VARCHAR(128) NOT NULL,
  "data" JSONB NOT NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("source_id")
);

CREATE TABLE IF NOT EXISTS "source_states" (
  "source_id" VARCHAR(128) NOT NULL,
  "last_crawl_at" TIMESTAMPTZ NULL,
  "last_success_at" TIMESTAMPTZ NULL,
  "consecutive_failures" SMALLINT DEFAULT 0 NOT NULL,
  "is_enabled_override" BOOLEAN NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("source_id")
);

CREATE TABLE IF NOT EXISTS "supervised_students" (
  "id" VARCHAR(64) DEFAULT (gen_random_uuid())::text NOT NULL,
  "scholar_id" VARCHAR(64) NOT NULL,
  "student_no" VARCHAR(64) NULL,
  "name" VARCHAR(128) NOT NULL,
  "home_university" VARCHAR(256) NULL,
  "degree_type" VARCHAR(32) NULL,
  "enrollment_year" SMALLINT NULL,
  "expected_graduation_year" SMALLINT NULL,
  "status" VARCHAR(32) NULL,
  "email" VARCHAR(256) NULL,
  "phone" VARCHAR(64) NULL,
  "notes" TEXT NULL,
  "added_by" VARCHAR(128) NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "venues" (
  "id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "full_name" TEXT NULL,
  "type" TEXT NOT NULL,
  "rank" TEXT NULL,
  "fields" TEXT[] NULL,
  "description" TEXT NULL,
  "h5_index" INTEGER NULL,
  "acceptance_rate" DOUBLE PRECISION NULL,
  "impact_factor" DOUBLE PRECISION NULL,
  "publisher" TEXT NULL,
  "website" TEXT NULL,
  "issn" TEXT NULL,
  "frequency" TEXT NULL,
  "is_active" BOOLEAN DEFAULT TRUE NULL,
  "custom_fields" JSONB NULL,
  "created_at" TIMESTAMPTZ DEFAULT now() NULL,
  "updated_at" TIMESTAMPTZ DEFAULT now() NULL,
  PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "vibe_coding_raw_data" (
  "id" BIGINT NOT NULL,
  "platform" TEXT NOT NULL,
  "content_id" TEXT NOT NULL,
  "content_type" TEXT NULL,
  "title" TEXT NULL,
  "description" TEXT NULL,
  "content_url" TEXT NULL,
  "cover_url" TEXT NULL,
  "user_id" TEXT NULL,
  "nickname" TEXT NULL,
  "avatar" TEXT NULL,
  "liked_count" INTEGER DEFAULT 0 NULL,
  "comment_count" INTEGER DEFAULT 0 NULL,
  "share_count" INTEGER DEFAULT 0 NULL,
  "collected_count" INTEGER DEFAULT 0 NULL,
  "ip_location" TEXT NULL,
  "publish_time" BIGINT NULL,
  "vibe_coding_keywords" TEXT[] NULL,
  "innovation_score" DOUBLE PRECISION NULL,
  "trend_category" TEXT NULL,
  "extracted_ideas" JSONB NULL,
  "analysis_status" TEXT DEFAULT 'pending' NULL,
  "analyzed_at" BIGINT NULL,
  "design_proposal_id" TEXT NULL,
  "platform_data" JSONB NULL,
  "top_comments" JSONB NULL,
  "source_keyword" TEXT NULL,
  "crawl_session_id" TEXT NULL,
  "created_at" TIMESTAMP DEFAULT now() NULL,
  "last_modify_ts" BIGINT NOT NULL,
  PRIMARY KEY ("id")
);

ALTER TABLE "event_scholars" ADD CONSTRAINT "fk_event_scholars_event_id_events_id" FOREIGN KEY ("event_id") REFERENCES "events" ("id");
ALTER TABLE "event_scholars" ADD CONSTRAINT "fk_event_scholars_scholar_id_scholars_id" FOREIGN KEY ("scholar_id") REFERENCES "scholars" ("id");
ALTER TABLE "event_taxonomy" ADD CONSTRAINT "fk_event_taxonomy_parent_id_event_taxonomy_id" FOREIGN KEY ("parent_id") REFERENCES "event_taxonomy" ("id");
ALTER TABLE "institutions" ADD CONSTRAINT "fk_institutions_parent_id_institutions_id" FOREIGN KEY ("parent_id") REFERENCES "institutions" ("id");
ALTER TABLE "scholar_awards" ADD CONSTRAINT "fk_scholar_awards_scholar_id_scholars_id" FOREIGN KEY ("scholar_id") REFERENCES "scholars" ("id");
ALTER TABLE "scholar_dynamic_updates" ADD CONSTRAINT "fk_scholar_dynamic_updates_scholar_id_scholars_id" FOREIGN KEY ("scholar_id") REFERENCES "scholars" ("id");
ALTER TABLE "scholar_education" ADD CONSTRAINT "fk_scholar_education_scholar_id_scholars_id" FOREIGN KEY ("scholar_id") REFERENCES "scholars" ("id");
ALTER TABLE "scholar_patents" ADD CONSTRAINT "fk_scholar_patents_scholar_id_scholars_id" FOREIGN KEY ("scholar_id") REFERENCES "scholars" ("id");
ALTER TABLE "scholar_publications" ADD CONSTRAINT "fk_scholar_publications_scholar_id_scholars_id" FOREIGN KEY ("scholar_id") REFERENCES "scholars" ("id");
ALTER TABLE "supervised_students" ADD CONSTRAINT "fk_supervised_students_scholar_id_scholars_id" FOREIGN KEY ("scholar_id") REFERENCES "scholars" ("id");
