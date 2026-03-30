from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MigrationItem:
    file: str
    capability: str
    reuse: str
    status: str
    description: str
    canonical: bool = False
    superseded_by: str | None = None


MIGRATION_CATALOG: tuple[MigrationItem, ...] = (
    MigrationItem(
        file="alter_supervised_students_add_columns.sql",
        capability="schema",
        reuse="medium",
        status="active",
        description="Add supervised_students detail columns (idempotent DDL).",
    ),
    MigrationItem(
        file="create_university_leadership_tables.sql",
        capability="schema",
        reuse="high",
        status="active",
        description="Create university leadership persistence table and indexes.",
        canonical=True,
    ),
    MigrationItem(
        file="migrate_event_project_tag_schema.sql",
        capability="schema",
        reuse="medium",
        status="active",
        description="Upgrade events/projects/scholars to tag-oriented schema.",
    ),
    MigrationItem(
        file="archive/oneoff/reset_institution_people_sections.sql",
        capability="schema",
        reuse="low",
        status="oneoff",
        description="One-time cleanup of institution people sections.",
    ),
    MigrationItem(
        file="optimize_pg_performance.sql",
        capability="performance",
        reuse="high",
        status="active",
        description="Core indexes for scholars/institutions query paths.",
        canonical=True,
    ),
    MigrationItem(
        file="apply_pg_optimizations.sh",
        capability="performance",
        reuse="high",
        status="active",
        description="Apply performance SQL with owner/permission safeguards.",
        canonical=True,
    ),
    MigrationItem(
        file="export_supabase_to_sql.py",
        capability="export_sync",
        reuse="high",
        status="active",
        description="Export Supabase schema/data to SQL dump files.",
        canonical=True,
    ),
    MigrationItem(
        file="refresh_and_load_local.sh",
        capability="export_sync",
        reuse="high",
        status="active",
        description="Refresh remote dump and load into local PostgreSQL.",
        canonical=True,
    ),
    MigrationItem(
        file="verify_local_pg_counts.py",
        capability="verification",
        reuse="high",
        status="active",
        description="Verify local row counts against export summary.",
        canonical=True,
    ),
    MigrationItem(
        file="fix_scholar_institutions.py",
        capability="data_cleanup",
        reuse="high",
        status="active",
        description="Unified entrypoint for scholar institution cleanup tasks.",
        canonical=True,
    ),
    MigrationItem(
        file="fix_scholar_institutions_region_and_merge.py",
        capability="data_cleanup",
        reuse="high",
        status="active",
        description="Global cleanup + region reclassification + scholar/institution L1/L2 merge.",
        canonical=True,
    ),
    MigrationItem(
        file="archive/legacy/fix_scholar_institutions_domestic_cleanup.py",
        capability="data_cleanup",
        reuse="medium",
        status="legacy",
        description="Domestic-focused institution cleanup (narrow scope).",
        superseded_by="fix_scholar_institutions.py --scope global",
    ),
    MigrationItem(
        file="archive/legacy/fix_scholar_institutions_full.py",
        capability="data_cleanup",
        reuse="medium",
        status="legacy",
        description="Earlier full cleanup implementation (superseded).",
        superseded_by="fix_scholar_institutions.py --scope global",
    ),
    MigrationItem(
        file="archive/oneoff/rename_cas_to_ucas.py",
        capability="data_cleanup",
        reuse="low",
        status="oneoff",
        description="One-time CAS->UCAS rename migration.",
    ),
    MigrationItem(
        file="import_adjunct_mentors.py",
        capability="data_import",
        reuse="medium",
        status="active",
        description="Import mentor/community data from configured CSV files.",
        canonical=True,
    ),
    MigrationItem(
        file="import_students_from_xlsx.py",
        capability="data_import",
        reuse="medium",
        status="active",
        description="Import supervised students from staged XLSX files.",
        canonical=True,
    ),
    MigrationItem(
        file="migrate_scholar_achievements.py",
        capability="data_import",
        reuse="medium",
        status="active",
        description="Backfill achievements from scholars JSON fields to relation tables.",
    ),
    MigrationItem(
        file="archive/oneoff/tag_named_scholars_as_adjunct_mentors.py",
        capability="data_tagging",
        reuse="low",
        status="oneoff",
        description="Tag specific hardcoded scholars as adjunct mentors.",
    ),
    MigrationItem(
        file="tag_scholars_from_academy_mentors_csv.py",
        capability="data_tagging",
        reuse="medium",
        status="active",
        description="Tag scholars listed in academy mentor CSV.",
    ),
    MigrationItem(
        file="init_event_taxonomy.py",
        capability="taxonomy",
        reuse="medium",
        status="active",
        description="Initialize event taxonomy from YAML config.",
    ),
    MigrationItem(
        file="archive/oneoff/migrate_event_categories.py",
        capability="taxonomy",
        reuse="low",
        status="oneoff",
        description="Backfill legacy events into new category/series structure.",
    ),
)


CAPABILITY_LABELS: dict[str, str] = {
    "schema": "Schema / DDL",
    "performance": "Performance",
    "export_sync": "Export / Sync",
    "verification": "Verification",
    "data_cleanup": "Data Cleanup",
    "data_import": "Data Import",
    "data_tagging": "Data Tagging",
    "taxonomy": "Taxonomy",
}


REUSE_LABELS: dict[str, str] = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
}
