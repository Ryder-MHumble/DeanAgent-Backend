-- =============================================================================
-- Information Crawler — PostgreSQL 数据仓库 DDL
-- 目标数据库：Supabase（PostgreSQL 15+）
-- 项目：yrawbjcyfafqmswnazmv.supabase.co
--
-- 运行方式：在 Supabase Dashboard → SQL Editor 中粘贴并执行
--
-- 设计原则：
--   1. 尽量减少 API 服务层改动（service 函数签名不变）
--   2. 高频查询字段建索引；可变/嵌套字段用 JSONB
--   3. 爬虫输出数据（articles）与已有 JSON 文件结构对齐
--   4. 学者核心字段显式列出，低频复杂嵌套用 JSONB
--   5. Intel 处理结果保留 JSONB 缓存层，Pipeline 直写无需改 API
-- =============================================================================

-- ============================================================
-- SECTION 1：基础设施
-- Supabase 已内置这些扩展，直接启用即可
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- 模糊搜索加速（source_name 模糊匹配）
CREATE EXTENSION IF NOT EXISTS btree_gin; -- JSONB 复合索引支持

-- ============================================================
-- SECTION 2：爬虫核心数据
-- ============================================================

-- ----------------------------------------------------------
-- 2.1 articles — 文章库
-- 替代：data/raw/{dimension}/{group}/{source_id}/latest.json
--       data/state/article_annotations.json
-- ----------------------------------------------------------
CREATE TABLE articles (
    -- 主键：与现有逻辑对齐，用 url_hash 作为业务 ID
    url_hash        VARCHAR(64)     PRIMARY KEY,          -- SHA-256 hex，现有逻辑 id 字段
    source_id       VARCHAR(128)    NOT NULL,
    dimension       VARCHAR(64)     NOT NULL,
    group_name      VARCHAR(128),                         -- YAML 中的 group 字段
    url             TEXT            NOT NULL,
    title           TEXT,
    author          VARCHAR(512),
    published_at    TIMESTAMPTZ,
    content         TEXT,                                 -- 正文纯文本
    content_html    TEXT,                                 -- 正文 HTML
    content_hash    VARCHAR(64),                          -- 正文去重 hash
    tags            TEXT[]          DEFAULT '{}',
    extra           JSONB           DEFAULT '{}',         -- 爬虫额外字段（来源特定）
    -- 爬取元信息
    crawled_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    first_crawled_at TIMESTAMPTZ   NOT NULL DEFAULT NOW(), -- 首次入库时间
    is_new          BOOLEAN         NOT NULL DEFAULT TRUE, -- 本次爬取是否为新条目
    -- 用户标注（原 article_annotations.json）
    is_read         BOOLEAN         NOT NULL DEFAULT FALSE,
    importance      SMALLINT        NOT NULL DEFAULT 0     -- 0=普通 1=重要 2=非常重要
);

CREATE INDEX idx_articles_source_id       ON articles(source_id);
CREATE INDEX idx_articles_dimension       ON articles(dimension);
CREATE INDEX idx_articles_published_at    ON articles(published_at DESC);
CREATE INDEX idx_articles_crawled_at      ON articles(crawled_at DESC);
CREATE INDEX idx_articles_dim_pub         ON articles(dimension, published_at DESC);
CREATE INDEX idx_articles_source_pub      ON articles(source_id, published_at DESC);
CREATE INDEX idx_articles_tags            ON articles USING GIN(tags);
CREATE INDEX idx_articles_title_trgm      ON articles USING GIN(title gin_trgm_ops);

COMMENT ON TABLE articles IS '文章库，替代 data/raw/**/{source_id}/latest.json 中的 items 数组';
COMMENT ON COLUMN articles.url_hash IS 'SHA-256(normalized_url)，对应现有 API 中的文章 id';
COMMENT ON COLUMN articles.extra IS '爬虫扩展字段，如 snapshot 源的 diff、github 的 stars 等';


