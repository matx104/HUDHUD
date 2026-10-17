// The site's <head> repeats the name and address for crawlers that don't run JavaScript.
// These tests keep that copy, the sitemap and the routes in step with config.js.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SITE = path.join(__dirname, "..", "..", "site");
const read = (file) => fs.readFileSync(path.join(SITE, file), "utf8");
const html = read("index.html");
const sandbox = { window: {} };
vm.runInNewContext(read("config.js"), sandbox);
const config = sandbox.window.SITE;

const meta = (key) => html.match(new RegExp(`<meta (?:property|name)="${key}" content="([^"]*)"`))?.[1];
const ldJson = () => JSON.parse(html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/)[1]);

test("the name crawlers see is the name in config.js", () => {
  const name = config.productName;
  assert.match(html.match(/<title>([^<]*)<\/title>/)[1], new RegExp(`^${name}\\b`));
  assert.equal(meta("og:site_name"), name);
  assert.ok(meta("og:title").startsWith(name));
  for (const node of ldJson()["@graph"].filter((n) => n["@type"] !== "Person")) assert.equal(node.name, name);
  assert.equal(JSON.parse(read("site.webmanifest")).name, name);
});

test("canonical, og:url, structured data, sitemap and robots share one address", () => {
  const url = config.siteUrl;
  assert.equal(html.match(/<link rel="canonical" href="([^"]*)"/)[1], url);
  assert.equal(meta("og:url"), url);
  assert.ok(meta("og:image").startsWith(url));
  assert.equal(ldJson()["@graph"].find((n) => n["@type"] === "WebSite").url, url);
  assert.match(read("sitemap.xml"), new RegExp(`<loc>${url}</loc>`));
  assert.match(read("robots.txt"), new RegExp(`Sitemap: ${url}sitemap.xml`));
});

test("every route link has a page to show, and every page has a title", () => {
  const pages = [...html.matchAll(/<section[^>]*data-page="([^"]*)"[^>]*>/g)];
  const keys = pages.map((m) => m[1]);
  for (const [tag] of pages) assert.match(tag, /data-title="[^"]+"/, tag);
  for (const [, href] of html.matchAll(/href="#\/([^"]*)"/g)) assert.ok(keys.includes(href), `#/${href} has no page`);
  assert.ok(keys.includes("") && keys.includes("missing"));
});

test("every asset the head points at exists", () => {
  for (const [, ref] of html.matchAll(/(?:href|src)="((?:assets|data)\/[^"]+|config\.js|site\.webmanifest)"/g)) {
    assert.ok(fs.existsSync(path.join(SITE, ref)), ref);
  }
  for (const icon of JSON.parse(read("site.webmanifest")).icons) assert.ok(fs.existsSync(path.join(SITE, icon.src)), icon.src);
});
