// HUD²'s pure parts: the lenses and their layers, the camera that puts a pitch point on the
// screen, and where a verified line is pinned. No DOM here, so tests/studio/hud.test.cjs can run
// it under node --test; hud.js draws with it.
(function (root) {
  const PITCH = { length: 105, width: 68 };

  // Every layer the HUD can draw. A lens is a starting set of these; each viewer can switch any of
  // them on or off, and the HUD remembers their choice per lens.
  const LAYERS = {
    ball: "The ball, locked on",
    trail: "The ball's path",
    passes: "Recent passes",
    shots: "Shots, sized by chance quality",
    names: "Who's on the ball",
    heat: "Where each side has played lately",
    pressure: "Pressing",
    fouls: "Fouls and tackles",
    zones: "The referee's zones",
    lines: "Checked lines, pinned where they happened",
    refusals: "The Critic's refusals, where they were aimed",
    explain: "Plain words for newcomers",
  };

  // Who each lens is for, and what it starts with.
  const LENSES = {
    referee: {
      name: "Referee",
      blurb: "Fouls, where they happened, and the zones a likely call is read against.",
      layers: ["ball", "names", "pressure", "fouls", "zones", "lines", "refusals"],
      kinds: ["ref_call", "goal"],
      mode: "analyst",
    },
    commentator: {
      name: "Commentator",
      blurb: "Who's on the ball, the last five minutes in numbers, and every checked line.",
      layers: ["ball", "trail", "passes", "shots", "names", "lines", "refusals"],
      kinds: null, // every kind of line
      mode: "analyst",
    },
    fan: {
      name: "Fan",
      blurb: "The match explained in plain words, your club lit up, and your questions answered.",
      layers: ["ball", "trail", "shots", "heat", "lines", "explain"],
      kinds: null,
      mode: "casual",
    },
  };

  // Plain words for a newcomer, by the kind of moment a line is about (the HUD titles each with
  // the kind's name). The product's own fixed words, the same every match: no model writes them.
  const EXPLAIN = {
    goal: "The whole ball crossed the goal line, between the posts and under the bar.",
    big_chance: "A shot that often goes in. xG, expected goals, says how often a shot from that spot, taken that way, scores: near 1 almost always, near 0 almost never.",
    momentum_swing: "For a few minutes one side has had more of the ball in the other half, and made more of it.",
    great_pass: "A pass few players would complete, judged by how hard it was before it was played.",
    counter: "The ball won back in a side's own half, and a shot within seconds, before the other side could get back.",
    high_press: "Winning the ball back close to the other side's goal, again and again.",
    ref_call: "What the Laws of the Game likely give for that foul. Event data sees where a foul happened, not how hard it was, so it always says likely.",
  };

  function lensOf(name) {
    return Object.hasOwn(LENSES, name) ? name : "fan";
  }

  // A lens's layers, with the viewer's own choices on top: saved is { layer: true | false }.
  function layersFor(lens, saved = {}) {
    const on = new Set(LENSES[lensOf(lens)].layers);
    for (const [layer, wanted] of Object.entries(saved ?? {})) {
      if (!Object.hasOwn(LAYERS, layer)) continue;
      if (wanted) on.add(layer);
      else on.delete(layer);
    }
    return Object.keys(LAYERS).filter((layer) => on.has(layer));
  }

  // Whether a lens shows a line about this kind of moment.
  function shows(lens, kind) {
    const kinds = LENSES[lensOf(lens)].kinds;
    return kinds === null || kinds.includes(kind);
  }

  // The camera. "top" looks straight down, like a tactics board. "stand" looks from above and
  // behind the near touchline (y = 68), the way a seat in the stand or a pair of glasses would
  // see it: the far touchline narrower, the near one wider. project(x, y) gives the screen point
  // and the pixels per metre there, so rings shrink with distance.
  function camera(view, w, h, pad = 0.05) {
    if (view === "top") {
      const s = Math.min((w * (1 - 2 * pad)) / PITCH.length, (h * (1 - 2 * pad)) / PITCH.width);
      const ox = (w - PITCH.length * s) / 2;
      const oy = (h - PITCH.width * s) / 2;
      return { view, project: (x, y) => [ox + x * s, oy + y * s, s] };
    }
    const height = 55; // metres above the pitch: high in the stand, the pitch tall enough to read
    const back = 8; // metres behind the near touchline
    const tilt = Math.atan2(height, back + PITCH.width / 2); // the centre spot in the middle
    const sin = Math.sin(tilt);
    const cos = Math.cos(tilt);
    const raw = (x, y) => {
      const depth = back + (PITCH.width - y);
      const forward = height * sin + depth * cos;
      const up = depth * sin - height * cos;
      return [(x - PITCH.length / 2) / forward, -up / forward, 1 / forward];
    };
    const corners = [[0, 0], [PITCH.length, 0], [0, PITCH.width], [PITCH.length, PITCH.width]].map(([x, y]) => raw(x, y));
    const xs = corners.map((c) => c[0]);
    const ys = corners.map((c) => c[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const f = Math.min((w * (1 - 2 * pad)) / (x1 - x0), (h * (1 - 2 * pad)) / (y1 - y0));
    const cx = w / 2 - (f * (x0 + x1)) / 2;
    const cy = h / 2 - (f * (y0 + y1)) / 2;
    return {
      view: "stand",
      project: (x, y) => {
        const [a, b, c] = raw(x, y);
        return [cx + f * a, cy + f * b, f * c];
      },
    };
  }

  // Where the ball is after an action: a pass ends where it was played to.
  function ballAt(play) {
    return play.kind === "pass" ? [play.ex, play.ey] : [play.x, play.y];
  }

  // Where a line is pinned: the last event it cites that the HUD has placed. A line about a run of
  // play is pinned where that run ended.
  function anchorOf(evidence, placed) {
    for (let i = (evidence?.length ?? 0) - 1; i >= 0; i--) {
      const play = placed.get(evidence[i]);
      if (play) return ballAt(play);
    }
    return null;
  }

  // How visible something drawn `age` seconds ago still is, over a `life` of seconds.
  function fade(age, life) {
    if (age <= 0) return 1;
    if (age >= life) return 0;
    const left = 1 - age / life;
    return left * left;
  }

  const api = { PITCH, LAYERS, LENSES, EXPLAIN, lensOf, layersFor, shows, camera, ballAt, anchorOf, fade };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.HUD = api;
})(globalThis);
