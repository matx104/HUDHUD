"""The match ledger: a match's history, chained by hashes so a changed byte shows (ADR 0013).

Blockchain's integrity, without a blockchain: no coin, no mining, no network to pay. What it keeps
is the part that makes a chain trustworthy:

- **Every entry is hashed.** The match itself (its meta), every event, every line that aired,
  every claim the Critic refused, every change of service, every answer to a viewer's question and
  the recap. An entry is its JSON in one canonical form (keys sorted, no spaces); its leaf hash is
  SHA-256 over a 0x00 byte and that text.
- **Each minute is a block.** A block's entries are sealed by their Merkle root, built as
  Certificate Transparency builds its logs (RFC 6962: leaves under 0x00, nodes under 0x01, the
  largest power of two on the left). The block's header (height, minute, how many entries, the
  root, the previous block's hash, when it was sealed) is hashed in turn.
- **Each block names the one before it.** Change any entry in any block and its root changes, so
  its block's hash, so every block after it. The last block's hash is the match's seal: one value
  that stands for the whole history.
- **Anyone can check it.** An entry's inclusion proof (its Merkle path, then the headers to the
  seal) is a few hundred bytes. The whole ledger verifies offline, here (`verify`, or
  `python -m court verify`) or in a browser, and a synthetic match's events can be generated again
  from its seed: the ledger must hold exactly those events.

The ledger records the court's outputs as the court made them, before any viewer's personal view.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

VERSION = 1
GENESIS_PREV = "0" * 64


def canonical(item: Any) -> str:
    """One text for one value: keys sorted, no spaces, UTF-8 as written."""
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def leaf_hash(text: str) -> str:
    return hashlib.sha256(b"\x00" + text.encode()).hexdigest()


def node_hash(left: str, right: str) -> str:
    return hashlib.sha256(b"\x01" + bytes.fromhex(left) + bytes.fromhex(right)).hexdigest()


def _split(n: int) -> int:
    """The largest power of two smaller than n (n > 1)."""
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def merkle_root(leaves: list[str]) -> str:
    """RFC 6962's Merkle Tree Hash over leaf hashes."""
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    if len(leaves) == 1:
        return leaves[0]
    k = _split(len(leaves))
    return node_hash(merkle_root(leaves[:k]), merkle_root(leaves[k:]))


def inclusion_path(leaves: list[str], index: int) -> list[str]:
    """RFC 6962's audit path for the leaf at index: the sibling roots, leaf to top."""
    if len(leaves) <= 1:
        return []
    k = _split(len(leaves))
    if index < k:
        return [*inclusion_path(leaves[:k], index), merkle_root(leaves[k:])]
    return [*inclusion_path(leaves[k:], index - k), merkle_root(leaves[:k])]


def verify_inclusion(leaf: str, index: int, size: int, path: list[str], root: str) -> bool:
    """RFC 9162 §2.1.3.2: does the path prove the leaf at index in a tree of size with root?"""
    if index >= size:
        return False
    fn, sn, r = index, size - 1, leaf
    for p in path:
        if sn == 0:
            return False
        if fn & 1 or fn == sn:
            r = node_hash(p, r)
            if not fn & 1:
                while not fn & 1 and fn != 0:
                    fn, sn = fn >> 1, sn >> 1
        else:
            r = node_hash(r, p)
        fn, sn = fn >> 1, sn >> 1
    return sn == 0 and r == root


def header_hash(header: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(header).encode()).hexdigest()


@dataclass
class Entry:
    kind: str  # meta, event, cue, rejection, spiked, degradation, answer, recap
    id: str
    text: str  # the canonical JSON: what the leaf hash is over
    leaf: str


@dataclass
class Block:
    header: dict[str, Any]  # height, minute, count, root, prev, at
    hash: str
    entries: list[Entry] = field(default_factory=list)


def entry_id(kind: str, natural: str) -> str:
    """Events keep their own ids (e00042); everything else is named by its kind as well."""
    return natural if kind == "event" else f"{kind}:{natural}"


