// The match ledger, checked in the browser (court/ledger.py, ADR 0013): every entry's leaf hash,
// every block's Merkle root (RFC 6962) and header hash, and every link to the block before, all
// recomputed here with the browser's own SHA-256. Nothing is taken from the server on trust. Pure,
// so tests/studio/ledger.test.cjs runs it under node against a ledger Python wrote.
(function (root) {
  const subtle = root.crypto?.subtle ?? require("node:crypto").webcrypto.subtle;
  const encoder = new TextEncoder();
  const GENESIS_PREV = "0".repeat(64);

  const hex = (buffer) => [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
  const bytes = (h) => Uint8Array.from(h.match(/../g), (pair) => parseInt(pair, 16));

  async function sha256(...parts) {
    const all = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
    let at = 0;
    for (const part of parts) { all.set(part, at); at += part.length; }
    return hex(await subtle.digest("SHA-256", all));
  }

  const leafHash = (text) => sha256(Uint8Array.of(0), encoder.encode(text));
  const nodeHash = (left, right) => sha256(Uint8Array.of(1), bytes(left), bytes(right));

  function split(n) {
    let k = 1;
    while (k * 2 < n) k *= 2;
    return k;
  }

  async function merkleRoot(leaves) {
    if (leaves.length === 0) return sha256(new Uint8Array());
    if (leaves.length === 1) return leaves[0];
    const k = split(leaves.length);
    return nodeHash(await merkleRoot(leaves.slice(0, k)), await merkleRoot(leaves.slice(k)));
  }

  // A block's header in the one text Python hashes: keys sorted, no spaces.
  function headerText(b) {
    return JSON.stringify({ at: b.at, count: b.count, height: b.height, minute: b.minute, prev: b.prev, root: b.root });
  }
  const headerHash = (b) => sha256(encoder.encode(headerText(b)));

  // Check a whole ledger. onBlock(block, ok) is told as each block is checked, for a page to show.
  async function verifyLedger(ledger, onBlock = () => {}) {
    const problems = [];
    let prev = GENESIS_PREV;
    let entries = 0;
    let brokenAt = null;
    for (const b of ledger.blocks) {
      const where = `block ${b.height} (${b.minute})`;
      const before = problems.length;
      if (b.prev !== prev) problems.push(`${where}: it doesn't name the block before it`);
      const leaves = await Promise.all(b.entries.map((e) => leafHash(e.text)));
      if (b.count !== leaves.length || (await merkleRoot(leaves)) !== b.root) problems.push(`${where}: its entries don't match its root`);
      if ((await headerHash(b)) !== b.hash) problems.push(`${where}: its header doesn't match its hash`);
      const ok = problems.length === before;
      if (!ok && brokenAt === null) brokenAt = b.height;
      onBlock(b, ok);
      prev = b.hash;
      entries += leaves.length;
    }
    if (prev !== ledger.head) problems.push("the last block isn't the seal the ledger states");
    return { ok: problems.length === 0, blocks: ledger.blocks.length, entries, problems, brokenAt };
  }

  // One entry's proof (RFC 9162 §2.1.3.2): its leaf, its Merkle path to its block's root, then each
  // block's header hash and link, on to the seal. Returns which step failed, or null.
  async function verifyProof(proof) {
    if ((await leafHash(proof.text)) !== proof.leaf) return "the entry's text isn't its leaf";
    const block = proof.block;
    let fn = proof.index;
    let sn = block.count - 1;
    let r = proof.leaf;
    if (fn > sn) return "the entry isn't in its block";
    for (const p of proof.path) {
      if (sn === 0) return "the Merkle path is too long";
      if (fn & 1 || fn === sn) {
        r = await nodeHash(p, r);
        if (!(fn & 1)) while (!(fn & 1) && fn !== 0) { fn >>= 1; sn >>= 1; }
      } else {
        r = await nodeHash(r, p);
      }
      fn >>= 1; sn >>= 1;
    }
    if (sn !== 0 || r !== block.root) return "the Merkle path doesn't reach its block's root";
    let previous = null;
    for (const b of [block, ...proof.after]) {
      if ((await headerHash(b)) !== b.hash) return `block ${b.height}'s header isn't its hash`;
      if (previous && b.prev !== previous.hash) return `block ${b.height} doesn't name the block before it`;
      previous = b;
    }
    return previous.hash === proof.head ? null : "the chain doesn't end at the seal";
  }

  const api = { GENESIS_PREV, leafHash, nodeHash, merkleRoot, headerText, headerHash, verifyLedger, verifyProof };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.Ledger = api;
})(globalThis);
