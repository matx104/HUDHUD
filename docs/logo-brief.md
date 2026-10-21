# The logo brief — mark v2, handoff to a designing agent

> Status: the concept below is **chosen and shipped** (commit `b6a615a`, 2026-10-21), but the owner
> judges the executed artwork below the quality bar. This file carries the idea, logic and
> reasoning so a fresh agent can re-execute the same concept at higher craft. The concept stands;
> the drawing is what gets replaced.

## 1. What the mark must say

HUDHUD is AI football commentary that proves every claim before it airs. Five agents work a live
synthetic match: the **Scout** detects what matters (hot path, sub-millisecond, no model), the
**Narrator** writes the line, the **Critic** recomputes every number from the raw events and
refuses what it can't prove, the **Localizer** airs it in English, Urdu and Arabic, and the
**Orchestrator** keeps the broadcast on air when a model fails. The name is the hoopoe: the
messenger whose news was checked before anyone acted on it (Surah An-Naml 27:20–28). Full story:
`brand.md`.

The original crest (five feathers, the Critic's gold at centre) carried the name but not the
product: nothing in it said *football* or *analysis*. The owner's brief, verbatim in intent:

1. **Keep the hoopoe tail feathers exactly as they are** — build on top, remove nothing.
2. The same crest, **printed on top of a football**.
3. An **analysis scope** on the centre — the root of the tail, where the feathers converge.
4. Each feather is dedicated to an agent: **icons denoting those agents** — or is that too much?

## 2. The concept and its reasoning

- **The crest on the ball.** The feathers spring from the ball's centre the way they spring from
  the hoopoe's head: the ball *is* the bird's head. One shape carries bird + match. The root of
  the tail sits at the ball's centre, so the fan reads as a signal broadcast out of the match
  itself.
- **The scope on the root.** A targeting/analysis reticle — dashed lock-ring, two ticks — centred
  on the convergence point of all five feathers. That point is where every agent's output meets
  and every claim is checked: the court. A small **gold lens** (the Critic's colour) caps the
  convergence, drawn last, on top.
- **One feather per agent** — already true before v2 (Scout · Narrator · Critic · Localizer ·
  Orchestrator; Critic gold, centre).
- **The icons question, resolved by looking at real renderings**: icons *inside* feathers dissolve
  into noise below ~96px, and the logo lives mostly at 24–56px (favicon, header, footers, slates).
  Decision, approved by the owner:
  - **Variant A** (no per-feather icons) is *the mark* everywhere it appears small.
  - **Variant B** (one glyph per feather) appears **only** in the large name-page figure, where
    the agent labels already live — the icons become a detail you discover, not clutter you
    decode. Glyph map: Scout = eye, Narrator = pen, Critic = check, Localizer = globe,
    Orchestrator = hub-and-spokes (five spokes echo the fan).

## 3. Palette, surfaces, behaviour — the non-negotiables

- Palette (from `brand.md`): deep navy `#0A1F2E` (surface), off-white `#F4F1E8` (chalk), electric
  lime `#B8F53D` (the agents, the signal), evidence gold `#C9A227` (the Critic, verdicts), pitch
  green `#1E7B45` (rarely). The mark lives on dark; chalk strokes must survive both dark and the
  navy tile.
- **The five feather paths must not change.** They are the existing brand asset, referenced by
  `id` across every page (local coords, root at origin, tip at negative y):
  - `f78`: `M0 0C5.2-23.4 13-46.8 10.4-66.3Q0-81.9-10.4-66.3C-13-46.8-5.2-23.4 0 0Z`
  - `f96`: `M0 0C5.2-28.8 13-57.6 10.4-81.6Q0-100.8-10.4-81.6C-13-57.6-5.2-28.8 0 0Z`
  - `f112`: `M0 0C5.6-33.6 14-67.2 11.2-95.2Q0-117.6-11.2-95.2C-14-67.2-5.6-33.6 0 0Z`
  Fan order: `f78 @ -52°`, `f96 @ -26°`, `f112 @ 0°` (gold), `f96 @ +26°`, `f78 @ +52°`.
- The feathers **fan open** on page entry (CSS animation on `.feather` groups with `--r` / `--i`
  custom properties; keyframes `fan` / `fan-again`). Any new drawing must keep per-feather groups
  addressable so the animation survives.
- Variant A small / Variant B large rule is an owner decision; changing it means asking the owner.
- No Premier League / Microsoft / club marks or implied real-match data (competition rules,
  `brand.md` §Video/music compliance).

## 4. The shipped geometry (reference, to be bettered)

Current art lives in a `0 0 240 240` viewBox, root of the tail / ball centre at `(120, 134)`:

- Ball: circle r = 60, fill `#0E2940`, chalk outline 1.8. Seams: five hand-plotted pentagon
  outlines + connecting quadratics, clipped to the ball — a "telstar hint", not a true
  icosahedron projection.
- Scope: dashed chalk ring r = 78 (`stroke-dasharray 9 8`, opacity 0.85), E/W ticks from x = 32
  to 40 and 200 to 208 at y = 134.
- Lens: r = 11 disc, navy fill, gold 2.5 stroke, gold centre dot r = 2.6.
- Variant B glyphs sit inside each feather's wide zone at local `(0, -56)` (f78), `(0, -70)`
  (f96), `(0, -82)` (f112), navy strokes so overflow off the feather is invisible.

## 5. Honest critique of the shipped execution

For the re-drawing agent — where the current artwork falls short:

- **The seams are guessed, not projected.** A real truncated-icosahedron seen from the root pole,
  properly projected and simplified to 2–3 stroke weights, would read "football" instantly. The
  current pentagons read as texture at ≤48px.
- **Optical balance was never eyeballed** (the executing agent could not view images). Ring vs
  ball vs feather densities compete; the dashed ring may be too busy against the seams. Try:
  fewer dashes, a partial sweep arc, or a solid thin ring; possibly drop the ring entirely at
  small sizes (a scale-dependent simplification is legitimate — ship two detail levels of the
  same mark).
- **The lens cap is crude** — a disc with a dot. A proper lens/reticle centre (fine crosshair,
  aperture ring, or the HUD² monogram) would earn its place.
- **Glyph legibility** in Variant B is borderline even at the large size; consider simplifying to
  single-stroke glyphs or replacing glyphs with the agents' initial letterforms in the display
  type.
- The whole composition has not been tuned at favicon scale (16–32px) — the true test.

## 6. Where the mark renders (the surface inventory)

Small (Variant A):

- `site/assets/crest.svg` — the favicon (navy tile, rx 28) and the footer "sting" `<img>`
- `site/index.html` — header `.brand-crest` (2.75rem), hero `.lockup-crest`
  (clamp 4.5–7.25rem), footer `.foot-crest` (3.5rem); each is inline SVG referencing the
  sprite's feather defs (`#f78/#f96/#f112`, `#ballClip`)
- `apps/api/src/court/studio/{index,hud,ask}.html` — the `<symbol id="crest">` (header brand) and
  the two opening slates (`.slate-crest`, studio.css clamp 9–16.5rem; hud.css clamp 7–11rem);
  head favicons are URL-encoded data URIs
- `site/demo/` — **generated copies**: after editing the studio source, run
  `.venv/bin/python scripts/site_demo.py --copy-only` (a drift test fails if the copies diverge)
- `site/assets/icon-{192,512}.png`, `apple-touch-icon.png` (180) — full-bleed navy tiles,
  maskable-safe (mark inside the inner ~80%); currently rendered by screenshotting the SVG at
  exact size with headless Chromium
- `kit/social-card.html` → `site/assets/og.png` (1200×630) via
  `.venv/bin/python scripts/social_card.py`
- `kit/thumbnail.html` → video thumbnail (1280×720), `kit/brand-sheet.html` → brand sheet PDF,
  both via `.venv/bin/python scripts/drive_kit.py` (builds `dist/kit`, syncs to Google Drive,
  prints the public folder link)

Large (Variant B):

- `site/index.html`, the name-page `figure.crest` — viewBox `-30 0 300 264`, root at `(120, 150)`,
  agent labels around (`Scout`, `Narrator`, `Critic` in gold, `Localizer`, `Orchestrator`), the
  HUD² wordmark below (`data-product-mark`), figcaption telling the reading

Untouched by v2 and still the bare crest (deliberate): the chapter `#head-emblem` (crest in a
pitch centre-circle) and the north-star `.star-crest` in `site/index.html`.

## 7. Definition of done for the re-draw

1. Same concept, same palette, same feather paths, same A/B placement rule.
2. Reads as "football + analysis + the hoopoe crest" at 32px, not just at 260px.
3. Fan animation still works on every animated surface (`.feather` groups with `--r`/`--i`).
4. Every surface in §6 updated, demo copies regenerated, PNGs and og re-rendered, Drive kit
   re-synced.
5. `make test` green (247 pytest + 26 node, incl. the demo drift tests).
6. The owner signs off on rendered previews at 260 / 96 / 48 / 24 px before anything ships.
