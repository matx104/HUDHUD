// HUD²: one match on one heads-up screen, through the referee's, the commentator's or the fan's
// lens (ADR 0012). The stream is the studio's, with hud=1: hello, clock, play (every action,
// placed on the pitch as the camera sees it), pulse (both sides' counts each minute), output (the
// court's cues and refusals), block (the match ledger's, ADR 0013), recap and end. The canvas draws where things happened; every word on
// screen came through the Critic, and every number from the server. Pure parts: hud-core.js.
(() => {
  const H = window.HUD;
  const $ = (sel) => document.querySelector(sel);
  const el = (tag, cls, text) => Object.assign(document.createElement(tag), { className: cls ?? "", textContent: text ?? "" });
  const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
  const now = () => performance.now() / 1000;
  const still = matchMedia("(prefers-reduced-motion: reduce)");

  // The Critic's reason codes, in words a viewer understands (as in the studio).
  const REASONS = {
    no_evidence: "Cites no events at all",
    unknown_event: "Cites an event that doesn't exist",
    future_event: "Cites an event that hadn't happened yet",
    stale_event: "Cites events too old to support it",
    assertion_mismatch: "A number in it doesn't match the events",
    insufficient_evidence: "Not enough evidence for the claim",
    ungrounded_number: "States a number nothing in the evidence supports",
    ungrounded_name: "Names a player its evidence isn't about",
    no_rule: "No rule yet for checking this kind of claim",
  };
  const KIND = { goal: "Goal", big_chance: "Big chance", momentum_swing: "Momentum", great_pass: "Great pass", counter: "Counter-attack", high_press: "High press", ref_call: "The ref's call" };
  const LENS_COLOR = { referee: "#C9A227", commentator: "#B8F53D", fan: "#F4F1E8" };
  const COLORS = { chalk: "244, 241, 232", lime: "184, 245, 61", gold: "201, 162, 39", card: "242, 92, 84" };
  const LIFE = { pin: 9, refused: 6, answer: 14, lock: 8, pass: 6, pressure: 5, foul: 12, shot: 4 };
  const MAX_PINS = 3;

  // A viewer's own settings live in this browser only: wrapped, because storage can be blocked.
  const store = {
    get(key, fallback) {
      try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* the choice lasts this visit */ }
    },
  };

  const S = {
    lens: "fan", view: store.get("hud2.view", "stand"), layers: [], saved: {}, fixed: null,
    matches: [], source: null, session: null, askSession: null, teams: null, zones: null,
    homeFirst: true, strictness: "standard", prefs: {}, live: false,
    plays: [], placed: new Map(), ball: null, ballTeam: null, onBall: null, lastFoul: null, nowT: 0, period: 1,
    pins: [], locks: [], bursts: [], pulse: null, cards: [], explain: null,
    tally: { aired: 0, refused: 0, checked: 0 }, heatDirty: true, heatAt: 0,
  };

  const form = $("[data-setup]");
  const box = $("[data-field-box]");
  const canvas = $("[data-field]");
  const ctx = canvas.getContext("2d");
  const pinsLayer = $("[data-pins]");
  const log = $("[data-log]");
  const askForm = $("[data-ask]");
  let cam = H.camera(S.view, 1, 1);
  let size = { w: 1, h: 1, dpr: 1 };
  const staticLayer = document.createElement("canvas");
  const heatLayer = document.createElement("canvas");
  const tagChip = el("div", "tag-chip");
  tagChip.hidden = true;
  pinsLayer.append(tagChip);

  // ---------- setup: the config, the lenses, presets in the address ----------
  fetch("/api/config")
    .then((r) => r.json())
    .then((config) => {
      document.querySelectorAll("[data-mark]").forEach((n) => (n.textContent = config.mark));
      document.querySelectorAll("[data-product]").forEach((n) => (n.textContent = config.product));
      document.title = `${config.mark}: the ${config.product} heads-up display`;
      S.matches = config.matches;
      for (const m of config.matches) {
        const option = el("option", "", `${m.home.name} v ${m.away.name}`);
        option.value = m.seed;
        $("[data-matches]").append(option);
      }
      if (!config.models) form.narration.value = "template";
      const params = new URLSearchParams(location.search);
      if (params.has("seed")) form.seed.value = params.get("seed");
      clubs();
      preset(params);
    });

  // The three lenses: cards on the slate, buttons on the deck. Keys 1, 2 and 3 switch between them.
  Object.entries(H.LENSES).forEach(([key, lens], i) => {
    const card = el("label", "lens-card");
    card.style.setProperty("--lens", LENS_COLOR[key]);
    const radio = Object.assign(document.createElement("input"), { type: "radio", name: "lens", value: key, checked: key === "fan" });
    card.append(radio, el("b", "", lens.name), el("span", "", lens.blurb));
    $("[data-lens-cards]").append(card);
    const button = Object.assign(el("button", "", lens.name), { type: "button" });
    button.dataset.lens = key;
    button.append(el("kbd", "", String(i + 1)));
    button.addEventListener("click", () => setLens(key));
    $("[data-lenses]").append(button);
  });

  form.seed.addEventListener("change", clubs);
  function clubs() {
    const match = S.matches.find((m) => String(m.seed) === form.seed.value);
    if (!match) return;
    for (const option of form.club.querySelectorAll("[data-side]")) option.textContent = match[option.dataset.side].name;
  }

  // ?lens=referee&seed=21&narration=foundry&lang=ur&start=54&speed=30&strictness=strict&club=home
  // &stress=1&view=top&layers=ball,fouls,zones&autostart=1: a recording starts the same way every take.
  function preset(params) {
    for (const name of ["seed", "narration", "lang", "start", "speed", "strictness", "club"]) {
      const value = params.get(name);
      const select = form.elements[name];
      // Any minute can start a take, not only the menu's: one not on it is added, never ignored.
      if (name === "start" && /^\d{1,2}$/.test(value ?? "") && Number(value) <= 90 && ![...select.options].some((o) => o.value === value)) {
        select.append(Object.assign(el("option", "", `${value}'`), { value }));
      }
      if (value !== null && [...select.options].some((o) => o.value === value)) select.value = value;
    }
    if (params.has("stress")) form.stress.checked = params.get("stress") === "1";
    const lens = H.lensOf(params.get("lens"));
    form.querySelector(`[name=lens][value=${lens}]`).checked = true;
    if (params.get("view") === "top" || params.get("view") === "stand") S.view = params.get("view");
    if (params.has("layers")) {
      const wanted = new Set(params.get("layers").split(","));
      S.fixed = Object.fromEntries(Object.keys(H.LAYERS).map((k) => [k, wanted.has(k)]));
    }
    setLens(lens);
    setView(S.view);
    if (params.get("autostart") === "1") start();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    start();
  });
  form.addEventListener("change", (event) => {
    if (event.target.name === "lens") setLens(event.target.value);
  });

  function setLens(name) {
    S.lens = H.lensOf(name);
    document.body.dataset.lens = S.lens;
    for (const b of document.querySelectorAll("[data-lenses] button")) b.setAttribute("aria-pressed", String(b.dataset.lens === S.lens));
    S.saved = S.fixed ?? store.get(`hud2.layers.${S.lens}`, {});
    S.layers = H.layersFor(S.lens, S.saved);
    askForm.question.placeholder = {
      referee: "Ask the match: how many fouls has each side made?",
      commentator: "Ask the match: who has completed the most passes?",
      fan: "Ask the match: who has had the better chances?",
    }[S.lens];
    layerList();
    for (const item of log.children) item.hidden = Boolean(item.dataset.kind) && !H.shows(S.lens, item.dataset.kind);
    readouts();
    paintStatic();
  }

  const on = (layer) => S.layers.includes(layer);

  // ---------- layers: the lens's own, and the viewer's choices on top ----------
  function layerList() {
    const list = $("[data-layer-list]");
    list.replaceChildren(...Object.entries(H.LAYERS).map(([key, label]) => {
      const row = el("label");
      const box = Object.assign(document.createElement("input"), { type: "checkbox", checked: on(key) });
      box.addEventListener("change", () => {
        S.saved = { ...S.saved, [key]: box.checked };
        if (!S.fixed) store.set(`hud2.layers.${S.lens}`, S.saved);
        S.layers = H.layersFor(S.lens, S.saved);
        S.heatDirty = true;
        readouts();
        paintStatic();
      });
      row.append(box, document.createTextNode(label));
      return row;
    }));
  }
  const layersButton = $("[data-layers-open]");
  layersButton.addEventListener("click", () => {
    const open = layersButton.getAttribute("aria-expanded") !== "true";
    layersButton.setAttribute("aria-expanded", String(open));
    $("[data-layers]").hidden = !open;
  });
  $("[data-layers-reset]").addEventListener("click", () => {
    S.fixed = null;
    store.set(`hud2.layers.${S.lens}`, {});
    setLens(S.lens);
  });

  // ---------- the camera ----------
  $("[data-view]").addEventListener("click", () => setView(S.view === "stand" ? "top" : "stand"));
  function setView(view) {
    S.view = view;
    store.set("hud2.view", view);
    const button = $("[data-view]");
    button.textContent = view === "stand" ? "Camera: the stand" : "Camera: above";
    button.setAttribute("aria-pressed", String(view === "top"));
    resize();
  }

  document.addEventListener("keydown", (event) => {
    if (event.target.closest("input, select, textarea") || event.metaKey || event.ctrlKey || event.altKey) return;
    const lens = Object.keys(H.LENSES)[Number(event.key) - 1];
    if (lens && document.body.dataset.state !== "slate") setLens(lens);
    if (event.key === "v" || event.key === "V") setView(S.view === "stand" ? "top" : "stand");
    if (event.key === "Escape" && layersButton.getAttribute("aria-expanded") === "true") layersButton.click();
  });

  new ResizeObserver(resize).observe(box);
  function resize() {
    const rect = box.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    size = { w: Math.max(1, rect.width), h: Math.max(1, rect.height), dpr };
    for (const c of [canvas, staticLayer, heatLayer]) {
      c.width = Math.round(size.w * dpr);
      c.height = Math.round(size.h * dpr);
    }
    cam = H.camera(S.view, size.w, size.h);
    S.heatDirty = true;
    paintStatic();
  }

  // ---------- the match ----------
  function start() {
    S.source?.close();
    const lens = form.querySelector("[name=lens]:checked")?.value ?? "fan";
    setLens(lens);
    Object.assign(S, {
      plays: [], placed: new Map(), ball: null, ballTeam: null, onBall: null, lastFoul: null, nowT: 0, period: 1,
      pins: [], locks: [], bursts: [], pulse: null, cards: [], explain: null, live: true,
      tally: { aired: 0, refused: 0, checked: 0 }, heatDirty: true,
    });
    for (const pin of pinsLayer.querySelectorAll(".pin")) pin.remove();
    log.replaceChildren();
    meter();
    document.body.dataset.state = "live";
    for (const node of ["[data-bug]", "[data-meter]", "[data-read]", "[data-log-rail]", "[data-deck]"]) $(node).hidden = false;
    $("[data-slate]").hidden = true;
    $("[data-live]").dataset.on = "true";
    $("[data-live]").textContent = "Live";
    resize();
    const params = new URLSearchParams({
      seed: form.seed.value,
      narration: form.narration.value,
      start: form.start.value,
      speed: form.speed.value,
      mode: H.LENSES[S.lens].mode,
      lang: form.lang.value,
      stress: form.stress.checked ? "0.25" : "0",
      strictness: form.strictness.value,
      club: form.club.value,
      hud: "1",
    });
    const source = new EventSource(`/api/stream?${params}`);
    S.source = source;
    const listen = (kind, handler) => source.addEventListener(kind, (e) => handler(JSON.parse(e.data)));
    listen("hello", hello);
    listen("clock", clock);
    listen("play", play);
    listen("pulse", (d) => { S.pulse = d; readouts(); });
    listen("output", output);
    listen("recap", recap);
    listen("block", (b) => ($("[data-chain]").textContent = `block ${b.height}`));
    listen("end", finish);
    // An EventSource reconnects by itself, which would start a new match: close on any error.
    source.addEventListener("error", (e) => {
      if (e.data) {
        const { detail, ref } = JSON.parse(e.data);
        note(ref ? `Sorry: ${detail} (reference ${ref}).` : `Sorry: ${detail}.`);
      } else if (source.readyState !== EventSource.CLOSED) note("The connection to the studio dropped.");
      stop();
    });
  }

  function stop() {
    S.source?.close();
    S.source = null;
    S.live = false;
    $("[data-live]").dataset.on = "false";
  }

  $("[data-new]").addEventListener("click", () => {
    stop();
    document.body.dataset.state = "slate";
    for (const node of ["[data-read]", "[data-log-rail]", "[data-deck]", "[data-bug]", "[data-meter]"]) $(node).hidden = true;
    $("[data-slate]").hidden = false;
    resize();
  });

  function hello(d) {
    S.session = d.session;
    S.askSession = d.session;
    S.teams = { home: d.home, away: d.away };
    S.zones = d.hud?.zones ?? null;
    S.homeFirst = d.hud?.home_attacks_right_first ?? true;
    S.strictness = d.strictness;
    S.prefs = d.prefs ?? {};
    for (const side of ["home", "away"]) {
      const node = $(`.bug [data-side=${side}]`);
      node.querySelector("b").textContent = d[side].short;
      node.title = d[side].name;
      node.style.setProperty("--team", d[side].color);
    }
    const who = d.narration === "foundry" ? "AI models on Microsoft Foundry write the lines" : "The offline template writes the lines";
    note(`${d.home.name} v ${d.away.name}, ${d.competition}. ${who}; the Critic checks every one.`);
    for (const text of d.notices) note(text);
    if (S.prefs.club) note(`Your club is ${d[S.prefs.club].name}: its moments glow.`);
    readouts();
    paintStatic();
  }

  function clock(d) {
    $("[data-clock]").textContent = d.minute;
    $("[data-score]").textContent = `${d.score[0]} – ${d.score[1]}`;
  }

  function attacksRight(team, period) {
    const homeRight = S.homeFirst === (period === 1);
    return team === "home" ? homeRight : !homeRight;
  }

  function play(p) {
    p.at = now();
    S.plays.push(p);
    if (S.plays.length > 2500) S.plays.splice(0, S.plays.length - 2500);
    S.placed.set(p.id, p);
    S.nowT = p.t;
    S.period = p.period;
    S.heatDirty = true;
    if (p.kind !== "pressure") {
      S.ball = H.ballAt(p);
      S.ballTeam = p.team;
    }
    if (p.player && p.kind !== "pressure") S.onBall = { name: p.player, number: p.number, team: p.team };
    if (p.kind === "tackle" && p.outcome === "foul") {
      S.lastFoul = p;
      if (S.lens === "referee") readouts();
    }
    if (p.kind === "shot" && p.outcome === "goal") goal(p);
  }

  function goal(p) {
    const team = S.teams?.[p.team];
    S.bursts.push({ kind: "goal", x: p.x > 52.5 ? 105 : 0, y: 34, color: team?.color ?? "#ffffff", born: now() });
    if (S.lens === "referee") return; // the referee's lens shows the least: the rings, no banner
    const banner = $("[data-goal]");
    banner.style.setProperty("--team", team?.color ?? "#fff");
    banner.replaceChildren(el("strong", "", "Goal"), el("span", "", `${team?.name ?? ""}: ${p.player}, ${p.minute}`));
    banner.hidden = false;
    clearTimeout(goal.timer);
    goal.timer = setTimeout(() => (banner.hidden = true), 2600);
  }

  function output(o) {
    if (o.type === "cue") return cue(o);
    if (o.type === "rejection" || o.type === "spiked") return refused(o);
    if (o.type === "degradation") {
      const off = o.level === "detection_only";
      note(off ? `${o.minute} The narrator is down: lines carry the Scout's computed facts until it's back.` : `${o.minute} The narrator is back.`);
    }
  }

  function cue(c) {
    S.tally.aired += 1;
    S.tally.checked += c.receipt?.numbers_checked ?? 0;
    meter();
    if (c.kind === "ref_call" && c.call && c.call.card !== "none") {
      const fouler = c.players?.find((p) => p.team === c.team);
      S.cards.push({ minute: c.minute, team: c.team, card: c.call.card, who: fouler?.name ?? "" });
    }
    if (H.EXPLAIN[c.kind]) S.explain = c.kind;
    readouts();
    const mine = c.for_you?.some((m) => m !== "rival");
    const item = el("li", `${c.status === "verified" ? "" : "detection"}${mine ? " mine" : ""}`);
    item.dataset.kind = c.kind;
    if (mine) item.style.setProperty("--team", S.teams?.[c.team]?.color ?? "#fff");
    item.append(el("span", "when", c.minute), el("span", "what", c.headline), say(c.text, c.lang), el("small", "", seal(c)));
    item.hidden = !H.shows(S.lens, c.kind);
    prependLog(item);
    if (!H.shows(S.lens, c.kind) || !on("lines")) return;
    const anchor = H.anchorOf(c.evidence, S.placed) ?? S.ball;
    if (!anchor) return;
    const status = c.status === "verified" ? "verified" : "detection";
    const body = el("div", `pin ${status}`);
    const head = el("header");
    head.append(el("span", "when", c.minute), el("span", "what", c.headline));
    if (c.call && c.call.card !== "none") head.append(el("span", `ref-card card-chip ${c.call.card}`, c.call.card === "red" ? "Red" : "Yellow"));
    body.append(head, say(c.text, c.lang), el("span", "seal", seal(c)));
    pin(body, anchor, LIFE.pin, status === "verified" ? COLORS.lime : COLORS.gold);
    S.locks.push({ x: anchor[0], y: anchor[1], born: now(), color: status === "verified" ? COLORS.gold : COLORS.chalk });
  }

  function seal(c) {
    if (c.status !== "verified") return "The narrator was down: the Scout's facts, as computed";
    const r = c.receipt;
    const parts = [`Checked: ${plural(r?.numbers_checked ?? 0, "number")}`, `${plural(c.evidence.length, "event")} cited`];
    if (c.attempts > 1) parts.push(`on attempt ${c.attempts}`);
    return parts.join(", ");
  }

  function refused(o) {
    S.tally.refused += 1;
    meter();
    const item = el("li", "refused");
    item.append(el("span", "when", o.minute), el("span", "what", o.type === "spiked" ? "Spiked: never aired" : "Refused before it aired"), el("p"));
    item.querySelector("p").append(el("s", "", o.claim.text));
    for (const r of o.reasons) item.append(el("small", "", `${REASONS[r.code] ?? r.code}: ${r.detail}`));
    prependLog(item);
    if (!on("refusals")) return;
    const anchor = H.anchorOf(o.claim.citations, S.placed) ?? S.ball;
    if (!anchor) return;
    const body = el("div", "pin refused");
    const head = el("header");
    head.append(el("span", "when", o.minute), el("span", "what", "Refused"));
    const struck = el("p");
    struck.append(el("s", "", o.claim.text));
    body.append(head, struck, el("span", "seal", REASONS[o.reasons[0]?.code] ?? "The Critic couldn't prove it"));
    pin(body, anchor, LIFE.refused, COLORS.card);
    S.bursts.push({ kind: "refused", x: anchor[0], y: anchor[1], born: now() });
  }

  function say(text, lang) {
    return Object.assign(el("p", "", text), { lang, dir: lang === "en" ? "ltr" : "rtl" });
  }

  function prependLog(item) {
    log.prepend(item);
    while (log.children.length > 80) log.lastElementChild.remove();
  }

  function note(text) {
    prependLog(el("li", "note", text));
  }

  function recap(d) {
    const url = URL.createObjectURL(new Blob([d.html], { type: "text/html" }));
    const item = el("li", "note", "The recap is ready, every line checked by the Critic: ");
    item.append(Object.assign(el("a", "", "read it"), { href: url, target: "_blank", rel: "noopener" }));
    prependLog(item);
  }

  function finish(summary) {
    const s = summary.stats;
    note(`Full time. ${plural(s.aired ?? 0, "line")} aired checked, ${plural(s.rejected ?? 0, "claim")} refused and rewritten. Model cost $${summary.cost_usd.toFixed(4)}. You can still ask about the whole match.`);
    $("[data-live]").textContent = "Full time";
    if (summary.ledger) {
      $("[data-chain]").textContent = "sealed";
      note(`The match ledger is sealed: ${plural(summary.ledger.blocks, "block")}, ${plural(summary.ledger.entries, "entry", "entries")}, seal ${summary.ledger.seal.slice(0, 16)}…`);
    }
    stop();
  }

  function meter() {
    $("[data-aired]").textContent = S.tally.aired;
    $("[data-refused]").textContent = S.tally.refused;
    $("[data-checked]").textContent = S.tally.checked;
  }

  // ---------- ask the match, from any lens ----------
  askForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = askForm.question.value.trim();
    if (!question || !S.askSession) return;
    const go = $("[data-ask-go]");
    go.disabled = true;
    go.textContent = "Checking";
    try {
      const response = await fetch(`/api/sessions/${S.askSession}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const a = await response.json().catch(() => ({}));
      if (!response.ok) return note(`${a.detail ?? "That question couldn't be asked"}.`);
      askForm.question.value = "";
      const verdict = {
        verified: `Checked by the Critic: ${plural(a.receipt.numbers_checked, "number")} matched`,
        cannot: "The events can't answer this: fixed words, not a model's",
        refused: "No answer could be proven",
      }[a.status];
      const item = el("li", a.status === "refused" ? "refused" : a.status === "cannot" ? "note" : "");
      item.append(el("span", "when", a.minute), el("span", "what", `You asked: ${a.question}`), say(a.text, a.lang), el("small", "", `${verdict}. ${plural(a.left, "question")} left.`));
      prependLog(item);
      const anchor = H.anchorOf(a.evidence, S.placed) ?? S.ball;
      if (!anchor) return;
      const body = el("div", `pin answer${a.status === "refused" ? " refused" : ""}`);
      const head = el("header");
      head.append(el("span", "when", a.minute), el("span", "what", "Your question"));
      body.append(head, say(a.text, a.lang), el("span", "seal", verdict));
      pin(body, anchor, LIFE.answer, COLORS.chalk);
    } catch {
      note("The studio didn't answer. Try again.");
    } finally {
      go.disabled = false;
      go.textContent = "Ask";
    }
  });

  // ---------- readouts: each lens's numbers, all of them counted on the server ----------
  function readouts() {
    const rail = $("[data-read]");
    const p = S.pulse;
    const parts = { referee: refereeRead, commentator: commentatorRead, fan: fanRead }[S.lens](p);
    rail.replaceChildren(...parts);
  }

  const name = (side) => S.teams?.[side]?.name ?? side;
  const color = (side) => S.teams?.[side]?.color ?? "#F4F1E8";
  const fmt = (metric, v) => (v === null || v === undefined ? "–" : metric === "xg" ? v.toFixed(2) : String(v));

  function duel(label, metric, of) {
    const row = el("div", "duel");
    const [a, b] = [of.home[metric], of.away[metric]];
    const bar = el("div", "duel-bar");
    for (const [side, v] of [["home", a], ["away", b]]) {
      const part = el("span");
      part.style.setProperty("--team", color(side));
      part.style.flexGrow = String(a + b > 0 ? v : 1);
      bar.append(part);
    }
    row.append(el("span", "duel-label", label), el("b", "", fmt(metric, a)), bar, el("b", "", fmt(metric, b)));
    return row;
  }

  function waiting() {
    return el("p", "", "The numbers arrive with the first minute played.");
  }

  function commentatorRead(p) {
    const out = [el("h2", "", "The last five minutes")];
    if (S.onBall) {
      const ball = el("div", "on-ball");
      ball.style.setProperty("--team", color(S.onBall.team));
      ball.append(el("span", "no", String(S.onBall.number)), el("strong", "", S.onBall.name), el("span", "", name(S.onBall.team)));
      out.push(el("p", "", "Last on the ball"), ball);
    }
    if (!p) return [...out, waiting()];
    out.push(
      duel("Passes", "passes", p.recent),
      duel("Shots", "shots", p.recent),
      duel("Expected goals (xG)", "xg", p.recent),
      duel("Passes ending in the final third", "final_third_passes", p.recent),
      duel("Passes into the box", "box_entries", p.recent),
      duel("Presses high up the pitch", "high_pressures", p.recent),
      duel("Ball won high up the pitch", "high_ball_wins", p.recent),
      el("h3", "", "The match so far"),
      duel("Shots", "shots", p.match),
      duel("Expected goals (xG)", "xg", p.match),
      duel("Passes completed", "passes_completed", p.match),
      duel("Tackles won", "tackles_won", p.match),
      el("p", "from", `As of ${p.minute}, counted from the events by the code the Critic checks with.`),
    );
    return out;
  }

  function refereeRead(p) {
    const out = [el("h2", "", "Discipline")];
    const cards = el("div", "card-row");
    for (const c of S.cards) cards.append(el("span", `ref-card ${c.card}`, `${c.minute}: ${c.who || name(c.team)} (${S.teams?.[c.team]?.short ?? c.team})`));
    out.push(S.cards.length ? cards : el("p", "", "No card has been called yet."));
    if (p) out.push(duel("Fouls, the match so far", "fouls", p.match), duel("Fouls, the last five minutes", "fouls", p.recent), duel("Tackles won", "tackles_won", p.match), duel("Presses high up, the last five minutes", "high_pressures", p.recent));
    else out.push(waiting());
    if (S.lastFoul) {
      const f = S.lastFoul;
      out.push(el("h3", "", "The last foul"), el("p", "", `${f.minute}: ${f.player} on ${f.opponent}, ${f.to_goal_m} m from the goal ${name(f.team)} defend${f.in_area ? ", inside the penalty area" : ""}.`));
    }
    if (S.zones) {
      const z = S.zones;
      const promising = z.promising_x > 0 ? ` Within ${z.promising_x} m of the fouling side's own goal, it stops a promising attack.` : " A stopped attack alone earns no card.";
      out.push(el("h3", "", "How the calls are read"), el("p", "", `A ${S.strictness} reading of the Law: a foul within ${z.goal_chance_m} m of goal and ${z.central_m} m of its middle denies a goal-scoring chance.${promising} Event data sees where a foul was, not how hard, so every call is likely.`));
    }
    return out;
  }

  function fanRead(p) {
    const out = [el("h2", "", "Who's on top")];
    if (!p) out.push(waiting());
    else {
      const tilt = el("div", "tilt");
      for (const side of ["home", "away"]) {
        const part = el("span");
        part.style.setProperty("--team", color(side));
        part.style.flexGrow = String(p.share[side] ?? 1);
        tilt.append(part);
      }
      const lead = (p.share.home ?? 0) >= (p.share.away ?? 0) ? "home" : "away";
      const share = p.share[lead];
      out.push(tilt, el("p", "", share === null ? "Nobody has had the ball yet." : `${name(lead)} have had ${share}% of the passes in the last five minutes.`));
      const pair = el("div", "big-pair");
      for (const side of ["home", "away"]) {
        const cell = el("div");
        cell.style.setProperty("--team", color(side));
        cell.append(el("small", "", S.teams?.[side]?.short ?? side), el("strong", "", String(p.match[side].shots)), el("small", "", `shots, xG ${p.match[side].xg.toFixed(2)}`));
        pair.append(cell);
      }
      out.push(el("h3", "", "Chances so far"), pair);
    }
    if (S.prefs.club) out.push(el("p", "", `Your club: ${name(S.prefs.club)}. Its moments glow in the log.`));
    if (on("explain") && S.explain) {
      const card = el("div", "explain");
      card.append(el("b", "", KIND[S.explain]), document.createTextNode(H.EXPLAIN[S.explain]));
      out.push(card);
    }
    return out;
  }

  // ---------- pins: a checked line where it happened ----------
  function pin(body, anchor, life, rgb) {
    pinsLayer.append(body);
    const item = { node: body, anchor, born: now(), life, rgb, w: body.offsetWidth, h: body.offsetHeight };
    S.pins.push(item);
    const most = size.w < 640 ? 1 : MAX_PINS; // a phone's field has room for one
    while (S.pins.length > most) S.pins.shift().node.remove();
  }

  function placePins(t) {
    const taken = [];
    for (const p of S.pins) {
      const age = t - p.born;
      if (age > p.life) { p.node.remove(); p.gone = true; continue; }
      const [ax, ay] = cam.project(p.anchor[0], p.anchor[1]);
      let x = ax < size.w * 0.6 ? ax + 26 : ax - 26 - p.w;
      let y = ay - p.h - 30;
      x = Math.max(8, Math.min(size.w - p.w - 8, x));
      y = Math.max(8, Math.min(size.h - p.h - 8, y));
      // Pins that would overlap stack instead.
      for (const r of taken) if (x < r.x + r.w && r.x < x + p.w && y < r.y + r.h && r.y < y + p.h) y = Math.min(size.h - p.h - 8, r.y + r.h + 8);
      taken.push({ x, y, w: p.w, h: p.h });
      p.box = { x, y };
      p.node.style.transform = `translate(${x}px, ${y}px)`;
      p.node.style.opacity = String(Math.min(1, (p.life - age) / 0.8));
    }
    S.pins = S.pins.filter((p) => !p.gone);
  }

  // ---------- drawing ----------
  const rgba = (hex, a) => {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
  };
  const P = (x, y) => cam.project(x, y);

  function path(c, points, close = false) {
    c.beginPath();
    points.forEach(([x, y], i) => {
      const [sx, sy] = P(x, y);
      if (i) c.lineTo(sx, sy);
      else c.moveTo(sx, sy);
    });
    if (close) c.closePath();
  }

  function ring(cx, cy, r, from = 0, to = Math.PI * 2, steps = 40) {
    const out = [];
    for (let i = 0; i <= steps; i++) {
      const a = from + ((to - from) * i) / steps;
      out.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]);
    }
    return out;
  }

  function rect(x0, y0, x1, y1) {
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  }

  // The pitch, and the referee's zones: drawn once per size, view or lens.
  function paintStatic() {
    const c = staticLayer.getContext("2d");
    c.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
    c.clearRect(0, 0, size.w, size.h);
    // The grass, mown in stripes, so the perspective reads.
    for (let i = 0; i < 10; i++) {
      path(c, rect(i * 10.5, 0, (i + 1) * 10.5, 68), true);
      c.fillStyle = i % 2 ? "rgba(30, 123, 69, 0.13)" : "rgba(30, 123, 69, 0.08)";
      c.fill();
    }
    c.strokeStyle = `rgba(${COLORS.chalk}, 0.42)`;
    c.lineWidth = 1.2;
    c.shadowColor = `rgba(${COLORS.lime}, 0.45)`;
    c.shadowBlur = 6;
    const lines = [
      [rect(0, 0, 105, 68), true],
      [[[52.5, 0], [52.5, 68]], false],
      [ring(52.5, 34, 9.15), false],
      [rect(0, 13.84, 16.5, 54.16), true],
      [rect(88.5, 13.84, 105, 54.16), true],
      [rect(0, 24.84, 5.5, 43.16), true],
      [rect(99.5, 24.84, 105, 43.16), true],
      [ring(11, 34, 9.15, -0.925, 0.925, 16), false],
      [ring(94, 34, 9.15, Math.PI - 0.925, Math.PI + 0.925, 16), false],
      [rect(-1.6, 30.34, 0, 37.66), false],
      [rect(105, 30.34, 106.6, 37.66), false],
    ];
    for (const [points, close] of lines) {
      path(c, points, close);
      c.stroke();
    }
    c.shadowBlur = 0;
    for (const [x, y] of [[52.5, 34], [11, 34], [94, 34]]) {
      const [sx, sy, s] = P(x, y);
      c.fillStyle = `rgba(${COLORS.chalk}, 0.5)`;
      c.beginPath();
      c.arc(sx, sy, Math.max(1.5, 0.3 * s), 0, Math.PI * 2);
      c.fill();
    }
    if (on("zones") && S.zones) zonesOn(c, S.zones);
  }

  // The referee's zones at both ends, as court.referee reads a foul: the penalty area, the
  // goal-chance zone (near and central), and the line of a promising attack.
  function zonesOn(c, z) {
    const half = Math.sqrt(Math.max(0, z.goal_chance_m ** 2 - z.central_m ** 2));
    const reach = Math.asin(Math.min(1, z.central_m / z.goal_chance_m));
    for (const right of [false, true]) {
      const mx = (x) => (right ? 105 - x : x);
      const area = rect(mx(0), z.area_y0, mx(z.area_x), z.area_y1);
      path(c, area, true);
      c.fillStyle = `rgba(${COLORS.gold}, 0.07)`;
      c.fill();
      const zone = [[mx(0), 34 - z.central_m], [mx(half), 34 - z.central_m]];
      for (const [x, y] of ring(0, 34, z.goal_chance_m, -reach, reach, 24)) zone.push([mx(x), y]);
      zone.push([mx(half), 34 + z.central_m], [mx(0), 34 + z.central_m]);
      path(c, zone, true);
      c.fillStyle = `rgba(${COLORS.gold}, 0.08)`;
      c.fill();
      c.setLineDash([6, 5]);
      c.strokeStyle = `rgba(${COLORS.gold}, 0.7)`;
      c.lineWidth = 1.2;
      c.stroke();
      if (z.promising_x > 0) {
        path(c, [[mx(z.promising_x), 0], [mx(z.promising_x), 68]]);
        c.strokeStyle = `rgba(${COLORS.gold}, 0.35)`;
        c.stroke();
      }
      c.setLineDash([]);
      c.font = "500 11px 'JetBrains Mono', monospace";
      c.fillStyle = `rgba(${COLORS.gold}, 0.9)`;
      c.textAlign = right ? "right" : "left";
      const [lx, ly] = P(mx(1), 34 + z.central_m + 3.5);
      c.fillText(`goal chance: ${z.goal_chance_m} m`, lx, ly);
      if (z.promising_x > 0) {
        // Beside its line, on the side of the goal it belongs to, so the two never meet midfield.
        const [px, py] = P(mx(z.promising_x - 1), 66);
        c.textAlign = right ? "left" : "right";
        c.fillText(`promising attack: ${z.promising_x} m`, px, py);
      }
    }
    c.textAlign = "left";
  }

  // Where each side has played in the last five minutes of the half: soft light, no numbers.
  function paintHeat() {
    const c = heatLayer.getContext("2d");
    c.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
    c.clearRect(0, 0, size.w, size.h);
    if (!on("heat") || !S.teams) return;
    c.globalCompositeOperation = "lighter";
    for (const p of S.plays) {
      if (p.period !== S.period || p.t < S.nowT - 300) continue;
      const [sx, sy, s] = P(p.x, p.y);
      const r = 7 * s;
      const glow = c.createRadialGradient(sx, sy, 0, sx, sy, r);
      glow.addColorStop(0, rgba(color(p.team), 0.07));
      glow.addColorStop(1, rgba(color(p.team), 0));
      c.fillStyle = glow;
      c.fillRect(sx - r, sy - r, r * 2, r * 2);
    }
    c.globalCompositeOperation = "source-over";
  }

  function draw() {
    const t = now();
    ctx.setTransform(size.dpr, 0, 0, size.dpr, 0, 0);
    ctx.clearRect(0, 0, size.w, size.h);
    ctx.drawImage(staticLayer, 0, 0, size.w, size.h);
    if (on("heat") && (S.heatDirty && t - S.heatAt > 0.4)) {
      paintHeat();
      S.heatDirty = false;
      S.heatAt = t;
    }
    if (on("heat")) ctx.drawImage(heatLayer, 0, 0, size.w, size.h);
    const recent = S.plays.slice(-60);
    if (on("pressure")) drawPressure(recent, t);
    if (on("passes")) drawPasses(recent, t);
    if (on("trail")) drawTrail(recent);
    if (on("fouls")) drawFouls(t);
    if (on("shots")) drawShots(t);
    drawBursts(t);
    if (on("ball") && S.ball) drawBall(t);
    drawLocks(t);
    placePins(t);
    drawLeaders();
    placeTag();
    requestAnimationFrame(draw);
  }

  function drawPasses(recent, t) {
    const passes = recent.filter((p) => p.kind === "pass").slice(-6);
    for (const p of passes) {
      const a = H.fade(t - p.at, LIFE.pass);
      if (!a) continue;
      const [x0, y0, s] = P(p.x, p.y);
      const [x1, y1] = P(p.ex, p.ey);
      ctx.lineWidth = Math.max(1, (p.box ? 0.5 : 0.3) * s);
      if (p.outcome === "complete") {
        ctx.setLineDash([]);
        ctx.strokeStyle = rgba(color(p.team), 0.85 * a);
      } else {
        ctx.setLineDash([5, 5]);
        ctx.strokeStyle = `rgba(${COLORS.chalk}, ${0.45 * a})`;
      }
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
      ctx.setLineDash([]);
      // The arrowhead, where it went
      const angle = Math.atan2(y1 - y0, x1 - x0);
      const head = Math.max(6, 0.9 * s);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x1 - head * Math.cos(angle - 0.45), y1 - head * Math.sin(angle - 0.45));
      ctx.lineTo(x1 - head * Math.cos(angle + 0.45), y1 - head * Math.sin(angle + 0.45));
      ctx.closePath();
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fill();
    }
  }

  function drawTrail(recent) {
    const points = recent.filter((p) => p.kind !== "pressure").slice(-12).map((p) => H.ballAt(p));
    for (let i = 1; i < points.length; i++) {
      const [x0, y0] = P(...points[i - 1]);
      const [x1, y1] = P(...points[i]);
      ctx.strokeStyle = `rgba(${COLORS.lime}, ${(0.55 * i) / points.length})`;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
    }
  }

  function drawPressure(recent, t) {
    for (const p of recent) {
      if (p.kind !== "pressure") continue;
      const a = H.fade(t - p.at, LIFE.pressure);
      if (!a) continue;
      const grow = still.matches ? 1 : 1 + 0.5 * (1 - a);
      path(ctx, ring(p.x, p.y, 1.8 * grow, 0, Math.PI * 2, 24), true);
      ctx.strokeStyle = rgba(color(p.team), 0.8 * a);
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  function drawFouls(t) {
    for (const p of S.plays.slice(-400)) {
      if (p.kind !== "tackle") continue;
      const [sx, sy, s] = P(p.x, p.y);
      const age = t - p.at;
      if (p.outcome !== "foul") {
        const a = H.fade(age, LIFE.pass);
        if (!a) continue;
        const d = Math.max(3, 0.6 * s);
        ctx.fillStyle = rgba(color(p.team), 0.7 * a);
        ctx.beginPath();
        ctx.moveTo(sx, sy - d); ctx.lineTo(sx + d, sy); ctx.lineTo(sx, sy + d); ctx.lineTo(sx - d, sy);
        ctx.fill();
        continue;
      }
      // A foul stays marked all match: an X in the fouling side's colour.
      const d = Math.max(4, 0.8 * s);
      ctx.strokeStyle = rgba(color(p.team), 0.95);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx - d, sy - d); ctx.lineTo(sx + d, sy + d);
      ctx.moveTo(sx + d, sy - d); ctx.lineTo(sx - d, sy + d);
      ctx.stroke();
      const a = H.fade(age, LIFE.foul);
      if (!a) continue;
      // The latest fouls: how far from the goal the fouling side defends.
      const goalX = attacksRight(p.team, p.period) ? 0 : 105;
      const [gx, gy] = P(goalX, 34);
      ctx.setLineDash([3, 4]);
      ctx.strokeStyle = `rgba(${COLORS.gold}, ${0.8 * a})`;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(gx, gy);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.font = "500 12px 'JetBrains Mono', monospace";
      ctx.fillStyle = `rgba(${COLORS.gold}, ${a})`;
      ctx.fillText(`${p.to_goal_m} m${p.in_area ? ", in the area" : ""}`, sx + d + 6, sy - d - 4);
    }
  }

  function drawShots(t) {
    for (const p of S.plays) {
      if (p.kind !== "shot") continue;
      const [sx, sy, s] = P(p.x, p.y);
      const r = Math.max(3, (0.9 + 3.2 * p.xg) * s);
      const team = color(p.team);
      ctx.beginPath();
      ctx.ellipse(sx, sy, r, cam.view === "stand" ? r * 0.62 : r, 0, 0, Math.PI * 2);
      if (p.outcome === "goal") {
        ctx.fillStyle = rgba(team, 0.85);
        ctx.shadowColor = team;
        ctx.shadowBlur = 14;
        ctx.fill();
        ctx.shadowBlur = 0;
      } else {
        ctx.strokeStyle = rgba(team, 0.8);
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
      const a = H.fade(t - p.at, LIFE.shot);
      if (!a) continue;
      const [gx, gy] = P(p.x > 52.5 ? 105 : 0, 34);
      ctx.strokeStyle = rgba(team, 0.9 * a);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(gx, gy);
      ctx.stroke();
      ctx.font = "500 12px 'JetBrains Mono', monospace";
      ctx.fillStyle = `rgba(${COLORS.chalk}, ${a})`;
      ctx.fillText(`xG ${p.xg.toFixed(2)}`, sx + r + 6, sy + 4);
    }
  }

  // The ball, locked on: five arcs like the crest's feathers, the Critic's in gold.
  function drawBall(t) {
    const [x, y] = S.ball;
    const spin = still.matches ? 0 : t * 0.6;
    for (let i = 0; i < 5; i++) {
      const from = spin + (i * Math.PI * 2) / 5 + 0.16;
      path(ctx, ring(x, y, 2.6, from, from + (Math.PI * 2) / 5 - 0.32, 10));
      ctx.strokeStyle = i === 2 ? `rgba(${COLORS.gold}, 0.95)` : `rgba(${COLORS.lime}, 0.85)`;
      ctx.lineWidth = 2;
      ctx.stroke();
    }
    const [sx, sy, s] = P(x, y);
    ctx.fillStyle = `rgba(${COLORS.lime}, 1)`;
    ctx.shadowColor = `rgba(${COLORS.lime}, 0.9)`;
    ctx.shadowBlur = 12;
    ctx.beginPath();
    ctx.arc(sx, sy, Math.max(2.5, 0.45 * s), 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;
  }

  // The Critic's lock: brackets that close on the spot a checked line is about.
  function drawLocks(t) {
    S.locks = S.locks.filter((l) => t - l.born < LIFE.lock);
    for (const l of S.locks) {
      const age = t - l.born;
      const close = still.matches ? 1 : Math.min(1, age / 0.5);
      const [sx, sy, s] = P(l.x, l.y);
      const half = Math.max(10, (6 - 3.2 * (1 - (1 - close) ** 3)) * s);
      const arm = half * 0.45;
      ctx.strokeStyle = `rgba(${l.color}, ${H.fade(age, LIFE.lock)})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (const [dx, dy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) {
        const cx = sx + dx * half;
        const cy = sy + dy * half;
        ctx.moveTo(cx - dx * arm, cy);
        ctx.lineTo(cx, cy);
        ctx.lineTo(cx, cy - dy * arm);
      }
      ctx.stroke();
    }
  }

  function drawBursts(t) {
    S.bursts = S.bursts.filter((b) => t - b.born < 1.8);
    for (const b of S.bursts) {
      const age = t - b.born;
      const [sx, sy, s] = P(b.x, b.y);
      if (b.kind === "goal") {
        for (let k = 0; k < 3; k++) {
          const grow = still.matches ? 0.5 : Math.max(0, age - k * 0.18) / 1.8;
          ctx.strokeStyle = rgba(b.color, 0.9 * (1 - grow));
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(sx, sy, (4 + 26 * grow) * s * 0.6, 0, Math.PI * 2);
          ctx.stroke();
        }
      } else {
        const a = 1 - age / 1.8;
        const d = Math.max(8, 1.6 * s);
        ctx.strokeStyle = `rgba(${COLORS.card}, ${a})`;
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(sx - d, sy - d); ctx.lineTo(sx + d, sy + d);
        ctx.moveTo(sx + d, sy - d); ctx.lineTo(sx - d, sy + d);
        ctx.stroke();
      }
    }
  }

  // A thin line from each pin to the spot it is about.
  function drawLeaders() {
    for (const p of S.pins) {
      if (!p.box) continue;
      const [ax, ay] = P(p.anchor[0], p.anchor[1]);
      const tx = p.box.x + p.w / 2 < ax ? p.box.x + p.w : p.box.x;
      const ty = p.box.y + p.h;
      ctx.strokeStyle = `rgba(${p.rgb}, ${Number(p.node.style.opacity || 1) * 0.8})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(tx, ty);
      ctx.stroke();
    }
  }

  function placeTag() {
    tagChip.hidden = !(on("names") && S.onBall && S.ball);
    if (tagChip.hidden) return;
    const [sx, sy] = P(S.ball[0], S.ball[1]);
    if (tagChip.dataset.who !== `${S.onBall.number}${S.onBall.name}`) {
      tagChip.dataset.who = `${S.onBall.number}${S.onBall.name}`;
      tagChip.style.setProperty("--team", color(S.onBall.team));
      tagChip.replaceChildren(el("b", "", String(S.onBall.number)), document.createTextNode(S.onBall.name));
    }
    tagChip.style.transform = `translate(${Math.min(size.w - 160, sx + 18)}px, ${Math.min(size.h - 28, sy + 14)}px)`;
  }

  resize();
  requestAnimationFrame(draw);
})();
