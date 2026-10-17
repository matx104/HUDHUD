// Hash routes for the one-file site: "#/how" shows the section whose data-page is "how".
// Pure on purpose, so tests/site/router.test.cjs can run it under node --test.
(function (root) {
  function resolveRoute(hash, pages) {
    const raw = String(hash ?? "").replace(/^#\/?/, "").replace(/\/+$/, "");
    const path = raw.toLowerCase();
    if (path === "") return { page: "", redirect: null };
    if (!pages.includes(path)) return { page: null, redirect: null, path: raw };
    // Old in-page anchors (#how) and odd casing (#/How) settle on the one canonical form.
    const canonical = `#/${path}`;
    return { page: path, redirect: hash === canonical ? null : canonical };
  }

  if (typeof module === "object" && module.exports) module.exports = { resolveRoute };
  else root.resolveRoute = resolveRoute;
})(globalThis);
