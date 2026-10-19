// HUD²'s pure parts (apps/api/src/court/studio/hud-core.js): the lenses, the viewer's own layer
// choices, the camera, and where a verified line is pinned.
const test = require("node:test");
const assert = require("node:assert/strict");
const HUD = require("../../apps/api/src/court/studio/hud-core.js");

test("every lens starts from known layers, and only shows the lines it is for", () => {
  for (const [name, lens] of Object.entries(HUD.LENSES)) {
    assert.ok(lens.layers.length, name);
    for (const layer of lens.layers) assert.ok(Object.hasOwn(HUD.LAYERS, layer), `${name}: ${layer}`);
  }
  assert.equal(HUD.shows("referee", "ref_call"), true);
  assert.equal(HUD.shows("referee", "great_pass"), false);
  assert.equal(HUD.shows("fan", "great_pass"), true);
  // Every kind of moment a line can be about has plain words for a newcomer.
  for (const kind of ["goal", "big_chance", "momentum_swing", "great_pass", "counter", "high_press", "ref_call"]) {
    assert.ok(HUD.EXPLAIN[kind], kind);
  }
});

test("a viewer's own choices sit on top of the lens, and unknown names are ignored", () => {
  assert.deepEqual(HUD.layersFor("referee"), HUD.layersFor("referee", {}));
  const mine = HUD.layersFor("referee", { heat: true, zones: false, nonsense: true });
  assert.ok(mine.includes("heat"));
  assert.ok(!mine.includes("zones"));
  assert.ok(!mine.includes("nonsense"));
  assert.equal(HUD.lensOf("coach"), "fan");
});

for (const view of ["top", "stand"]) {
  test(`the ${view} camera keeps the whole pitch on screen, the centre spot in the middle`, () => {
    const cam = HUD.camera(view, 1600, 900);
    for (const [x, y] of [[0, 0], [105, 0], [0, 68], [105, 68]]) {
      const [sx, sy] = cam.project(x, y);
      assert.ok(sx >= 0 && sx <= 1600 && sy >= 0 && sy <= 900, `${x},${y} -> ${sx},${sy}`);
    }
    const [cx] = cam.project(52.5, 34);
    assert.ok(Math.abs(cx - 800) < 1);
  });
}

test("from the stand, the far touchline is narrower and higher than the near one", () => {
  const cam = HUD.camera("stand", 1600, 900);
  const width = (y) => cam.project(105, y)[0] - cam.project(0, y)[0];
  assert.ok(width(0) < width(68));
  assert.ok(cam.project(52.5, 0)[1] < cam.project(52.5, 68)[1]);
  assert.ok(cam.project(52.5, 0)[2] < cam.project(52.5, 68)[2], "fewer pixels per metre far away");
  // The top view keeps the pitch's proportions.
  const top = HUD.camera("top", 1600, 900);
  const [x0, y0] = top.project(0, 0);
  const [x1, y1] = top.project(105, 68);
  assert.ok(Math.abs((x1 - x0) / (y1 - y0) - 105 / 68) < 1e-9);
});

test("a line is pinned at the last cited action the HUD has placed", () => {
  const placed = new Map([
    ["e00010", { kind: "pass", x: 40, y: 30, ex: 70, ey: 20 }],
    ["e00012", { kind: "shot", x: 92, y: 33 }],
  ]);
  assert.deepEqual(HUD.anchorOf(["e00010", "e00012", "e99999"], placed), [92, 33]);
  assert.deepEqual(HUD.anchorOf(["e00010"], placed), [70, 20], "a pass is pinned where it went");
  assert.equal(HUD.anchorOf(["e99999"], placed), null);
  assert.equal(HUD.anchorOf(undefined, placed), null);
});

test("what was drawn fades out over its life", () => {
  assert.equal(HUD.fade(0, 5), 1);
  assert.equal(HUD.fade(5, 5), 0);
  assert.ok(HUD.fade(1, 5) > HUD.fade(3, 5));
});
