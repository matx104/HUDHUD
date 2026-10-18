"""Audit trail: every output of a match kept, with its evidence, off the hot path (ADR 0004).

The trail tees the Orchestrator's sink. Each output reaches the broadcast first, then joins a
queue that a background task writes to the store, so a slow or failing store never holds up a
cue. If the store fails, the trail stops writing, counts what it dropped and reports it at the
end of the run; the match goes on regardless.

A run writes a `run` record first, then one record per output (cue, rejection, spiked,
degradation), then a `summary`. Records are partitioned by match, so one query gives a match's
whole story, including what the Critic refused, not only what aired.

    pip install -e "apps/api[audit]"    # azure-cosmos, azure-identity, aiohttp
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from match_events import MatchMeta

from .config import product_name
from .contracts import OUTPUT_ADAPTER, Output


class AuditStore(Protocol):
    async def write(self, record: dict[str, Any]) -> None: ...
    async def close(self) -> None: ...


class MemoryStore:
    """Keeps records in a list: tests, and runs with no cloud."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def write(self, record: dict[str, Any]) -> None:
        self.records.append(record)

    async def close(self) -> None:
        return None


class CosmosStore:
    """The `audit` container of the free-tier Azure Cosmos DB account. Entra ID only: the account
    has keys disabled, and the caller needs the built-in Data Contributor role."""

    def __init__(self, endpoint: str, *, database: str = "hudhud", container: str = "audit"):
        from azure.cosmos.aio import CosmosClient
        from azure.identity.aio import AzureCliCredential

        # Pinned to the project's tenant when known, as the Foundry narrator is.
        self._credential = AzureCliCredential(tenant_id=os.environ.get("AZURE_TENANT_ID") or None)
        self._client = CosmosClient(endpoint, credential=self._credential)
        self._container = self._client.get_database_client(database).get_container_client(container)

    async def write(self, record: dict[str, Any]) -> None:
        await self._container.create_item(record)

    async def close(self) -> None:
        await self._client.close()
        await self._credential.close()


class AuditTrail:
    def __init__(
        self,
        store: AuditStore,
        meta: MatchMeta,
        *,
        narrator: str,
        write_timeout_s: float = 10.0,
    ) -> None:
        self.store = store
        self.match_id = meta.match_id
        self.run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:6]}"
        self.write_timeout_s = write_timeout_s
        self.written = 0
        self.dropped = 0
        self.failure: str | None = None
        self._seq = 0
        self._queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._writer: asyncio.Task[None] | None = None
        self._enqueue(
            "run",
            {
                "product": product_name(),
                "narrator": narrator,
                "seed": meta.seed,
                "home": meta.home.name,
                "away": meta.away.name,
                "synthetic": True,
            },
        )

    def tee(self, sink):
        """The Orchestrator's sink, wrapped: the broadcast first, the trail second."""

        def both(output: Output) -> None:
            sink(output)
            self.record(output)

        return both

    def record(self, output: Output) -> None:
        body = OUTPUT_ADAPTER.dump_python(output, mode="json")
        self._enqueue(body.pop("type"), body)

    def start(self) -> None:
        self._writer = asyncio.create_task(self._write_all())

    async def close(self, summary: dict[str, Any], *, timeout_s: float = 30.0) -> None:
        """Write the summary, then wait for the queue to drain (or give up after timeout_s)."""
        self._enqueue("summary", summary)
        self._queue.put_nowait(None)
        if self._writer is None:
            self.start()
        try:
            await asyncio.wait_for(self._writer, timeout=timeout_s)
        except TimeoutError:
            self._writer.cancel()
            self.failure = self.failure or f"the store didn't finish within {timeout_s:.0f} s"
            self.dropped += self._queue.qsize()
        finally:
            await self.store.close()

    def report(self) -> str:
        if self.failure:
            return f"{self.written} records kept, {self.dropped} dropped: {self.failure}"
        return f"{self.written} records kept (run {self.run_id})"

    def _enqueue(self, kind: str, body: dict[str, Any]) -> None:
        self._seq += 1
        record = {
            "id": f"{self.run_id}-{self._seq:04d}",
            "matchId": self.match_id,
            "runId": self.run_id,
            "seq": self._seq,
            "type": kind,
            "recordedAt": datetime.now(UTC).isoformat(),
            **body,
        }
        self._queue.put_nowait(record)

    async def _write_all(self) -> None:
        while (record := await self._queue.get()) is not None:
            if self.failure:
                self.dropped += 1
                continue
            try:
                await asyncio.wait_for(self.store.write(record), timeout=self.write_timeout_s)
                self.written += 1
            except Exception as error:  # a store failure costs the trail, never the broadcast
                self.failure = f"{type(error).__name__}: {error}".splitlines()[0][:200]
                self.dropped += 1
