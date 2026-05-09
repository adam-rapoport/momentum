from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.default_user import get_default_project, get_default_user
from app.dependencies import get_db
from app.models import Message, Session
from app.schemas.session import (
    MessageRead,
    SessionCreate,
    SessionDetail,
    SessionRead,
    SessionUpdate,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)) -> Session:
    user = await get_default_user(db)
    if payload.project_id is None:
        project = await get_default_project(db, user.organization_id)
        project_id = project.id
    else:
        project_id = payload.project_id

    session = Session(
        id=uuid4(),
        user_id=user.id,
        project_id=project_id,
        title=payload.title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("", response_model=list[SessionRead])
async def list_sessions(db: AsyncSession = Depends(get_db)) -> list[Session]:
    user = await get_default_user(db)
    stmt = (
        select(Session)
        .where(Session.user_id == user.id, Session.status != "archived")
        .order_by(Session.updated_at.desc())
    )
    return list((await db.scalars(stmt)).all())


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    session = await db.scalar(select(Session).where(Session.id == session_id))
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    msg_stmt = (
        select(Message)
        .where(Message.session_id == session_id, Message.is_compacted.is_(False))
        .order_by(Message.turn_id, Message.created_at)
    )
    messages = list((await db.scalars(msg_stmt)).all())

    # The DB column "metadata" is exposed on the model as `session_metadata`
    # to avoid clashing with SQLAlchemy's reserved attribute. Skip the raw
    # column name in the loop so we don't double-emit it under the wrong key,
    # and add the renamed field by hand.
    return {
        **{
            c.name: getattr(session, c.name)
            for c in session.__table__.columns
            if c.name != "metadata"
        },
        "session_metadata": session.session_metadata or {},
        "messages": [MessageRead.model_validate(m) for m in messages],
    }


@router.patch("/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: UUID, payload: SessionUpdate, db: AsyncSession = Depends(get_db)
) -> Session:
    session = await db.scalar(select(Session).where(Session.id == session_id))
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    if payload.title is not None:
        session.title = payload.title
    if payload.status is not None:
        session.status = payload.status
    await db.commit()
    await db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_session(session_id: UUID, db: AsyncSession = Depends(get_db)) -> None:
    session = await db.scalar(select(Session).where(Session.id == session_id))
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    session.status = "archived"
    await db.commit()
