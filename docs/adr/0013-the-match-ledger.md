# ADR 0013: The match ledger, a match's history chained by hashes

- **Status:** accepted, 2026-10-20
- **Context:** the Monarch asked for blockchain-inspired principles that keep the match history's
  integrity, highlighted on the showcase site. The Critic proves each line against the events, and
  the audit trail (ADR 0004) keeps every output in Cosmos DB. Neither shows that the record itself
  hasn't changed since: a row in a database can be edited, and nobody outside could tell.

## Decision

- **A ledger per match, in the studio session** (`court/ledger.py`), holding every entry in the
  order it happened: the match's meta (the genesis block), every event, every line that aired,
  every claim the Critic refused or spiked, every change of service, every answer to a viewer's
  question, and the recap's SHA-256. Outputs go in as the court made them, before any viewer's
  personal view.
- **Blockchain's integrity, without a blockchain.** No coin, no mining, no network: what is kept
  is the structure that makes a chain trustworthy.
  - An entry is its JSON in one canonical form (keys sorted, no spaces, UTF-8 as written); its
    leaf hash is SHA-256 over 0x00 and that text.
  - Each match minute is a block. Its entries are sealed by their Merkle root, built as Certificate
    Transparency builds its logs (RFC 6962), and its header (height, minute, count, root, the
    previous block's hash, when it was sealed) is hashed in turn.
  - The last block's hash is the match's seal. It goes into the match summary, so the audit trail
    in Cosmos DB and the trace in Application Insights (`hudhud.ledger_seal`) each keep a copy apart
    from the ledger.
  - After full time each answer seals a block of its own, and the chain goes on from the seal.
- **Anyone can check it, without trusting the studio.**
  - The page sees each block's header live (an SSE `block` event) and can download the whole
    ledger (`/api/sessions/{id}/ledger`). The browser recomputes every hash itself
    (`studio/ledger-core.js`, Web Crypto) and checks the seal against the one sealed live.
  - One entry's proof (`/api/sessions/{id}/ledger/proof?item=`) is its Merkle path and the headers
    to the seal (RFC 9162's verification), a few hundred bytes.
  - `python -m court verify ledger.json` recomputes everything offline and generates the synthetic
    match again from its seed: the ledger must hold exactly those events.
- **The tamper test is part of the product.** At full time the studio offers "Try changing one
  line": the browser changes one number in one line of a copy and verifies it, and the broken
  block turns red.

## Consequences

- Python and the browser hash the same bytes: a sample ledger written by Python
  (`tests/studio/fixtures/ledger-sample.json`) is verified by both test suites in CI.
- About 1,830 entries and 100 blocks a match; the file is about 700 KB. Hashing costs well under a
  second of CPU over a whole match.
- What it proves: the history hasn't changed since it was sealed, and the events are the seed's.
  What it doesn't: it says nothing a line didn't already prove, and a studio that lied while
  recording would seal its lie. The copies of the seal in Cosmos DB and Application Insights, and
  the events regenerated from the seed, make that harder, not impossible. Publishing seals to a
  public log is the next step, after the hackathon.
