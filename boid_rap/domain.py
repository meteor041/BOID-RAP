from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ObjectType(str, Enum):
    COMPANY = "company"
    STOCK = "stock"
    COMMODITY = "commodity"


class SessionStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"


class ResearchJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"


@dataclass
class ModelConfig:
    name: str
    provider: str
    enabled: bool = True
    recommended_for: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    permissions: list[str] = field(default_factory=lambda: ["user"])
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchMessage:
    role: str
    content: str
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowEvent:
    stage: str
    detail: str
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchSession:
    user_id: str
    object_name: str
    object_type: ObjectType | str
    model_id: str
    time_range: str
    authority_level: str
    depth: str
    retrieval_provider: str | None = None
    focus_areas: list[str] = field(default_factory=list)
    query: str = ""
    status: SessionStatus | str = SessionStatus.DRAFT
    messages: list[ResearchMessage] = field(default_factory=list)
    workflow: list[WorkflowEvent] = field(default_factory=list)
    report_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["object_type"] = (
            self.object_type.value if isinstance(self.object_type, ObjectType) else self.object_type
        )
        data["status"] = self.status.value if isinstance(self.status, SessionStatus) else self.status
        return data


@dataclass
class Report:
    session_id: str
    title: str
    summary: str
    body: list[dict[str, str]]
    conclusion: str
    citations: list[dict[str, str]]
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class User:
    username: str
    password_hash: str
    role: UserRole = UserRole.USER
    enabled: bool = True
    deleted_at: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value
        data.pop("password_hash", None)
        return data


@dataclass
class AuditLog:
    actor_user_id: str | None
    action: str
    resource_type: str
    resource_id: str
    detail: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchJob:
    session_id: str
    user_id: str
    status: ResearchJobStatus | str = ResearchJobStatus.QUEUED
    progress: int = 0
    current_stage: str = "queued"
    force_refresh: bool = False
    cancel_requested: bool = False
    error_message: str | None = None
    report_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, ResearchJobStatus) else self.status
        return data
