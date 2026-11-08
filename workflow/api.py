"""HTTP interface. Run with uvicorn workflow.api:create_app --factory."""

from datetime import datetime
from pathlib import Path
from typing import Literal
import os

from fastapi import Depends, FastAPI, Header, Query
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from workflow.service import Problem, Service, parse_time
from workflow.store import Store


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(Input):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    assignee_id: StrictInt | None = None
    priority: StrictInt = Field(default=3, ge=1, le=5)
    due_at: str | None = None

    @field_validator("title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("blank title")
        return value

    @field_validator("due_at")
    @classmethod
    def due_timestamp(cls, value):
        if value is not None:
            return parse_time(value).isoformat(timespec="microseconds")
        return None


class TaskPatch(Input):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    assignee_id: StrictInt | None = None
    status: Literal["todo", "in_progress", "done"] | None = None
    priority: StrictInt | None = Field(default=None, ge=1, le=5)
    due_at: str | None = None

    @model_validator(mode="after")
    def values_present(self):
        if not self.model_fields_set:
            raise ValueError("empty patch")
        for name in self.model_fields_set - {"assignee_id", "due_at"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if "title" in self.model_fields_set and not self.title.strip():
            raise ValueError("blank title")
        if self.due_at is not None:
            self.due_at = parse_time(self.due_at).isoformat(timespec="microseconds")
        return self


class WorkInput(Input):
    minutes: StrictInt = Field(ge=1, le=480)


def create_app(db_path=None):
    app = FastAPI(title="WorkFlow API", version="0.1.0")
    path = db_path or os.environ.get("WORKFLOW_DB_PATH", str(Path("data") / "workflow.sqlite3"))
    service = Service(Store(path))
    app.state.service = service

    @app.exception_handler(Problem)
    async def problem_handler(request, exc):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    def actor(authorization: str | None = Header(default=None)):
        if authorization is None or not authorization.startswith("Bearer "):
            raise Problem(401, "authentication required")
        return service.authenticate(authorization[7:])

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/users")
    def users(user=Depends(actor)):
        return service.store.users()

    @app.post("/tasks", status_code=201)
    def create_task(body: TaskCreate, user=Depends(actor),
                    idempotency_key: str | None = Header(default=None)):
        if idempotency_key is not None and not (1 <= len(idempotency_key) <= 128 and idempotency_key.strip()):
            raise Problem(422, "invalid idempotency key")
        return service.create(user, body.model_dump(), idempotency_key)

    @app.get("/tasks")
    def tasks(q: str = Query(default="", max_length=200),
              limit: int = Query(default=20, ge=1, le=100),
              offset: int = Query(default=0, ge=0), user=Depends(actor)):
        return service.list(user, q, limit, offset)

    @app.get("/tasks/overdue")
    def overdue(at: str, user=Depends(actor)):
        try:
            parse_time(at)
        except (ValueError, TypeError):
            raise Problem(422, "timezone-aware timestamp required") from None
        return {"items": service.overdue(user, at)}

    @app.get("/tasks/export")
    def export(user=Depends(actor)):
        return Response(service.export(user), media_type="text/csv; charset=utf-8")

    @app.get("/tasks/{task_id}")
    def get_task(task_id: int, user=Depends(actor)):
        return service.get(user, task_id)

    @app.patch("/tasks/{task_id}")
    def patch_task(task_id: int, body: TaskPatch, user=Depends(actor)):
        return service.update(user, task_id, body.model_dump(exclude_unset=True))

    @app.post("/tasks/{task_id}/work")
    def add_work(task_id: int, body: WorkInput, user=Depends(actor)):
        return service.add_work(user, task_id, body.minutes)

    @app.get("/tasks/{task_id}/work")
    def work(task_id: int, user=Depends(actor)):
        return {"items": service.work(user, task_id)}

    # Read-only: no other method is routed, so history cannot be edited through the API.
    @app.get("/tasks/{task_id}/history")
    def history(task_id: int, user=Depends(actor)):
        return {"items": service.history(user, task_id)}

    return app
