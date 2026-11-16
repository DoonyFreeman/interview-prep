"""LangGraph's account preference Store, backed by the chat database."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import timezone
import json

from langgraph.store.base import BaseStore, GetOp, Item, Op, PutOp, Result, validate_op_namespace
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.assistant.storage import AssistantPreference
from app.database import SessionLocal
from app.models import _utcnow


class AssistantStore(BaseStore):
    """Async exact-key get, put and delete for explicitly saved preferences."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    def batch(self, ops: Iterable[Op]) -> list[Result]:
        raise NotImplementedError("Use the async assistant preference operations")

    async def abatch(self, ops: Iterable[Op]) -> list[Result]:
        operations: list[tuple[GetOp | PutOp, int, str, str | None]] = []
        for op in ops:
            if not isinstance(op, (GetOp, PutOp)):
                raise NotImplementedError("Assistant preferences support exact-key get, put and delete")
            validate_op_namespace(op)
            if len(op.namespace) != 3 or op.namespace[0] != "assistant":
                raise ValueError("Expected an assistant account namespace")
            _, owner, account_key = op.namespace
            owner_id = int(owner)
            if owner_id < 1 or str(owner_id) != owner:
                raise ValueError("Expected an assistant account namespace")
            value = None
            if isinstance(op, PutOp):
                if op.ttl is not None:
                    raise NotImplementedError("Assistant preferences persist until explicitly deleted")
                if op.value is not None:
                    value = json.dumps(dict(op.value), allow_nan=False)
            operations.append((op, owner_id, account_key, value))

        if self.session is not None:
            return await self._execute(self.session, operations)
        async with SessionLocal.begin() as session:
            return await self._execute(session, operations)

    @staticmethod
    async def _execute(
        session: AsyncSession, operations: list[tuple[GetOp | PutOp, int, str, str | None]],
    ) -> list[Result]:
        results: list[Result] = []
        now = _utcnow()
        for op, owner_id, account_key, value in operations:
            scope = (
                AssistantPreference.owner_id == owner_id,
                AssistantPreference.account_key == account_key,
                AssistantPreference.key == op.key,
            )
            if isinstance(op, GetOp):
                row = await session.scalar(
                    select(AssistantPreference).where(*scope).execution_options(populate_existing=True),
                )
                results.append(Item(
                    value=json.loads(row.value_json), key=op.key, namespace=op.namespace,
                    created_at=row.created_at.replace(tzinfo=timezone.utc),
                    updated_at=row.updated_at.replace(tzinfo=timezone.utc),
                ) if row else None)
            elif value is None:
                await session.execute(delete(AssistantPreference).where(*scope))
                results.append(None)
            else:
                statement = insert(AssistantPreference).values(
                    owner_id=owner_id, account_key=account_key, key=op.key,
                    value_json=value, created_at=now, updated_at=now,
                )
                await session.execute(statement.on_conflict_do_update(
                    index_elements=[AssistantPreference.owner_id, AssistantPreference.account_key, AssistantPreference.key],
                    set_={"value_json": value, "updated_at": now},
                ))
                results.append(None)
        return results
