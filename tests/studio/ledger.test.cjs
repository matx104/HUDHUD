// The match ledger checked the browser's way (apps/api/src/court/studio/ledger-core.js), against a
// ledger Python wrote (tests/studio/fixtures/ledger-sample.json): the two must agree on every byte.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Ledger = require("../../apps/api/src/court/studio/ledger-core.js");

const sample = () => JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "ledger-sample.json"), "utf8"));

test("RFC 6962's empty leaf, as Certificate Transparency hashes it", async () => {
  assert.equal(await Ledger.leafHash(""), "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d");
});

test("the ledger Python wrote verifies here, block by block", async () => {
  const seen = [];
  const check = await Ledger.verifyLedger(sample(), (b, ok) => seen.push([b.height, ok]));
  assert.deepEqual(check.problems, []);
  assert.equal(check.ok, true);
  assert.equal(check.blocks, 4);
  assert.deepEqual(seen.map(([, ok]) => ok), [true, true, true, true]);
});

test("one changed word in one line breaks its block, and hiding it breaks the next link", async () => {
  const forged = sample();
  const entry = forged.blocks[2].entries.find((e) => e.id === "cue:c1");
  entry.text = entry.text.replace("0.42", "0.92");
  let check = await Ledger.verifyLedger(forged);
  assert.equal(check.ok, false);
  assert.equal(check.brokenAt, 2);
  assert.match(check.problems[0], /entries don't match its root/);
  // A forger who recomputes the root must change the header, so its hash, so the next block's link.
  forged.blocks[2].root = await Ledger.merkleRoot(await Promise.all(forged.blocks[2].entries.map((e) => Ledger.leafHash(e.text))));
  forged.blocks[2].hash = await Ledger.headerHash(forged.blocks[2]);
  check = await Ledger.verifyLedger(forged);
  assert.equal(check.ok, false);
  assert.match(check.problems.join("\n"), /block 3 .*doesn't name the block before it/);
});

test("one line's proof, Python's, checks here: leaf, Merkle path, then the chain to the seal", async () => {
  const proof = JSON.parse(fs.readFileSync(path.join(__dirname, "fixtures", "ledger-proof.json"), "utf8"));
  assert.equal(await Ledger.verifyProof(proof), null);
  assert.match(await Ledger.verifyProof({ ...proof, text: proof.text.replace("0.42", "0.52") }), /isn't its leaf/);
  const moved = structuredClone(proof);
  moved.after[0].prev = "0".repeat(64);
  assert.match(await Ledger.verifyProof(moved), /header isn't its hash|doesn't name/);
});
