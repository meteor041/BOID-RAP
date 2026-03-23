from __future__ import annotations

import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path("data/boid_rap.db")

MIGRATIONS: list[tuple[str, str]] = [
    (
        "001_initial_schema",
        """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS model_configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    recommended_for TEXT NOT NULL,
    parameters TEXT NOT NULL,
    permissions TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    object_name TEXT NOT NULL,
    object_type TEXT NOT NULL,
    model_id TEXT NOT NULL,
    time_range TEXT NOT NULL,
    authority_level TEXT NOT NULL,
    depth TEXT NOT NULL,
    focus_areas TEXT NOT NULL,
    query TEXT NOT NULL,
    status TEXT NOT NULL,
    report_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(model_id) REFERENCES model_configs(id)
);

CREATE TABLE IF NOT EXISTS research_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES research_sessions(id)
);

CREATE TABLE IF NOT EXISTS workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES research_sessions(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    body TEXT NOT NULL,
    conclusion TEXT NOT NULL,
    citations TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES research_sessions(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor_user_id TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(actor_user_id) REFERENCES users(id)
);
""",
    ),
    (
        "002_user_soft_delete",
        """
ALTER TABLE users ADD COLUMN deleted_at TEXT;
""",
    ),
    (
        "003_research_jobs",
        """
CREATE TABLE IF NOT EXISTS research_jobs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL,
    current_stage TEXT NOT NULL,
    error_message TEXT,
    report_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES research_sessions(id),
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(report_id) REFERENCES reports(id)
);
""",
    ),
    (
        "004_research_job_cancel",
        """
ALTER TABLE research_jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0;
""",
    ),
    (
        "005_session_retrieval_provider",
        """
ALTER TABLE research_sessions ADD COLUMN retrieval_provider TEXT;
""",
    ),
    (
        "006_job_retrieval_results",
        """
CREATE TABLE IF NOT EXISTS research_job_retrieval_results (
    job_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    bundle_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES research_jobs(id),
    FOREIGN KEY(session_id) REFERENCES research_sessions(id)
);
""",
    ),
    (
        "007_retrieval_result_cache_key",
        """
ALTER TABLE research_job_retrieval_results ADD COLUMN cache_key TEXT;
""",
    ),
    (
        "008_research_job_force_refresh",
        """
ALTER TABLE research_jobs ADD COLUMN force_refresh INTEGER NOT NULL DEFAULT 0;
""",
    ),
    (
        "009_retrieval_result_cache_hit",
        """
ALTER TABLE research_job_retrieval_results ADD COLUMN cache_hit INTEGER NOT NULL DEFAULT 0;
""",
    ),
]


def _ensure_migrations_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def list_applied_migrations(db_path: Path = DEFAULT_DB_PATH) -> list[str]:
    if not db_path.exists():
        return []
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        _ensure_migrations_table(connection)
        rows = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY applied_at ASC"
        ).fetchall()
        return [row["version"] for row in rows]
    finally:
        connection.close()


def apply_migrations(db_path: Path = DEFAULT_DB_PATH) -> list[str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    applied_versions: list[str] = []
    try:
        _ensure_migrations_table(connection)
        existing = {
            row["version"]
            for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for version, sql in MIGRATIONS:
            if version in existing:
                continue
            try:
                connection.executescript(sql)
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
                (version,),
            )
            applied_versions.append(version)
        connection.commit()
    finally:
        connection.close()
    return applied_versions


def initialize_database(db_path: Path = DEFAULT_DB_PATH) -> Path:
    apply_migrations(db_path)
    return db_path


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection
