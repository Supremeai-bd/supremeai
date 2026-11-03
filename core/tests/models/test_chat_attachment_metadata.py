"""M2-A — chat_attachments context-metadata model tests (offline, sqlite).

The ORM mirror of the tier_s_features ``chat_attachments`` table (now the
canonical files-metadata surface for the M2 Context Engine). Dedicated
sqlite engine with ONLY the chat_attachments table (self-referential
parent_id FK needs the pragma for the cascade-free SET NULL behavior).

Covers: legacy-column compat (the raw-Supabase writer's columns keep
working), L0/L1/L2 columns round-trip, hash/version defaults, parent
self-reference, scope anchors, and unique-ish user scoping queries the
Context Engine will issue.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from models.base import Base
from models.chat_attachment import ChatAttachment


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _fk_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync: Base.metadata.create_all(sync, tables=[ChatAttachment.__table__])
        )
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as session:
        yield session
    await engine.dispose()


def _mk(**overrides) -> ChatAttachment:
    defaults = {
        "user_id": "user-1",
        "file_name": "report.pdf",
        "file_path": "/ide/t1/uploads/report.pdf",
        "file_size": 1024,
        "mime_type": "application/pdf",
    }
    defaults.update(overrides)
    return ChatAttachment(**defaults)


class TestLegacyCompat:
    @pytest.mark.asyncio
    async def test_legacy_writer_columns_work(self, db_session: AsyncSession):
        """The raw-Supabase writer's column set keeps working unchanged."""
        att = _mk()
        db_session.add(att)
        await db_session.flush()
        assert att.id is not None
        assert att.created_at is not None
        assert att.version == 1  # new column server-defaulted client-side

    @pytest.mark.asyncio
    async def test_user_id_required(self, db_session: AsyncSession):
        att = ChatAttachment(
            file_name="x",
            file_path="/x",
            file_size=1,
            mime_type="text/plain",
        )
        db_session.add(att)
        with pytest.raises(Exception, match="NOT NULL"):
            await db_session.flush()


class TestContextMetadata:
    @pytest.mark.asyncio
    async def test_l0_l1_l2_roundtrip(self, db_session: AsyncSession):
        l1 = {"sections": ["intro", "findings"], "entities": ["ACME"], "keywords": ["revenue"]}
        att = _mk(
            summary_l0="Quarterly revenue report for ACME.",
            summary_l1=l1,
            content_ref="ref://files/att-1/raw",
        )
        db_session.add(att)
        await db_session.flush()
        await db_session.refresh(att)
        assert att.summary_l0 == "Quarterly revenue report for ACME."
        assert att.summary_l1 == l1
        assert att.content_ref == "ref://files/att-1/raw"

    @pytest.mark.asyncio
    async def test_hash_and_version(self, db_session: AsyncSession):
        att = _mk(content_hash="a" * 64, version=3)
        db_session.add(att)
        await db_session.flush()
        await db_session.refresh(att)
        assert att.content_hash == "a" * 64
        assert att.version == 3

    @pytest.mark.asyncio
    async def test_parent_self_reference(self, db_session: AsyncSession):
        parent = _mk(file_name="folder-docs")
        db_session.add(parent)
        await db_session.flush()
        child = _mk(file_name="child.pdf", parent_id=parent.id)
        db_session.add(child)
        await db_session.flush()
        await db_session.refresh(child)
        assert child.parent_id == parent.id

    @pytest.mark.asyncio
    async def test_scope_anchors(self, db_session: AsyncSession):
        att = _mk(workspace_id="ws-1", project_id="proj-9")
        db_session.add(att)
        await db_session.flush()
        await db_session.refresh(att)
        assert att.workspace_id == "ws-1"
        assert att.project_id == "proj-9"


class TestContextQueries:
    @pytest.mark.asyncio
    async def test_user_scoped_query(self, db_session: AsyncSession):
        """The tenant filter the Context Engine must always apply."""
        db_session.add(_mk(user_id="user-1", file_name="mine.txt"))
        db_session.add(_mk(user_id="user-2", file_name="theirs.txt"))
        await db_session.flush()
        rows = (
            (
                await db_session.execute(
                    select(ChatAttachment).where(ChatAttachment.user_id == "user-1")
                )
            )
            .scalars()
            .all()
        )
        assert [r.file_name for r in rows] == ["mine.txt"]

    @pytest.mark.asyncio
    async def test_scope_chain_query(self, db_session: AsyncSession):
        """WORKSPACE/PROJECT scoping queries return the right items."""
        db_session.add(_mk(user_id="u", workspace_id="ws-1", file_name="a"))
        db_session.add(_mk(user_id="u", workspace_id="ws-2", file_name="b"))
        db_session.add(_mk(user_id="u", project_id="proj-9", file_name="c"))
        await db_session.flush()
        ws_rows = (
            (
                await db_session.execute(
                    select(ChatAttachment).where(ChatAttachment.workspace_id == "ws-1")
                )
            )
            .scalars()
            .all()
        )
        assert [r.file_name for r in ws_rows] == ["a"]
        proj_rows = (
            (
                await db_session.execute(
                    select(ChatAttachment).where(ChatAttachment.project_id == "proj-9")
                )
            )
            .scalars()
            .all()
        )
        assert [r.file_name for r in proj_rows] == ["c"]

    @pytest.mark.asyncio
    async def test_dedup_by_hash(self, db_session: AsyncSession):
        """content_hash supports the Context Engine's dedup lookup."""
        db_session.add(_mk(content_hash="h" * 64, file_name="first.bin"))
        db_session.add(_mk(content_hash="h" * 64, file_name="second.bin"))
        await db_session.flush()
        dupes = (
            (
                await db_session.execute(
                    select(ChatAttachment).where(ChatAttachment.content_hash == "h" * 64)
                )
            )
            .scalars()
            .all()
        )
        assert len(dupes) == 2
