const test = require("node:test");
const assert = require("node:assert/strict");
const { resolveRoute } = require("../../site/assets/router.js");

const PAGES = ["how", "recovery", "data", "name"];

test("no hash, a bare # and #/ are all the home page", () => {
  for (const hash of ["", "#", "#/"]) assert.deepEqual(resolveRoute(hash, PAGES), { page: "", redirect: null });
});

test("a canonical route resolves to its page with no redirect", () => {
  assert.deepEqual(resolveRoute("#/how", PAGES), { page: "how", redirect: null });
});

test("old in-page anchors, odd casing and trailing slashes redirect to the canonical route", () => {
  assert.deepEqual(resolveRoute("#how", PAGES), { page: "how", redirect: "#/how" });
  assert.deepEqual(resolveRoute("#/Name", PAGES), { page: "name", redirect: "#/name" });
  assert.deepEqual(resolveRoute("#/data/", PAGES), { page: "data", redirect: "#/data" });
});

test("an unknown path resolves to no page and keeps what was asked for", () => {
  assert.deepEqual(resolveRoute("#/Fixtures", PAGES), { page: null, redirect: null, path: "Fixtures" });
});
