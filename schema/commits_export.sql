-- Minimal privacy-aware commit export for git-calculator–style analytics.
-- See docs/adr/0001-minimal-commit-storage-schema.md for semantics and tradeoffs.
--
-- committed_at: Unix seconds from git %ct (committer instant in UTC epoch).
-- committer_tz_offset: optional git-style offset e.g. -0500 (%z) for local-time heuristics.
-- parent_count: must equal number of SHAs in parent_shas (exporter-enforced invariant).
-- parent_shas: space-separated full SHAs, Git order; '' when parent_count = 0.
-- conventional_type_scope: where/how conventional_type was derived (see ADR); NULL iff conventional_type IS NULL.
-- pii_protection_profile: caller-chosen tier (none → advanced); see ADR — dictates how author_ref / author_label_pii are populated.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS commits_export (
    repo_slug TEXT NOT NULL,
    sha TEXT NOT NULL,
    parent_shas TEXT NOT NULL,
    parent_count INTEGER NOT NULL CHECK (parent_count >= 0),
    committed_at INTEGER NOT NULL,
    committer_tz_offset TEXT,
    pii_protection_profile TEXT NOT NULL CHECK (pii_protection_profile IN (
        'none',
        'pseudonym_hmac',
        'pseudonym_hmac_strict',
        'encrypted_identity'
    )),
    author_ref TEXT NOT NULL,
    author_label_pii TEXT,
    subject_has_keywords INTEGER NOT NULL CHECK (subject_has_keywords IN (0, 1)),
    body_has_keywords INTEGER NOT NULL CHECK (body_has_keywords IN (0, 1)),
    conventional_type TEXT,
    conventional_type_scope TEXT CHECK (
        conventional_type_scope IS NULL OR conventional_type_scope IN (
            'subject',
            'body',
            'subject_and_body',
            'subject_or_body_subject',
            'subject_or_body_body'
        )
    ),
    schema_version INTEGER NOT NULL,
    tenant_id TEXT,
    PRIMARY KEY (repo_slug, sha)
);

CREATE INDEX IF NOT EXISTS idx_commits_export_repo_time
    ON commits_export (repo_slug, committed_at);

CREATE INDEX IF NOT EXISTS idx_commits_export_repo_author
    ON commits_export (repo_slug, author_ref);

CREATE INDEX IF NOT EXISTS idx_commits_export_repo_parent_count
    ON commits_export (repo_slug, parent_count);

-- One row per parent edge; enables SQL joins and recursive CTEs without parsing parent_shas.
-- Invariant: COUNT(*) per (repo_slug, child_sha) = parent_count on commits_export; parent_ord is Git order (0 = first parent).
CREATE TABLE IF NOT EXISTS commit_parent_edges (
    repo_slug TEXT NOT NULL,
    child_sha TEXT NOT NULL,
    parent_sha TEXT NOT NULL,
    parent_ord INTEGER NOT NULL CHECK (parent_ord >= 0),
    PRIMARY KEY (repo_slug, child_sha, parent_ord),
    FOREIGN KEY (repo_slug, child_sha) REFERENCES commits_export (repo_slug, sha)
);

CREATE INDEX IF NOT EXISTS idx_commit_parent_edges_by_parent
    ON commit_parent_edges (repo_slug, parent_sha);

-- Optional snapshot of ref tips at export time (same semantics as `git branch -a` objectname → ref).
CREATE TABLE IF NOT EXISTS refs_export (
    repo_slug TEXT NOT NULL,
    export_id TEXT NOT NULL,
    ref_name TEXT NOT NULL,
    tip_sha TEXT NOT NULL,
    exported_at INTEGER NOT NULL,
    tenant_id TEXT,
    PRIMARY KEY (repo_slug, export_id, ref_name)
);

CREATE INDEX IF NOT EXISTS idx_refs_export_repo_export
    ON refs_export (repo_slug, export_id);