class Ledger:
    def __init__(self, meta: dict[str, Any], *, at: datetime | None = None) -> None:
        self.match_id = meta["match_id"]
        self.seed = meta["seed"]
        self.generator_version = meta["generator_version"]
        self.blocks: list[Block] = []
        self._pending: list[Entry] = []
        self._where: dict[str, tuple[int, int]] = {}  # entry id -> (block height, index)
        self.add("meta", "meta", meta)
        self.seal("genesis", at=at)

    def add(self, kind: str, natural: str, item: Any) -> Entry:
        text = canonical(item)
        entry = Entry(kind, entry_id(kind, natural), text, leaf_hash(text))
        self._pending.append(entry)
        return entry

    @property
    def head(self) -> str:
        return self.blocks[-1].hash

    @property
    def size(self) -> int:
        return sum(len(b.entries) for b in self.blocks) + len(self._pending)

    def seal(self, minute: str, *, at: datetime | None = None) -> dict[str, Any] | None:
        """Close the open block, if anything is in it: its header, its hash and its entries' ids."""
        if not self._pending:
            return None
        entries, self._pending = self._pending, []
        height = len(self.blocks)
        header = {
            "height": height,
            "minute": minute,
            "count": len(entries),
            "root": merkle_root([e.leaf for e in entries]),
            "prev": self.blocks[-1].hash if self.blocks else GENESIS_PREV,
            "at": (at or datetime.now(UTC)).isoformat(timespec="seconds"),
        }
        block = Block(header, header_hash(header), entries)
        self.blocks.append(block)
        for i, e in enumerate(entries):
            self._where[e.id] = (height, i)
        return {**header, "hash": block.hash, "ids": [e.id for e in entries]}

    def export(self) -> dict[str, Any]:
        """The whole ledger, sealed blocks only, as a file anyone can verify."""
        return {
            "ledger": VERSION,
            "match_id": self.match_id,
            "seed": self.seed,
            "generator_version": self.generator_version,
            "head": self.head,
            "blocks": [
                {
                    **b.header,
                    "hash": b.hash,
                    "entries": [{"kind": e.kind, "id": e.id, "text": e.text} for e in b.entries],
                }
                for b in self.blocks
            ],
        }

    def proof(self, item: str) -> dict[str, Any] | None:
        """One entry's proof: its text, its Merkle path in its block, the headers to the seal."""
        if item not in self._where:
            return None
        height, index = self._where[item]
        block = self.blocks[height]
        entry = block.entries[index]
        leaves = [e.leaf for e in block.entries]
        return {
            "id": entry.id,
            "kind": entry.kind,
            "text": entry.text,
            "leaf": entry.leaf,
            "index": index,
            "path": inclusion_path(leaves, index),
            "block": {**block.header, "hash": block.hash},
            "after": [{**b.header, "hash": b.hash} for b in self.blocks[height + 1 :]],
            "head": self.head,
        }


@dataclass
class Check:
    ok: bool
    blocks: int = 0
    entries: int = 0
    events_regenerated: int = 0
    problems: list[str] = field(default_factory=list)


def check_proof(proof: dict[str, Any]) -> bool:
    """An entry is in the ledger whose seal is `head`: its leaf, its root, and the chain on."""
    block = proof["block"]
    if leaf_hash(proof["text"]) != proof["leaf"]:
        return False
    if not verify_inclusion(
        proof["leaf"], proof["index"], block["count"], proof["path"], block["root"]
    ):
        return False
    previous = block
    for b in [block, *proof["after"]]:
        header = {k: b[k] for k in ("height", "minute", "count", "root", "prev", "at")}
        if header_hash(header) != b["hash"] or (b is not block and b["prev"] != previous["hash"]):
            return False
        previous = b
    return previous["hash"] == proof["head"]


def verify(exported: dict[str, Any], *, regenerate: bool = True) -> Check:
    """Recompute every hash in an exported ledger. With regenerate, also generate the synthetic
    match from its seed and require exactly its events, in order, as the ledger holds them."""
    check = Check(ok=True)
    prev = GENESIS_PREV
    events: list[tuple[str, str]] = []
    for b in exported["blocks"]:
        where = f"block {b['height']} ({b['minute']})"
        texts = [e["text"] for e in b["entries"]]
        if b["prev"] != prev:
            check.problems.append(f"{where}: it doesn't name the block before it")
        if b["count"] != len(texts) or merkle_root([leaf_hash(t) for t in texts]) != b["root"]:
            check.problems.append(f"{where}: its entries don't match its root")
        header = {k: b[k] for k in ("height", "minute", "count", "root", "prev", "at")}
        if header_hash(header) != b["hash"]:
            check.problems.append(f"{where}: its header doesn't match its hash")
        prev = b["hash"]
        check.blocks += 1
        check.entries += len(texts)
        events += [(e["id"], e["text"]) for e in b["entries"] if e["kind"] == "event"]
    if prev != exported["head"]:
        check.problems.append("the last block isn't the seal the ledger states")
    if regenerate:
        from match_events import generate

        match = generate(exported["seed"])
        if match.meta.generator_version != exported["generator_version"]:
            check.problems.append("this generator isn't the one that made the match")
        truth = [(e.id, canonical(e.model_dump(mode="json"))) for e in match.events]
        if events != truth[: len(events)]:
            first = next(
                (
                    i
                    for i, (got, want) in enumerate(zip(events, truth, strict=False))
                    if got != want
                ),
                min(len(events), len(truth)),
            )
            check.problems.append(f"event {first + 1} isn't the event the seed generates")
        check.events_regenerated = len(events)
    check.ok = not check.problems
    return check
