// The rooms' bar (apps/api/src/court/studio/nav.css, nav.js): each of the studio's three pages
// carries its own copy, so these tests keep the copies in step and each page lit as itself.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const STUDIO = path.join(__dirname, "..", "..", "apps", "api", "src", "court", "studio");
const PAGES = { "index.html": "/", "hud.html": "/hud", "ask.html": "/ask" };
const read = (file) => fs.readFileSync(path.join(STUDIO, file), "utf8");
const bar = (html) => html.match(/<nav class="topnav"[\s\S]*?<\/nav>/)?.[0];

test("every page carries the same bar, the room it is lit as aside", () => {
  const copies = Object.keys(PAGES).map((file) => bar(read(file)));
  copies.forEach((copy, i) => assert.ok(copy, `${Object.keys(PAGES)[i]} has no rooms' bar`));
  const plain = copies.map((copy) => copy.replace(' aria-current="page"', ""));
  assert.equal(plain[1], plain[0], "hud.html's bar differs from index.html's");
  assert.equal(plain[2], plain[0], "ask.html's bar differs from index.html's");
});

test("each page lights its own room, and only that one", () => {
  for (const [file, here] of Object.entries(PAGES)) {
    const rooms = bar(read(file)).match(/<ul class="topnav-rooms">[\s\S]*?<\/ul>/)[0];
    const lit = [...rooms.matchAll(/<a href="([^"]+)" aria-current="page">/g)].map((m) => m[1]);
    assert.deepEqual(lit, [here], file);
  }
});

test("every page loads the bar's style before its own, and its script, and draws the badge it uses", () => {
  for (const file of Object.keys(PAGES)) {
    const html = read(file);
    const nav = html.indexOf('href="/static/nav.css"');
    const own = html.indexOf(`href="/static/${{ "index.html": "studio", "hud.html": "hud", "ask.html": "ask" }[file]}.css"`);
    assert.ok(nav > 0 && own > nav, `${file}: nav.css must come before the page's own stylesheet`);
    assert.ok(html.includes('<script src="/static/nav.js"></script>'), `${file}: nav.js`);
    assert.ok(html.includes('<symbol id="badge"'), `${file}: the badge symbol`);
  }
});
