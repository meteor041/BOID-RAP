from __future__ import annotations

import json
from pathlib import Path

from boid_rap.database import DEFAULT_DB_PATH, connect
from boid_rap.domain import (
    AuditLog,
    ModelConfig,
    Report,
    ResearchJob,
    ResearchJobStatus,
    ResearchMessage,
    ResearchSession,
    SessionStatus,
    User,
    UserRole,
    WorkflowEvent,
)
from boid_rap.retrieval import RetrievalBundle, RetrievalDocument


class UserRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def save(self, user: User) -> User:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO users (id, username, password_hash, role, enabled, deleted_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.username,
                    user.password_hash,
                    user.role.value,
                    int(user.enabled),
                    user.deleted_at,
                    user.created_at,
                ),
            )
            connection.commit()
        return user

    def get_by_username(self, username: str) -> User | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return self._hydrate(row) if row else None

    def get(self, user_id: str) -> User | None:
        with connect(self.db_path) as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._hydrate(row) if row else None

    def list_all(self) -> list[User]:
        with connect(self.db_path) as connection:
            rows = connection.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [self._hydrate(row) for row in rows]

    def _hydrate(self, row) -> User:
        return User(
            id=row["id"],
            username=row["username"],
            password_hash=row["password_hash"],
            role=UserRole(row["role"]),
            enabled=bool(row["enabled"]),
            deleted_at=row["deleted_at"] if "deleted_at" in row.keys() else None,
            created_at=row["created_at"],
        )


class TokenRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def save(self, token: str, user_id: str, created_at: str, expires_at: str) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO auth_tokens (token, user_id, created_at, expires_at, revoked_at)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (token, user_id, created_at, expires_at),
            )
            connection.commit()

    def get(self, token: str):
        with connect(self.db_path) as connection:
            return connection.execute(
                "SELECT * FROM auth_tokens WHERE token = ?",
                (token,),
            ).fetchone()

    def revoke(self, token: str, revoked_at: str) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                "UPDATE auth_tokens SET revoked_at = ? WHERE token = ?",
                (revoked_at, token),
            )
            connection.commit()

    def revoke_by_user_id(self, user_id: str, revoked_at: str) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                "UPDATE auth_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (revoked_at, user_id),
            )
            connection.commit()


class ModelRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def list_all(self) -> list[ModelConfig]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM model_configs ORDER BY created_at DESC"
            ).fetchall()
        return [self._hydrate(row) for row in rows]

    def save(self, model: ModelConfig) -> ModelConfig:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO model_configs
                (id, name, provider, enabled, recommended_for, parameters, permissions, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model.id,
                    model.name,
                    model.provider,
                    int(model.enabled),
                    json.dumps(model.recommended_for, ensure_ascii=False),
                    json.dumps(model.parameters, ensure_ascii=False),
                    json.dumps(model.permissions, ensure_ascii=False),
                    model.created_at,
                ),
            )
            connection.commit()
        return model

    def get(self, model_id: str) -> ModelConfig | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM model_configs WHERE id = ?",
                (model_id,),
            ).fetchone()
        return self._hydrate(row) if row else None

    def delete(self, model_id: str) -> None:
        with connect(self.db_path) as connection:
            connection.execute("DELETE FROM model_configs WHERE id = ?", (model_id,))
            connection.commit()

    def count_usage(self, model_id: str) -> int:
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM research_sessions WHERE model_id = ?",
                (model_id,),
            ).fetchone()
        return int(row["count"])

    def _hydrate(self, row) -> ModelConfig:
        return ModelConfig(
            id=row["id"],
            name=row["name"],
            provider=row["provider"],
            enabled=bool(row["enabled"]),
            recommended_for=json.loads(row["recommended_for"]),
            parameters=json.loads(row["parameters"]),
            permissions=json.loads(row["permissions"]),
            created_at=row["created_at"],
        )


class SessionRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def save(self, session: ResearchSession) -> ResearchSession:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO research_sessions
                (id, user_id, object_name, object_type, model_id, time_range, authority_level,
                 depth, focus_areas, query, status, report_id, retrieval_provider, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.user_id,
                    session.object_name,
                    session.object_type.value
                    if hasattr(session.object_type, "value")
                    else session.object_type,
                    session.model_id,
                    session.time_range,
                    session.authority_level,
                    session.depth,
                    json.dumps(session.focus_areas, ensure_ascii=False),
                    session.query,
                    session.status.value if hasattr(session.status, "value") else session.status,
                    session.report_id,
                    session.retrieval_provider,
                    session.created_at,
                    session.updated_at,
                ),
            )

            connection.execute("DELETE FROM research_messages WHERE session_id = ?", (session.id,))
            for message in session.messages:
                connection.execute(
                    """
                    INSERT INTO research_messages (session_id, role, content, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session.id, message.role, message.content, message.created_at),
                )

            connection.execute("DELETE FROM workflow_events WHERE session_id = ?", (session.id,))
            for event in session.workflow:
                connection.execute(
                    """
                    INSERT INTO workflow_events (session_id, stage, detail, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session.id, event.stage, event.detail, event.created_at),
                )
            connection.commit()
        return session

    def get(self, session_id: str) -> ResearchSession | None:
        with connect(self.db_path) as connection:
            session_row = connection.execute(
                "SELECT * FROM research_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if not session_row:
                return None
            message_rows = connection.execute(
                "SELECT * FROM research_messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            workflow_rows = connection.execute(
                "SELECT * FROM workflow_events WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return self._hydrate(session_row, message_rows, workflow_rows)

    def list_filtered(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: str | None = None,
        object_type: str | None = None,
        model_id: str | None = None,
        status: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[ResearchSession]:
        clauses: list[str] = []
        params: list[str | int] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if object_type:
            clauses.append("object_type = ?")
            params.append(object_type)
        if model_id:
            clauses.append("model_id = ?")
            params.append(model_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)

        sql = "SELECT id FROM research_sessions"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with connect(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return self._load_sessions(rows)

    def count_filtered(
        self,
        user_id: str | None = None,
        object_type: str | None = None,
        model_id: str | None = None,
        status: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list[str] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if object_type:
            clauses.append("object_type = ?")
            params.append(object_type)
        if model_id:
            clauses.append("model_id = ?")
            params.append(model_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)

        sql = "SELECT COUNT(*) AS count FROM research_sessions"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with connect(self.db_path) as connection:
            row = connection.execute(sql, params).fetchone()
        return int(row["count"])

    def _load_sessions(self, rows) -> list[ResearchSession]:
        items: list[ResearchSession] = []
        for row in rows:
            session = self.get(row["id"])
            if session is not None:
                items.append(session)
        return items

    def _hydrate(self, session_row, message_rows, workflow_rows) -> ResearchSession:
        return ResearchSession(
            id=session_row["id"],
            user_id=session_row["user_id"],
            object_name=session_row["object_name"],
            object_type=session_row["object_type"],
            model_id=session_row["model_id"],
            retrieval_provider=(
                session_row["retrieval_provider"] if "retrieval_provider" in session_row.keys() else None
            ),
            time_range=session_row["time_range"],
            authority_level=session_row["authority_level"],
            depth=session_row["depth"],
            focus_areas=json.loads(session_row["focus_areas"]),
            query=session_row["query"],
            status=SessionStatus(session_row["status"]),
            messages=[
                ResearchMessage(
                    role=row["role"],
                    content=row["content"],
                    created_at=row["created_at"],
                )
                for row in message_rows
            ],
            workflow=[
                WorkflowEvent(
                    stage=row["stage"],
                    detail=row["detail"],
                    created_at=row["created_at"],
                )
                for row in workflow_rows
            ],
            report_id=session_row["report_id"],
            created_at=session_row["created_at"],
            updated_at=session_row["updated_at"],
        )


class ReportRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def save(self, report: Report) -> Report:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO reports
                (id, session_id, title, summary, body, conclusion, citations, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.id,
                    report.session_id,
                    report.title,
                    report.summary,
                    json.dumps(report.body, ensure_ascii=False),
                    report.conclusion,
                    json.dumps(report.citations, ensure_ascii=False),
                    report.created_at,
                ),
            )
            connection.commit()
        return report

    def list_filtered(
        self,
        limit: int = 100,
        offset: int = 0,
        session_ids: list[str] | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[Report]:
        clauses: list[str] = []
        params: list[str | int] = []
        if session_ids is not None:
            if not session_ids:
                return []
            placeholders = ",".join("?" for _ in session_ids)
            clauses.append(f"session_id IN ({placeholders})")
            params.extend(session_ids)
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)

        sql = "SELECT * FROM reports"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with connect(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._hydrate(row) for row in rows]

    def count_filtered(
        self,
        session_ids: list[str] | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list[str] = []
        if session_ids is not None:
            if not session_ids:
                return 0
            placeholders = ",".join("?" for _ in session_ids)
            clauses.append(f"session_id IN ({placeholders})")
            params.extend(session_ids)
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)

        sql = "SELECT COUNT(*) AS count FROM reports"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with connect(self.db_path) as connection:
            row = connection.execute(sql, params).fetchone()
        return int(row["count"])

    def get(self, report_id: str) -> Report | None:
        with connect(self.db_path) as connection:
            row = connection.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return self._hydrate(row) if row else None

    def _hydrate(self, row) -> Report:
        return Report(
            id=row["id"],
            session_id=row["session_id"],
            title=row["title"],
            summary=row["summary"],
            body=json.loads(row["body"]),
            conclusion=row["conclusion"],
            citations=json.loads(row["citations"]),
            created_at=row["created_at"],
        )


class ResearchJobRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def save(self, job: ResearchJob) -> ResearchJob:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO research_jobs
                (id, session_id, user_id, status, progress, current_stage, force_refresh, cancel_requested, error_message, report_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.session_id,
                    job.user_id,
                    job.status.value if hasattr(job.status, "value") else job.status,
                    job.progress,
                    job.current_stage,
                    int(job.force_refresh),
                    int(job.cancel_requested),
                    job.error_message,
                    job.report_id,
                    job.created_at,
                    job.updated_at,
                ),
            )
            connection.commit()
        return job

    def get(self, job_id: str) -> ResearchJob | None:
        with connect(self.db_path) as connection:
            row = connection.execute("SELECT * FROM research_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._hydrate(row) if row else None

    def list_filtered(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
    ) -> list[ResearchJob]:
        clauses: list[str] = []
        params: list[str | int] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        sql = "SELECT * FROM research_jobs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with connect(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._hydrate(row) for row in rows]

    def count_filtered(
        self,
        user_id: str | None = None,
        session_id: str | None = None,
        status: str | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list[str] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        sql = "SELECT COUNT(*) AS count FROM research_jobs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with connect(self.db_path) as connection:
            row = connection.execute(sql, params).fetchone()
        return int(row["count"])

    def get_latest_for_session(self, session_id: str) -> ResearchJob | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM research_jobs WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return self._hydrate(row) if row else None

    def _hydrate(self, row) -> ResearchJob:
        return ResearchJob(
            id=row["id"],
            session_id=row["session_id"],
            user_id=row["user_id"],
            status=ResearchJobStatus(row["status"]),
            progress=int(row["progress"]),
            current_stage=row["current_stage"],
            force_refresh=bool(row["force_refresh"]) if "force_refresh" in row.keys() else False,
            cancel_requested=bool(row["cancel_requested"]) if "cancel_requested" in row.keys() else False,
            error_message=row["error_message"],
            report_id=row["report_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class RetrievalResultRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def save(
        self,
        job_id: str,
        session_id: str,
        bundle: RetrievalBundle,
        cache_key: str | None = None,
        cache_hit: bool = False,
    ) -> dict:
        payload = bundle.to_dict()
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO research_job_retrieval_results
                (job_id, session_id, provider, bundle_json, created_at, cache_key, cache_hit)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    session_id,
                    bundle.provider,
                    json.dumps(payload, ensure_ascii=False),
                    bundle.created_at,
                    cache_key,
                    int(cache_hit),
                ),
            )
            connection.commit()
        return payload

    def get_by_job_id(self, job_id: str) -> dict | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM research_job_retrieval_results WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["bundle_json"])
        payload["job_id"] = row["job_id"]
        payload["session_id"] = row["session_id"]
        payload["cache_key"] = row["cache_key"] if "cache_key" in row.keys() else None
        return payload

    def get_latest_by_cache_key(self, cache_key: str) -> dict | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM research_job_retrieval_results
                WHERE cache_key = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (cache_key,),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["bundle_json"])
        payload["job_id"] = row["job_id"]
        payload["session_id"] = row["session_id"]
        payload["cache_key"] = row["cache_key"] if "cache_key" in row.keys() else None
        return payload

    def list_by_session_id(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
        provider: str | None = None,
        cache_hit: bool | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[dict]:
        clauses = ["session_id = ?"]
        params: list[str | int] = [session_id]
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        if cache_hit is not None:
            clauses.append("cache_hit = ?")
            params.append(int(cache_hit))
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)
        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM research_job_retrieval_results
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return [self._row_to_payload(row) for row in rows]

    def count_by_session_id(
        self,
        session_id: str,
        provider: str | None = None,
        cache_hit: bool | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> int:
        clauses = ["session_id = ?"]
        params: list[str | int] = [session_id]
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        if cache_hit is not None:
            clauses.append("cache_hit = ?")
            params.append(int(cache_hit))
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)
        with connect(self.db_path) as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM research_job_retrieval_results
                WHERE {' AND '.join(clauses)}
                """,
                params,
            ).fetchone()
        return int(row["count"])

    @staticmethod
    def _row_to_payload(row) -> dict:
        payload = json.loads(row["bundle_json"])
        payload["job_id"] = row["job_id"]
        payload["session_id"] = row["session_id"]
        payload["cache_key"] = row["cache_key"] if "cache_key" in row.keys() else None
        payload["cache_hit"] = bool(row["cache_hit"]) if "cache_hit" in row.keys() else False
        return payload


class AuditLogRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def save(self, log: AuditLog) -> AuditLog:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO audit_logs (id, actor_user_id, action, resource_type, resource_id, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log.id,
                    log.actor_user_id,
                    log.action,
                    log.resource_type,
                    log.resource_id,
                    log.detail,
                    log.created_at,
                ),
            )
            connection.commit()
        return log

    def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        actor_user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> list[AuditLog]:
        clauses: list[str] = []
        params: list[str | int] = []
        if actor_user_id:
            clauses.append("actor_user_id = ?")
            params.append(actor_user_id)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if resource_type:
            clauses.append("resource_type = ?")
            params.append(resource_type)
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)

        sql = "SELECT * FROM audit_logs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with connect(self.db_path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._hydrate(row) for row in rows]

    def count_all(
        self,
        actor_user_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list[str] = []
        if actor_user_id:
            clauses.append("actor_user_id = ?")
            params.append(actor_user_id)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if resource_type:
            clauses.append("resource_type = ?")
            params.append(resource_type)
        if created_from:
            clauses.append("created_at >= ?")
            params.append(created_from)
        if created_to:
            clauses.append("created_at <= ?")
            params.append(created_to)

        sql = "SELECT COUNT(*) AS count FROM audit_logs"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        with connect(self.db_path) as connection:
            row = connection.execute(sql, params).fetchone()
        return int(row["count"])

    def _hydrate(self, row) -> AuditLog:
        return AuditLog(
            id=row["id"],
            actor_user_id=row["actor_user_id"],
            action=row["action"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            detail=row["detail"],
            created_at=row["created_at"],
        )
