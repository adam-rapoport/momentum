"""CRUD + run-now for scheduled tasks (v0.3). The execution itself lives in
app.core.scheduler; this router only manages rows and kicks manual runs."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import scheduler
from app.core.default_user import get_default_project, get_default_user
from app.dependencies import get_db
from app.models import ScheduledTask
from app.schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskRead,
    ScheduledTaskUpdate,
)

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


async def _get_task(db: AsyncSession, task_id: UUID) -> ScheduledTask:
    task = await db.get(ScheduledTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="scheduled task not found")
    return task


@router.get("", response_model=list[ScheduledTaskRead])
async def list_scheduled_tasks(db: AsyncSession = Depends(get_db)) -> list[ScheduledTask]:
    rows = await db.scalars(select(ScheduledTask).order_by(ScheduledTask.created_at))
    return list(rows.all())


@router.post("", response_model=ScheduledTaskRead, status_code=status.HTTP_201_CREATED)
async def create_scheduled_task(
    payload: ScheduledTaskCreate, db: AsyncSession = Depends(get_db)
) -> ScheduledTask:
    user = await get_default_user(db)
    if payload.project_id is None:
        project = await get_default_project(db, user.organization_id)
        project_id = project.id
    else:
        project_id = payload.project_id

    schedule = payload.schedule.model_dump()
    task = ScheduledTask(
        id=uuid4(),
        project_id=project_id,
        name=payload.name,
        prompt=payload.prompt,
        schedule=schedule,
        enabled=payload.enabled,
        catch_up_missed=payload.catch_up_missed,
        next_run_at=scheduler.compute_next_run(schedule, datetime.now(timezone.utc)),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


@router.put("/{task_id}", response_model=ScheduledTaskRead)
async def update_scheduled_task(
    task_id: UUID, payload: ScheduledTaskUpdate, db: AsyncSession = Depends(get_db)
) -> ScheduledTask:
    task = await _get_task(db, task_id)
    was_enabled = task.enabled
    if payload.name is not None:
        task.name = payload.name
    if payload.prompt is not None:
        task.prompt = payload.prompt
    if payload.catch_up_missed is not None:
        task.catch_up_missed = payload.catch_up_missed
    if payload.enabled is not None:
        task.enabled = payload.enabled
    if payload.schedule is not None:
        task.schedule = payload.schedule.model_dump()
    # A new schedule needs a fresh fire time; so does re-enabling — otherwise a
    # long-disabled task comes back with a stale next_run_at and immediately
    # "catches up" a run the user never expected.
    if payload.schedule is not None or (payload.enabled and not was_enabled):
        task.next_run_at = scheduler.compute_next_run(task.schedule, datetime.now(timezone.utc))
    await db.commit()
    await db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_task(task_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    task = await _get_task(db, task_id)
    await db.delete(task)
    await db.commit()


@router.post("/{task_id}/run-now")
async def run_scheduled_task_now(task_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    task = await _get_task(db, task_id)
    if scheduler.is_running(task.id):
        raise HTTPException(status_code=409, detail="this task is already running")
    scheduler.kick_run(task.id)
    return {"status": "started"}
