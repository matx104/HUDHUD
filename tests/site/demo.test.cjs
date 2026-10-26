// The site's demos replay a recorded match through the studio's own pages (site/demo/, written by
// scripts/site_demo.py). The copies must stay the studio's: the same files, and the pages changed
// only where they name the studio's paths. Run the script again when the studio changes.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.join(__dirname, "..", "..");
const STUDIO = path.join(ROOT, "apps", "api", "src", "court", "studio");
const DEMO = path.join(ROOT, "site", "demo");
const read = (dir, file) => fs.readFileSync(path.join(dir, file), "utf8");

// The same change scripts/site_demo.py makes to a studio page.
function page(html) {
  html = html.replaceAll('src="/static/', 'src="').replaceAll('href="/static/', 'href="');
  for (const [from, to] of [['href="/"', "studio.html"], ['href="/hud"', "hud.html"], ['href="/ask"', "ask.html"]]) {
    html = html.replaceAll(from, `href="${to}"`);
  }
  const first = html.indexOf("  <script src=");
  return `${html.slice(0, first)}  <script src="replay.js"></script>\n${html.slice(first)}`;
}

test("the demo pages are the studio's, with only its paths changed", () => {
  for (const [source, target] of [["index.html", "studio.html"], ["hud.html", "hud.html"], ["ask.html", "ask.html"]]) {
    assert.equal(read(DEMO, target), page(read(STUDIO, source)), `${target}: run scripts/site_demo.py --copy-only`);
  }
});

test("the demo's scripts and styles are the studio's, byte for byte", () => {
  for (const file of ["studio.css", "studio.js", "hud.css", "hud.js", "hud-core.js", "ask.css", "ask.js", "ledger-core.js", "voice.js", "nav.css", "nav.js"]) {
    assert.equal(read(DEMO, file), read(STUDIO, file), `${file}: run scripts/site_demo.py --copy-only`);
  }
});

test("the recording holds a whole match, its answers and their proofs", () => {
  const recording = JSON.parse(read(DEMO, "recording.json"));
  const kinds = new Set(recording.events.map(([, kind]) => kind));
  for (const kind of ["hello", "clock", "play", "pulse", "output", "block", "end"]) assert.ok(kinds.has(kind), kind);
  assert.equal(recording.config.voice, false, "the site has no voice");
  assert.ok(recording.answers.length >= 8);
  for (const answer of recording.answers) assert.equal(answer.proof.id, `answer:${answer.id}`);
  const ledger = JSON.parse(read(DEMO, "ledger.json"));
  assert.ok(recording.answers.every((a) => a.proof.head === ledger.head), "every proof ends at the ledger's seal");
});
