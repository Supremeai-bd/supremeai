from __future__ import annotations

from types import SimpleNamespace

import pytest

from database.db_repository import SmartDataRepository


class FakeDoc:
    def __init__(self, exists: bool, data: dict | None = None):
        self.exists = exists
        self._data = data or {}

    def to_dict(self):
        return self._data


class FakeFirebaseDocRef:
    def __init__(self, doc_id: str, should_error: bool = False, exists: bool = True):
        self.doc_id = doc_id
        self.should_error = should_error
        self.exists = exists

    def get(self):
        if self.should_error:
            raise RuntimeError("firebase down")
        return FakeDoc(self.exists, {"id": self.doc_id, "value": "primary"})

    def document(self, doc_id: str):
        return self


class FakeFirebase:
    def __init__(self, should_error: bool = False, exists: bool = True):
        self.should_error = should_error
        self.exists = exists

    def collection(self, collection_name: str):
        return FakeFirebaseDocRef(
            collection_name, should_error=self.should_error, exists=self.exists
        )


class FakeSupabaseTable:
    def __init__(self, data: list[dict]):
        self._data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key: str, value: str):
        self._filter = (key, value)
        return self

    async def execute(self):
        return SimpleNamespace(data=self._data)


class FakeSupabaseClient:
    def __init__(self, data: list[dict] | None = None):
        self._data = data or []

    def table(self, table_name: str):
        return FakeSupabaseTable(self._data)


@pytest.mark.asyncio
async def test_fetch_from_primary_async_doc_returns_document():
    firebase = FakeFirebase(should_error=False, exists=True)
    supabase = FakeSupabaseClient()
    repo = SmartDataRepository(firebase_client=firebase, supabase_client=supabase)

    result = await repo.get_document_with_fallback("users", "abc")
    assert result == {"id": "users", "value": "primary"}


@pytest.mark.asyncio
async def test_get_document_with_fallback_uses_supabase_on_primary_failure():
    firebase = FakeFirebase(should_error=True)
    supabase = FakeSupabaseClient(data=[{"id": "abc", "name": "backup"}])
    repo = SmartDataRepository(firebase_client=firebase, supabase_client=supabase)

    result = await repo.get_document_with_fallback("users", "abc")
    assert result == {"id": "abc", "name": "backup"}


@pytest.mark.asyncio
async def test_get_document_with_fallback_returns_none_when_both_down():
    firebase = FakeFirebase(should_error=True)

    class BrokenSupabase:
        pass

    repo = SmartDataRepository(firebase_client=firebase, supabase_client=BrokenSupabase())
    result = await repo.get_document_with_fallback("users", "abc")
    assert result is None