-- ----------------------------------------------------------
-- 2.2 source_states — 信源运行状态
-- 替代：data/state/source_state.json
-- 注：信源静态配置仍保留在 YAML，此表只存运行时状态
-- ----------------------------------------------------------
CREATE TABLE source_states (
    source_id               VARCHAR(128)    PRIMARY KEY,
    last_crawl_at           TIMESTAMPTZ,
    last_success_at         TIMESTAMPTZ,
    consecutive_failures    SMALLINT        NOT NULL DEFAULT 0,
    is_enabled_override     BOOLEAN,        -- NULL = 不覆盖 YAML，TRUE/FALSE = 强制覆盖
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE source_states IS '信源运行时动态状态，替代 data/state/source_state.json';
COMMENT ON COLUMN source_states.is_enabled_override IS 'NULL=尊重 YAML 配置；TRUE/FALSE=API 覆盖启用状态';


-- ----------------------------------------------------------
-- 2.3 crawl_logs — 爬取执行日志
-- 替代：data/logs/{source_id}/crawl_logs.json（每源最多 100 条）
-- ----------------------------------------------------------
CREATE TABLE crawl_logs (
    id                  BIGSERIAL       PRIMARY KEY,
    source_id           VARCHAR(128)    NOT NULL,
    status              VARCHAR(32)     NOT NULL,    -- success | partial_success | failed | skipped
    items_total         INT             NOT NULL DEFAULT 0,
    items_new           INT             NOT NULL DEFAULT 0,
    error_message       TEXT,
    started_at          TIMESTAMPTZ     NOT NULL,
    finished_at         TIMESTAMPTZ,
    duration_seconds    FLOAT
);

CREATE INDEX idx_crawl_logs_source_id   ON crawl_logs(source_id);
CREATE INDEX idx_crawl_logs_started_at  ON crawl_logs(started_at DESC);
CREATE INDEX idx_crawl_logs_status      ON crawl_logs(status);

COMMENT ON TABLE crawl_logs IS '爬取执行日志，替代 data/logs/{source_id}/crawl_logs.json';


-- ----------------------------------------------------------
-- 2.4 snapshots — 快照数据
-- 替代：data/state/snapshots/{source_id}.json
-- ----------------------------------------------------------
CREATE TABLE snapshots (
    source_id   VARCHAR(128)    PRIMARY KEY,
    data        JSONB           NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE snapshots IS '快照源的状态数据，替代 data/state/snapshots/{source_id}.json';


-- ============================================================
-- SECTION 3：学者知识库
-- ============================================================

-- ----------------------------------------------------------
-- 3.1 scholars — 学者主表
-- 替代：data/scholars/scholars.json（2679 位学者）
-- 设计：高频查询字段显式列出，复杂嵌套保留 JSONB
-- ----------------------------------------------------------
CREATE TABLE scholars (
    -- 主键
    id                      VARCHAR(64)     PRIMARY KEY,  -- source_id + name hash 或 UUID

    -- === 基本信息 ===
    name                    VARCHAR(256)    NOT NULL,
    name_en                 VARCHAR(256),
    gender                  VARCHAR(16),                  -- 男 | 女
    photo_url               TEXT,

    -- === 机构归属 ===
    university              VARCHAR(256),                 -- 所属大学（高频过滤）
    department              VARCHAR(256),                 -- 主要院系（高频过滤）
    secondary_departments   TEXT[]          DEFAULT '{}', -- 兼职院系

    -- === 职称荣誉 ===
    position                VARCHAR(256),                 -- 教授 | 副教授 | 研究员 等（高频过滤）
    academic_titles         TEXT[]          DEFAULT '{}', -- 院士/杰青/长江等头衔列表
    is_academician          BOOLEAN         NOT NULL DEFAULT FALSE,

    -- === 研究方向 ===
    research_areas          TEXT[]          DEFAULT '{}', -- 高频过滤
    keywords                TEXT[]          DEFAULT '{}',
    bio                     TEXT,                         -- 中文简介
    bio_en                  TEXT,                         -- 英文简介

    -- === 联系方式 ===
    email                   VARCHAR(256),
    phone                   VARCHAR(64),
    office                  VARCHAR(256),

    -- === 主页与链接 ===
    profile_url             TEXT,
    lab_url                 TEXT,
    google_scholar_url      TEXT,
    dblp_url                TEXT,
    orcid                   VARCHAR(64),

    -- === 教育经历（简化主字段，详细记录在 scholar_education） ===
    phd_institution         VARCHAR(256),
    phd_year                SMALLINT,

    -- === 学术指标 ===
    publications_count      INT             DEFAULT 0,
    h_index                 SMALLINT        DEFAULT 0,
    citations_count         INT             DEFAULT 0,
    metrics_updated_at      TIMESTAMPTZ,

    -- === 与两院关系（用户维护，爬虫不覆盖） ===
    is_advisor_committee        BOOLEAN,                  -- 是否担任顾问委员会
    is_potential_recruit        BOOLEAN,                  -- 是否潜在引进对象
    adjunct_supervisor          JSONB,                    -- 兼职导师详情（AdjunctSupervisorInfo）
    joint_research_projects     JSONB       DEFAULT '[]', -- 联合科研项目列表
    joint_management_roles      JSONB       DEFAULT '[]', -- 联合管理职务
    academic_exchange_records   JSONB       DEFAULT '[]', -- 学术交流记录
    institute_relation_notes    TEXT,
    relation_updated_by         VARCHAR(128),
    relation_updated_at         TIMESTAMPTZ,

    -- === 元信息 ===
    source_id               VARCHAR(128),                 -- 来源爬虫 source_id
    source_url              TEXT,
    crawled_at              TIMESTAMPTZ,
    first_seen_at           TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    last_seen_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    is_active               BOOLEAN         NOT NULL DEFAULT TRUE,
    data_completeness       FLOAT           DEFAULT 0.0,  -- 0.0-1.0

    -- === 时间戳 ===
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scholars_university      ON scholars(university);
CREATE INDEX idx_scholars_department      ON scholars(department);
CREATE INDEX idx_scholars_position        ON scholars(position);
CREATE INDEX idx_scholars_is_active       ON scholars(is_active);
CREATE INDEX idx_scholars_source_id       ON scholars(source_id);
CREATE INDEX idx_scholars_research_areas  ON scholars USING GIN(research_areas);
CREATE INDEX idx_scholars_keywords        ON scholars USING GIN(keywords);
CREATE INDEX idx_scholars_academic_titles ON scholars USING GIN(academic_titles);
CREATE INDEX idx_scholars_name_trgm       ON scholars USING GIN(name gin_trgm_ops);
CREATE INDEX idx_scholars_name_en_trgm    ON scholars USING GIN(name_en gin_trgm_ops);

COMMENT ON TABLE scholars IS '学者主表，替代 data/scholars/scholars.json';
COMMENT ON COLUMN scholars.adjunct_supervisor IS 'AdjunctSupervisorInfo JSON: {status, type, agreement_type, agreement_period, recommender}';


-- ----------------------------------------------------------
-- 3.2 scholar_publications — 代表性论文
-- 替代：scholars.representative_publications
-- ----------------------------------------------------------
CREATE TABLE scholar_publications (
    id              BIGSERIAL       PRIMARY KEY,
    scholar_id      VARCHAR(64)     NOT NULL REFERENCES scholars(id) ON DELETE CASCADE,
    title           TEXT            NOT NULL,
    venue           VARCHAR(256),
    year            SMALLINT,
    authors         TEXT[]          DEFAULT '{}',
    url             TEXT,
    citation_count  INT             DEFAULT 0,
    is_corresponding BOOLEAN        DEFAULT FALSE,
    added_by        VARCHAR(128),   -- crawler | llm | user
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scholar_pub_scholar_id ON scholar_publications(scholar_id);
CREATE INDEX idx_scholar_pub_year       ON scholar_publications(year DESC);


-- ----------------------------------------------------------
-- 3.3 scholar_patents — 专利
-- ----------------------------------------------------------
CREATE TABLE scholar_patents (
    id          BIGSERIAL       PRIMARY KEY,
    scholar_id  VARCHAR(64)     NOT NULL REFERENCES scholars(id) ON DELETE CASCADE,
    title       TEXT            NOT NULL,
    patent_no   VARCHAR(128),
    year        SMALLINT,
    inventors   TEXT[]          DEFAULT '{}',
    patent_type VARCHAR(64),    -- 发明专利 | 实用新型 | 外观设计
    status      VARCHAR(64),    -- 授权 | 申请中 | 失效
    added_by    VARCHAR(128),
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scholar_patents_scholar_id ON scholar_patents(scholar_id);


-- ----------------------------------------------------------
-- 3.4 scholar_awards — 荣誉奖项
-- ----------------------------------------------------------
CREATE TABLE scholar_awards (
    id          BIGSERIAL       PRIMARY KEY,
    scholar_id  VARCHAR(64)     NOT NULL REFERENCES scholars(id) ON DELETE CASCADE,
    title       TEXT            NOT NULL,
    year        SMALLINT,
    level       VARCHAR(64),    -- 国家级 | 省部级 | 校级 等
    grantor     VARCHAR(256),   -- 颁奖机构
    description TEXT,
    added_by    VARCHAR(128),
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scholar_awards_scholar_id ON scholar_awards(scholar_id);


-- ----------------------------------------------------------
-- 3.5 scholar_education — 教育经历
-- ----------------------------------------------------------
CREATE TABLE scholar_education (
    id          BIGSERIAL       PRIMARY KEY,
    scholar_id  VARCHAR(64)     NOT NULL REFERENCES scholars(id) ON DELETE CASCADE,
    degree      VARCHAR(64),    -- 学士 | 硕士 | 博士 | 博士后
    institution VARCHAR(256),
    year        SMALLINT,
    major       VARCHAR(256),
    sort_order  SMALLINT        DEFAULT 0,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_scholar_edu_scholar_id ON scholar_education(scholar_id);


-- ----------------------------------------------------------
-- 3.6 scholar_dynamic_updates — 动态更新记录
-- 替代：scholars.recent_updates
-- ----------------------------------------------------------
CREATE TABLE scholar_dynamic_updates (
    id          BIGSERIAL       PRIMARY KEY,
    scholar_id  VARCHAR(64)     NOT NULL REFERENCES scholars(id) ON DELETE CASCADE,
    update_type VARCHAR(64),    -- project | talent_title | position_change | award | publication
    title       TEXT,
    content     TEXT,
    source_url  TEXT,
    published_at TIMESTAMPTZ,
    crawled_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    added_by    VARCHAR(128)    -- crawler | user
);

CREATE INDEX idx_scholar_updates_scholar_id ON scholar_dynamic_updates(scholar_id);
CREATE INDEX idx_scholar_updates_published  ON scholar_dynamic_updates(published_at DESC);


-- ----------------------------------------------------------
-- 3.7 supervised_students — 联合培养学生
-- 替代：scholars.supervised_students + 独立 API 表
-- ----------------------------------------------------------
CREATE TABLE supervised_students (
    id                          VARCHAR(64)     PRIMARY KEY DEFAULT gen_random_uuid()::text,
    scholar_id                  VARCHAR(64)     NOT NULL REFERENCES scholars(id) ON DELETE CASCADE,
    student_no                  VARCHAR(64),
    name                        VARCHAR(128)    NOT NULL,
    home_university             VARCHAR(256),
    degree_type                 VARCHAR(32),    -- 硕士 | 博士 | 博士后
    enrollment_year             SMALLINT,
    expected_graduation_year    SMALLINT,
    status                      VARCHAR(32),    -- 在读 | 已毕业 | 退学
    email                       VARCHAR(256),
    phone                       VARCHAR(64),
    notes                       TEXT,
    added_by                    VARCHAR(128),
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_supervised_students_scholar_id ON supervised_students(scholar_id);


-- ============================================================
-- SECTION 4：机构图谱
-- ============================================================

-- ----------------------------------------------------------
-- 4.1 institutions — 机构/院系表
-- 替代：data/scholars/institutions.json
-- ----------------------------------------------------------
CREATE TABLE institutions (
    id              VARCHAR(128)    PRIMARY KEY,  -- 通常是大学名或 UUID
    name            VARCHAR(256)    NOT NULL,
    type            VARCHAR(32)     NOT NULL,     -- university | department
    parent_id       VARCHAR(128)    REFERENCES institutions(id),  -- 院系 → 大学
    org_name        VARCHAR(256),                 -- department 的归属大学名（冗余加速查询）

    -- 分类与优先级（手动富化字段，Pipeline 不覆盖）
    category        VARCHAR(64),                  -- 985 | 211 | 双一流 | 科研院所 等
    priority        SMALLINT        DEFAULT 3,    -- 1=最高，用于排序

    -- 统计数据（Pipeline Stage 4d 自动重建）
    scholar_count   INT             NOT NULL DEFAULT 0,
    mentor_count    INT             NOT NULL DEFAULT 0,

    -- 学生数量（手动填写）
    student_count_24    INT,
    student_count_25    INT,
    student_count_total INT,

    -- 复杂嵌套字段（手动维护，JSONB）
    resident_leaders    JSONB       DEFAULT '[]', -- [{name, title, department}]
    committees          JSONB       DEFAULT '[]', -- [{name, category, department}]
    labs                JSONB       DEFAULT '[]', -- [{name, director, focus}]
    cooperation_info    JSONB       DEFAULT '{}', -- {joint_programs, mou_status, contact}

    -- 院系信源列表（for /institutions/{id}/sources API）
    sources             JSONB       DEFAULT '[]', -- [DepartmentSource]

    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_institutions_type         ON institutions(type);
CREATE INDEX idx_institutions_parent_id    ON institutions(parent_id);
CREATE INDEX idx_institutions_category     ON institutions(category);
CREATE INDEX idx_institutions_name_trgm    ON institutions USING GIN(name gin_trgm_ops);

COMMENT ON TABLE institutions IS '机构图谱，替代 data/scholars/institutions.json';
COMMENT ON COLUMN institutions.sources IS 'DepartmentSource 列表，用于 /api/v1/institutions/{id}/sources';


-- ============================================================
-- SECTION 5：项目库
-- ============================================================

-- ----------------------------------------------------------
-- 5.1 projects — 研究项目
-- 替代：data/scholars/projects.json
-- ----------------------------------------------------------
CREATE TABLE projects (
    id                      VARCHAR(64)     PRIMARY KEY,  -- UUID 前 12 位
    name                    TEXT            NOT NULL,
    pi_name                 VARCHAR(256)    NOT NULL,
    pi_institution          VARCHAR(256),
    funder                  VARCHAR(256),                 -- 资助机构（高频过滤）
    funding_amount          NUMERIC(14,2),
    start_year              SMALLINT,
    end_year                SMALLINT,
    status                  VARCHAR(32)     NOT NULL,     -- 申请中|在研|已结题|暂停|终止
    category                VARCHAR(32),                  -- 国家级|省部级|横向课题|院内课题|国际合作|其他
    tags                    TEXT[]          DEFAULT '{}',
    description             TEXT,

    -- 关联数据（JSONB，与现有 ProjectDetailResponse 对齐）
    related_scholars        JSONB           DEFAULT '[]', -- [{name, role, institution, scholar_id}]
    outputs                 JSONB           DEFAULT '[]', -- [{type, title, year, authors, venue, url}]
    cooperation_institutions JSONB          DEFAULT '[]', -- [string]

    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_projects_status    ON projects(status);
CREATE INDEX idx_projects_category  ON projects(category);
CREATE INDEX idx_projects_funder    ON projects USING GIN(funder gin_trgm_ops);
CREATE INDEX idx_projects_pi_name   ON projects USING GIN(pi_name gin_trgm_ops);
CREATE INDEX idx_projects_tags      ON projects USING GIN(tags);
CREATE INDEX idx_projects_name_trgm ON projects USING GIN(name gin_trgm_ops);

COMMENT ON TABLE projects IS '研究项目库，替代 data/scholars/projects.json';


-- ============================================================
-- SECTION 6：学术活动
-- ============================================================

-- ----------------------------------------------------------
-- 6.1 events — 学术活动
-- 替代：data/scholars/events.json
-- ----------------------------------------------------------
CREATE TABLE events (
    id                  VARCHAR(64)     PRIMARY KEY DEFAULT gen_random_uuid()::text,
    event_type          VARCHAR(64),    -- 学术报告 | 学术会议 | 专题研讨 | 工作坊 等
    title               TEXT            NOT NULL,
    series_number       INT,            -- 系列编号（如"第 12 期"）

    -- 主讲人信息
    speaker_name        VARCHAR(256),
    speaker_title       VARCHAR(256),
    speaker_organization VARCHAR(256),
    speaker_bio         TEXT,
    speaker_photo_url   TEXT,

    -- 活动信息
    event_date          DATE,
    event_time          VARCHAR(64),    -- "14:00-16:00"
    location            VARCHAR(512),
    online_link         TEXT,
    registration_url    TEXT,
    poster_url          TEXT,
    description         TEXT,
    organizer           VARCHAR(256),

    -- 关联学者（ARRAY，快速查询；详见 event_scholars 关联表）
    scholar_ids         TEXT[]          DEFAULT '{}',

    -- 管理字段
    is_past             BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_event_type  ON events(event_type);
CREATE INDEX idx_events_event_date  ON events(event_date DESC);
CREATE INDEX idx_events_scholar_ids ON events USING GIN(scholar_ids);
CREATE INDEX idx_events_title_trgm  ON events USING GIN(title gin_trgm_ops);

COMMENT ON TABLE events IS '学术活动，替代 data/scholars/events.json';


-- ----------------------------------------------------------
-- 6.2 event_scholars — 活动与学者关联（多对多）
-- ----------------------------------------------------------
CREATE TABLE event_scholars (
    event_id    VARCHAR(64)     NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    scholar_id  VARCHAR(64)     NOT NULL REFERENCES scholars(id) ON DELETE CASCADE,
    role        VARCHAR(64),    -- speaker | organizer | participant
    PRIMARY KEY (event_id, scholar_id)
);

CREATE INDEX idx_event_scholars_scholar ON event_scholars(scholar_id);


-- ============================================================
-- SECTION 7：舆情监控
-- ============================================================

-- ----------------------------------------------------------
-- 7.1 sentiment_contents — 社媒内容
-- 字段与社媒舆情数据库 contents 表完全一致
-- ----------------------------------------------------------
CREATE TABLE sentiment_contents (
    id              BIGINT          PRIMARY KEY,
    platform        VARCHAR(32)     NOT NULL,     -- xhs | dy | bili | zhihu 等
    content_id      VARCHAR(256)    NOT NULL,
    content_type    VARCHAR(32),                  -- video | normal | 0
    title           TEXT,
    description     TEXT,
    content_url     TEXT,
    cover_url       TEXT,

    -- 作者信息
    user_id         VARCHAR(256),
    nickname        VARCHAR(256),
    avatar          TEXT,
    ip_location     VARCHAR(256),

    -- 互动数据
    liked_count     INT             DEFAULT 0,
    comment_count   INT             DEFAULT 0,
    share_count     INT             DEFAULT 0,
    collected_count INT             DEFAULT 0,

    -- 爬取元信息
    platform_data   JSONB           DEFAULT '{}',
    source_keyword  VARCHAR(512),
    crawl_task_id   VARCHAR(256),

    -- 时间戳（BIGINT 毫秒时间戳，与原始数据一致）
    publish_time    BIGINT,
    add_ts          BIGINT,
    last_modify_ts  BIGINT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sentiment_platform        ON sentiment_contents(platform);
CREATE INDEX idx_sentiment_publish_time    ON sentiment_contents(publish_time DESC);
CREATE INDEX idx_sentiment_content_id      ON sentiment_contents(content_id);
CREATE INDEX idx_sentiment_source_keyword  ON sentiment_contents(source_keyword);
CREATE INDEX idx_sentiment_title_trgm      ON sentiment_contents USING GIN(title gin_trgm_ops);


-- ----------------------------------------------------------
-- 7.2 sentiment_comments — 评论
-- 字段与社媒舆情数据库 comments 表完全一致
-- ----------------------------------------------------------
CREATE TABLE sentiment_comments (
    id                  BIGINT          PRIMARY KEY,
    platform            VARCHAR(32)     NOT NULL,
    comment_id          VARCHAR(256)    NOT NULL,
    content_id          VARCHAR(256)    NOT NULL,
    parent_comment_id   VARCHAR(256),
    content             TEXT,
    pictures            TEXT,
    user_id             VARCHAR(256),
    nickname            VARCHAR(256),
    avatar              TEXT,
    ip_location         VARCHAR(256),
    like_count          INT             DEFAULT 0,
    dislike_count       INT             DEFAULT 0,
    sub_comment_count   INT             DEFAULT 0,
    platform_data       JSONB           DEFAULT '{}',
    publish_time        BIGINT,
    add_ts              BIGINT,
    last_modify_ts      BIGINT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sentiment_comments_content_id ON sentiment_comments(content_id);
CREATE INDEX idx_sentiment_comments_platform   ON sentiment_comments(platform);


-- ----------------------------------------------------------
-- 7.3 sentiment_creators — 创作者/账号信息
-- 字段与社媒舆情数据库 creators 表完全一致
-- ----------------------------------------------------------
CREATE TABLE sentiment_creators (
    id              BIGINT          PRIMARY KEY,
    platform        VARCHAR(32)     NOT NULL,
    user_id         VARCHAR(256)    NOT NULL,
    nickname        VARCHAR(256),
    avatar          TEXT,
    description     TEXT,
    gender          VARCHAR(16),
    ip_location     VARCHAR(256),
    follows_count   INT             DEFAULT 0,
    fans_count      INT             DEFAULT 0,
    interaction_count INT           DEFAULT 0,
    platform_data   JSONB           DEFAULT '{}',
    add_ts          BIGINT,
    last_modify_ts  BIGINT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sentiment_creators_platform ON sentiment_creators(platform);
CREATE INDEX idx_sentiment_creators_user_id  ON sentiment_creators(user_id);


-- ============================================================
-- SECTION 8：业务智能缓存层（Intel）
-- ============================================================
-- 设计思路：Pipeline 处理结果以 JSONB 写入此表，
-- API 服务层直接读取，无需改动现有 service 函数逻辑。
-- 一行 = Pipeline 一次运行 + 一种维度的完整输出。
-- ----------------------------------------------------------

-- ----------------------------------------------------------
-- 8.1 intel_cache — 通用业务智能缓存
-- 替代：data/processed/{type}/*.json
-- ----------------------------------------------------------
CREATE TABLE intel_cache (
    id              BIGSERIAL       PRIMARY KEY,
    intel_type      VARCHAR(64)     NOT NULL,   -- policy_feed | policy_opportunities |
                                                -- personnel_feed | personnel_changes | personnel_enriched_feed |
                                                -- tech_frontier_topics | tech_frontier_opportunities | tech_frontier_stats |
                                                -- university_feed | university_overview | university_research_outputs |
                                                -- daily_briefing
    generated_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    pipeline_run_id VARCHAR(64),                -- Pipeline 执行 ID（用于关联同次运行的多个输出）
    data            JSONB           NOT NULL DEFAULT '[]',
    meta            JSONB           DEFAULT '{}' -- 统计信息、文章计数等
);

-- 每种类型保留最新 N 条（通过定期清理老数据）
CREATE INDEX idx_intel_cache_type_gen ON intel_cache(intel_type, generated_at DESC);

COMMENT ON TABLE intel_cache IS 'Pipeline 业务智能处理结果缓存，替代 data/processed/**/*.json';
COMMENT ON COLUMN intel_cache.intel_type IS
    '支持类型：policy_feed, policy_opportunities, '
    'personnel_feed, personnel_changes, personnel_enriched_feed, '
    'tech_frontier_topics, tech_frontier_opportunities, tech_frontier_stats, '
    'university_feed, university_overview, university_research_outputs, '
    'daily_briefing';


-- ============================================================
-- SECTION 9：辅助视图（加速 API 查询）
-- ============================================================

-- 最新一条 intel 缓存（给 service 层快捷访问）
CREATE OR REPLACE VIEW intel_cache_latest AS
SELECT DISTINCT ON (intel_type)
    id, intel_type, generated_at, pipeline_run_id, data, meta
FROM intel_cache
ORDER BY intel_type, generated_at DESC;

COMMENT ON VIEW intel_cache_latest IS '各类型业务智能的最新缓存，service 层可直接查询此视图';


-- 学者完整信息视图（含所属机构名）
CREATE OR REPLACE VIEW scholars_with_institution AS
SELECT
    s.*,
    i.category          AS institution_category,
    i.priority          AS institution_priority
FROM scholars s
LEFT JOIN institutions i ON i.name = s.university AND i.type = 'university';

COMMENT ON VIEW scholars_with_institution IS '学者信息 + 机构分类，减少 JOIN 操作';


-- ============================================================
-- SECTION 10：触发器 — 自动更新 updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_scholars_updated_at
    BEFORE UPDATE ON scholars
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_institutions_updated_at
    BEFORE UPDATE ON institutions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_events_updated_at
    BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_supervised_students_updated_at
    BEFORE UPDATE ON supervised_students
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_source_states_updated_at
    BEFORE UPDATE ON source_states
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ============================================================
-- SECTION 11：数据保留策略（建议定期执行）
-- ============================================================

-- 爬取日志只保留最近 90 天
-- DELETE FROM crawl_logs WHERE started_at < NOW() - INTERVAL '90 days';

-- 业务智能缓存每种类型保留最近 30 条
-- DELETE FROM intel_cache WHERE id NOT IN (
--     SELECT id FROM intel_cache ORDER BY intel_type, generated_at DESC
--     LIMIT 30
-- );

-- articles 中 is_new 标记在下次爬取时自动置 FALSE（由爬虫层控制）


-- ============================================================
-- SECTION 12：Supabase Row Level Security (RLS)
-- 后端使用 service_role key 访问，绕过 RLS
-- 如需前端直接访问某张表，在此添加对应策略
-- ============================================================

-- 默认对所有表启用 RLS（Supabase 安全最佳实践）
ALTER TABLE articles            ENABLE ROW LEVEL SECURITY;
ALTER TABLE source_states       ENABLE ROW LEVEL SECURITY;
ALTER TABLE crawl_logs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots           ENABLE ROW LEVEL SECURITY;
ALTER TABLE scholars            ENABLE ROW LEVEL SECURITY;
ALTER TABLE scholar_publications ENABLE ROW LEVEL SECURITY;
ALTER TABLE scholar_patents     ENABLE ROW LEVEL SECURITY;
ALTER TABLE scholar_awards      ENABLE ROW LEVEL SECURITY;
ALTER TABLE scholar_education   ENABLE ROW LEVEL SECURITY;
ALTER TABLE scholar_dynamic_updates ENABLE ROW LEVEL SECURITY;
ALTER TABLE supervised_students ENABLE ROW LEVEL SECURITY;
ALTER TABLE institutions        ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects            ENABLE ROW LEVEL SECURITY;
ALTER TABLE events              ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_scholars      ENABLE ROW LEVEL SECURITY;
ALTER TABLE sentiment_contents  ENABLE ROW LEVEL SECURITY;
ALTER TABLE sentiment_comments  ENABLE ROW LEVEL SECURITY;
ALTER TABLE sentiment_creators  ENABLE ROW LEVEL SECURITY;
ALTER TABLE intel_cache         ENABLE ROW LEVEL SECURITY;

-- 后端 service_role 拥有所有权限（无需 policy），前端 anon/authenticated 默认无权限
-- 如需开放某表给前端直接读取，取消下方注释并按需修改：
-- CREATE POLICY "allow_read_articles" ON articles FOR SELECT USING (true);
-- CREATE POLICY "allow_read_scholars" ON scholars FOR SELECT USING (true);
