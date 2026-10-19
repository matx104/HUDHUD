// The studio page: opens one match as Server-Sent Events and renders what the court does with it.
// The server sends hello (teams, session, the viewer's preferences), clock (minute, score), shot,
// output (cue, rejection, spiked, degradation), personal (the player card and the single metric)
// and end. Nothing here computes a fact: every number on screen came from the server, and every
// line came through the Critic.
(() => {
  const $ = (sel) => document.querySelector(sel);
  const el = (tag, cls, text) => Object.assign(document.createElement(tag), { className: cls ?? "", textContent: text ?? "" });
  const svg = (tag, attrs) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };

  // The Critic's reason codes, in words a viewer understands (the showcase site uses the same).
  const REASONS = {
    no_evidence: "Cites no events at all",
    unknown_event: "Cites an event that doesn't exist",
    future_event: "Cites an event that hadn't happened yet",
    stale_event: "Cites events too old to support it",
    assertion_mismatch: "A number in it doesn't match the events",
    insufficient_evidence: "Not enough evidence for the claim",
    ungrounded_number: "States a number nothing in the evidence supports",
    no_rule: "No rule yet for checking this kind of claim",
  };

  const form = $("[data-setup]");
  const go = $("[data-go]");
  const pull = $("[data-pull]");
  const cues = $("[data-cues]");
  const cards = $("[data-cards]");
  const yours = { club: $("[data-club]"), player: $("[data-player]"), focus: $("[data-focus]"), metric: $("[data-metric]") };
  let source = null;
  let session = null;
  let teams = null;
  let matches = [];
  let history = [];
  // The voice: verified lines read aloud by Azure AI Speech, one after another, newest kept.
  const hear = $("[data-hear]");
  const said = new Map(); // cue id -> its list item, to mark the line being spoken
  let voiceSession = null;
  let queue = [];
  let speaking = false;
  let tally = { refused: 0, checked: 0, cost: 0 };

  fetch("/api/config")
    .then((r) => r.json())
    .then((config) => {
      document.querySelectorAll("[data-product]").forEach((n) => (n.textContent = config.product));
      document.title = `${config.product} studio`;
      matches = config.matches;
      for (const m of matches) {
        const option = el("option", "", `${m.home.name} v ${m.away.name}`);
        option.value = m.seed;
        $("[data-matches]").append(option);
      }
      if (!config.models) form.narration.value = "template";
      if (!config.voice) {
        hear.disabled = true;
        $("[data-hear-label]").title = "No voice is connected here: the offline studio has none";
      }
      const params = new URLSearchParams(location.search);
      if (params.has("seed")) form.seed.value = params.get("seed");
      fillYours();
      preset(params);
    });

  // The personal modes' pickers follow the chosen match: its two clubs, its 22 players.
  form.seed.addEventListener("change", fillYours);
  yours.player.addEventListener("change", focusable);
  function fillYours() {
    const match = matches.find((m) => String(m.seed) === form.seed.value);
    if (!match) return;
    for (const option of yours.club.querySelectorAll("[data-side]")) option.textContent = match[option.dataset.side].name;
    const keep = yours.player.value;
    yours.player.replaceChildren(Object.assign(el("option", "", "Nobody in particular"), { value: "" }));
    for (const side of ["home", "away"]) {
      const group = Object.assign(document.createElement("optgroup"), { label: match[side].name });
      for (const p of match.players.filter((x) => x.team === side)) {
        group.append(Object.assign(el("option", "", `${p.number} ${p.name} (${p.position})`), { value: p.id }));
      }
      yours.player.append(group);
    }
    if ([...yours.player.options].some((o) => o.value === keep)) yours.player.value = keep;
    focusable();
  }
  function focusable() {
    // Following one player needs a player to follow.
    const only = yours.focus.querySelector("[value=player]");
    only.disabled = !yours.player.value;
    if (only.disabled && yours.focus.value === "player") yours.focus.value = "match";
  }

  // Settings can ride in the address, so a recording starts the same way every take:
  // ?seed=21&narration=foundry&lang=ur&start=54&speed=30&stress=1&casual=0&autostart=1
  // and the personal modes: &club=home&player=h09&focus=player&metric=xg
  function preset(params) {
    for (const name of ["seed", "narration", "lang", "start", "speed", "strictness", "club", "player", "focus", "metric"]) {
      const value = params.get(name);
      const select = form.elements[name];
      if (value !== null && [...select.options].some((o) => o.value === value)) select.value = value;
      if (name === "player") focusable();
    }
    if (params.has("stress")) $("[data-stress]").checked = params.get("stress") === "1";
    if (params.has("casual")) $("[data-casual]").checked = params.get("casual") === "1";
    if (params.get("autostart") === "1") start();
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    start();
  });

  pull.addEventListener("click", async () => {
    if (!session) return;
    const offAir = pull.getAttribute("aria-pressed") === "true";
    const response = await fetch(`/api/sessions/${session}/air?on=${offAir}`, { method: "POST" });
    if (!response.ok) return;
    pull.setAttribute("aria-pressed", String(!offAir));
    pull.textContent = offAir ? "Take the narrator off air" : "Put the narrator back on air";
    notice(offAir
      ? "You put the narrator back on air. Full commentary resumes at the next moment."
      : "You took the narrator off air. Watch the Orchestrator keep the broadcast going.", offAir);
  });

  function start() {
    source?.close();
    cues.replaceChildren();
    cards.replaceChildren();
    $("[data-shots]").replaceChildren();
    $("[data-feed-hint]").hidden = true;
    $("[data-slate]").hidden = true;
    $("[data-board]").hidden = false;
    for (const node of ["[data-mine]", "[data-card]", "[data-ticker]"]) $(node).hidden = true;
    history = [];
    tally = { refused: 0, checked: 0, cost: 0 };
    drawTally();
    setLevel("full", "On air");
    pull.disabled = false;
    pull.setAttribute("aria-pressed", "false");
    pull.textContent = "Take the narrator off air";
    go.disabled = true;
    go.textContent = "Live";

    const params = new URLSearchParams({
      seed: form.seed.value,
      narration: form.narration.value,
      start: form.start.value,
      speed: form.speed.value,
      mode: $("[data-casual]").checked ? "casual" : "analyst",
      lang: form.lang.value,
      stress: $("[data-stress]").checked ? "0.25" : "0",
      strictness: form.strictness.value,
      club: yours.club.value,
      player: yours.player.value,
      focus: yours.focus.value,
      metric: yours.metric.value,
    });
    source = new EventSource(`/api/stream?${params}`);
    source.addEventListener("hello", (e) => hello(JSON.parse(e.data)));
    source.addEventListener("clock", (e) => clock(JSON.parse(e.data)));
    source.addEventListener("shot", (e) => shot(JSON.parse(e.data)));
    source.addEventListener("output", (e) => output(JSON.parse(e.data)));
    source.addEventListener("personal", (e) => personal(JSON.parse(e.data)));
    source.addEventListener("recap", (e) => recap(JSON.parse(e.data)));
    source.addEventListener("end", (e) => finish(JSON.parse(e.data)));
    // An EventSource reconnects by itself, which would start a new match: close on any error.
    source.addEventListener("error", (e) => {
      if (e.data) {
        const { detail, ref } = JSON.parse(e.data);
        notice(ref ? `Sorry: ${detail} (reference ${ref}).` : `Sorry: ${detail}.`);
      }
      else if (source.readyState !== EventSource.CLOSED) notice("The connection to the studio dropped.");
      stop();
    });
  }

  function stop() {
    source?.close();
    source = null;
    session = null;
    go.disabled = false;
    go.textContent = "Kick off again";
    pull.disabled = true;
  }

  function hello(data) {
    session = data.session;
    voiceSession = data.session; // kept after full time, so the last line can still be heard
    queue = [];
    said.clear();
    teams = { home: data.home, away: data.away };
    for (const side of ["home", "away"]) {
      const node = $(`[data-${side}]`);
      node.querySelector("b").textContent = data[side].short;
      node.title = data[side].name;
      node.style.setProperty("--team", data[side].color);
    }
    const who = data.narration === "foundry" ? "AI models on Microsoft Foundry write the commentary" : "The offline template writes the commentary";
    notice(`${data.home.name} v ${data.away.name}, ${data.competition}. ${who}. Fouls are called on a ${data.strictness ?? "standard"} reading of the Law.`, true);
    for (const text of data.notices) notice(text);
    const prefs = data.prefs ?? {};
    const parts = [];
    if (prefs.club) parts.push(`your club is ${data[prefs.club].name}: its moments are marked and come first, and the other side's still air`);
    if (prefs.player) parts.push(prefs.focus === "player" ? "only your player's moments air here; the rest are counted, not lost" : "your player's moments are marked");
    if (parts.length) notice(`Made yours: ${parts.join("; ")}. Every line still passed the Critic.`, true);
  }

  // The player card and the single metric: counted on the server from the match's own events.
  function personal(data) {
    $("[data-mine]").hidden = false;
    if (data.card) drawCard(data.card);
    if (data.metric) drawTicker(data.metric);
  }

  function drawCard(c) {
    const node = $("[data-card]");
    node.hidden = false;
    node.style.setProperty("--team", teams?.[c.player.team]?.color ?? "var(--lime)");
    const head = el("header");
    head.append(el("span", "card-no", String(c.player.number)), el("strong", "", c.player.name), el("span", "card-pos", c.player.position));
    const stats = el("dl");
    const rows = [
      ["Passes", c.passes ? `${c.passes_completed}/${c.passes}` : "0", c.completion_pct === null ? "" : `${c.completion_pct}%`],
      ["Chances created", c.chances_created],
      ["Shots", c.shots, c.shots ? `xG ${c.xg.toFixed(2)}` : ""],
      ["Goals", c.goals],
      ["Tackles won", c.tackles_won],
      ["Pressures", c.pressures],
    ];
    for (const [label, value, extra] of rows) {
      const box = el("div");
      const dd = el("dd", "", String(value));
      if (extra) dd.append(el("small", "", extra));
      box.append(el("dt", "", label), dd);
      stats.append(box);
    }
    node.replaceChildren(head, stats, el("p", "card-from", `Counted from ${c.evidence.length} of the player's own events`));
  }

  function drawTicker(m) {
    const node = $("[data-ticker]");
    node.hidden = false;
    // A share has no value before the first pass: the line starts once both sides have one.
    if (m.home !== null && m.away !== null) history.push([m.home, m.away]);
    const value = (v) => (v === null ? "–" : m.metric === "xg" ? v.toFixed(2) : String(v));
    const row = el("div", "ticker-row");
    for (const side of ["home", "away"]) {
      const cell = el("div", `ticker-side ${side}`);
      cell.style.setProperty("--team", teams?.[side]?.color ?? "var(--chalk)");
      cell.append(el("span", "ticker-team", teams?.[side]?.short ?? side), el("span", "ticker-value", value(m[side])));
      row.append(cell);
    }
    node.replaceChildren(el("h3", "", m.label), row, spark(), el("p", "card-from", `Counted from ${m.counted} events so far`));
  }

  // The metric minute by minute, both sides on one scale.
  function spark() {
    const w = 240, h = 48;
    const top = Math.max(1e-9, ...history.flat());
    const line = (i) => history.map(([a, b], n) => `${(n / Math.max(1, history.length - 1)) * w},${h - (([a, b][i]) / top) * (h - 4) - 2}`).join(" ");
    const box = svg("svg", { viewBox: `0 0 ${w} ${h}`, class: "spark", preserveAspectRatio: "none", role: "img", "aria-label": "The metric over the match so far" });
    for (const [i, side] of [[0, "home"], [1, "away"]]) {
      box.append(svg("polyline", { points: line(i), fill: "none", stroke: teams?.[side]?.color ?? "#fff", "stroke-width": 2, "vector-effect": "non-scaling-stroke" }));
    }
    return box;
  }

  function clock(data) {
    $("[data-clock]").textContent = data.minute;
    $("[data-score]").textContent = `${data.score[0]} – ${data.score[1]}`;
  }

  function shot(data) {
    // Shot coordinates face the shooter's goal (x = 105). Home attacks right, away attacks left.
    const home = data.team === "home";
    const x = home ? data.x : 105 - data.x;
    const y = home ? data.y : 68 - data.y;
    const dot = svg("circle", { cx: x, cy: y, r: 1 + 4 * data.xg, class: `shot ${data.outcome === "goal" ? "goal" : "miss"}`, fill: teams?.[data.team].color ?? "#fff" });
    dot.append(svg("title", {}));
    dot.firstChild.textContent = `${data.minute} ${data.player}: ${data.outcome.replace("_", " ")}, xG ${data.xg.toFixed(2)}`;
    $("[data-shots]").append(dot);
  }

  function output(o) {
    if (o.type === "cue") return cue(o);
    if (o.type === "rejection" || o.type === "spiked") return card(o);
    if (o.type === "degradation") {
      const off = o.level === "detection_only";
      setLevel(o.level, off ? "Detection only" : "On air");
      notice(off ? `${o.minute} The narrator is down. Cues carry the Scout's computed facts until it's back.` : `${o.minute} The narrator is back. Full commentary resumes.`, !off);
    }
  }

  // Why a cue is the viewer's own (personal modes), in the viewer's words.
  const YOURS = { club: "Your club", rival: "Against your club", player: "Your player" };

  function cue(c) {
    const mine = c.for_you?.some((m) => m !== "rival");
    const item = el("li", `cue${c.status === "verified" ? "" : " detection"}${mine ? " is-mine" : ""}`);
    if (mine) item.style.setProperty("--team", teams?.[c.team]?.color ?? "var(--lime)");
    const head = el("header");
    const headline = Object.assign(el("span", "headline", c.headline), { dir: "auto" });
    head.append(el("span", "minute", c.minute), headline);
    for (const m of c.for_you ?? []) head.append(el("span", `yours-tag ${m}`, YOURS[m]));
    // A ref's call: the likely decision as the overlay would draw it, the card itself first.
    if (c.call) {
      if (c.call.card !== "none") head.append(el("span", `ref-card ${c.call.card}`, `${c.call.card === "red" ? "Red" : "Yellow"} card`));
      if (c.call.restart === "penalty") head.append(el("span", "ref-restart", "Penalty"));
    }
    if (c.status !== "verified") head.append(el("span", "tag", "Detection only"));
    else if (c.attempts > 1) head.append(el("span", "tag", `Aired on attempt ${c.attempts}`));
    const evidence = el("div", "evidence");
    for (const id of c.evidence) evidence.append(el("code", "", id));
    // Urdu and Arabic read right to left; each line keeps its verified English a tap away.
    const line = Object.assign(el("p", "", c.text), { lang: c.lang, dir: c.lang === "en" ? "ltr" : "rtl" });
    item.append(head, line);
    if (c.original) {
      const english = el("details", "original");
      english.append(el("summary", "", "In English, as the Critic checked it"), el("p", "", c.original));
      item.append(english);
    }
    if (c.players?.length) item.append(tags(c.players));
    item.append(evidence);
    if (c.receipt) item.append(receipt(c.receipt));
    cues.prepend(item);
    said.set(c.id, item);
    say(c);
    tally.checked += c.receipt?.numbers_checked ?? 0;
    tally.cost += c.receipt?.cost_usd ?? 0;
    drawTally();
  }

  // A line is spoken only by its cue's id: the server reads exactly what aired, never free text.
  function say(c) {
    if (!hear.checked || !voiceSession) return;
    if (queue.length > 1) queue.shift(); // fall no more than two lines behind the broadcast
    queue.push(c.id);
    if (!speaking) speakNext();
  }

  async function speakNext() {
    const id = queue.shift();
    if (!id) { speaking = false; return; }
    speaking = true;
    const item = said.get(id);
    try {
      const response = await fetch(`/api/sessions/${voiceSession}/speak?cue=${encodeURIComponent(id)}`);
      if (!response.ok) throw new Error(`the voice answered ${response.status}`);
      const url = URL.createObjectURL(await response.blob());
      const audio = new Audio(url);
      item?.classList.add("speaking");
      await audio.play();
      await new Promise((done) => { audio.onended = done; audio.onerror = done; });
      URL.revokeObjectURL(url);
    } catch (error) {
      if (String(error).includes("429")) { hear.checked = false; notice("Today's budget for the voice is spent: the lines stay on screen."); }
    } finally {
      item?.classList.remove("speaking");
      speakNext();
    }
  }

  // Who the cue is about (§4.1): number, name, role, and the speed or distance badges a
  // threshold earned. Computed from the cue's own events, never written by a model.
  function tags(players) {
    const row = el("ul", "tags");
    for (const p of players) {
      const tag = el("li", "tag-player");
      tag.style.setProperty("--team", teams?.[p.team]?.color ?? "var(--chalk-dim)");
      tag.append(el("b", "", `${p.number} ${p.name}`), el("span", "", p.role));
      for (const badge of p.badges) tag.append(el("em", "", badge));
      row.append(tag);
    }
    return row;
  }

  function receipt(r) {
    const box = el("details", "receipt");
    box.append(el("summary", "", "Receipt"));
    const rows = r.writer === "none"
      ? [["Written by", "nobody: the Scout's facts"], ["Events cited", r.evidence]]
      : [
          ["Written by", r.writer],
          ["Attempts", r.attempts],
          ["Numbers checked", r.numbers_checked],
          ["Facts recomputed", r.facts_recomputed],
          ["Events cited", r.evidence],
        ];
    rows.push(["Alert to air", `${(r.latency_ms / 1000).toFixed(1)} s`]);
    if (r.model_calls) rows.push(["Tokens", `${r.tokens_in} in, ${r.tokens_out} out`], ["Cost", `$${r.cost_usd.toFixed(5)}`]);
    if (r.handovers) rows.push(["Backup model took over", r.handovers]);
    if (r.translated_by) rows.push(["Translated by", `${r.translated_by}, numbers and names checked`]);
    if (r.translation_refused) rows.push(["Translation", "refused: English aired"]);
    const list = el("dl");
    for (const [label, value] of rows) list.append(el("dt", "", label), el("dd", "", String(value)));
    box.append(list);
    return box;
  }

  function card(o) {
    const item = el("li", "card");
    item.append(el("span", "minute", `${o.minute} · attempt ${o.claim.attempt}`), el("s", "", o.claim.text));
    const reasons = el("ul");
    for (const r of o.reasons) {
      const line = el("li", "", REASONS[r.code] ?? r.code);
      line.append(el("small", "", r.detail)); // the Critic's own words: which number, which event
      reasons.append(line);
    }
    item.append(reasons);
    if (o.type === "spiked") item.append(el("p", "spiked", "Spiked: never aired."));
    cards.prepend(item);
    tally.refused += 1;
    drawTally();
  }

  // The recap: a page built on the server after full time, every written line checked by the Critic.
  function recap(data) {
    const url = URL.createObjectURL(new Blob([data.html], { type: "text/html" }));
    const box = el("li", "notice good recap-ready");
    const name = `${document.title.split(" ")[0].toLowerCase()}-recap-${form.seed.value}.html`;
    box.append(
      el("span", "", "The recap is ready: the result, the goals, the numbers and how it turned, every line checked by the Critic. "),
      Object.assign(el("a", "button-link", "Read the recap"), { href: url, target: "_blank", rel: "noopener" }),
      Object.assign(el("a", "button-link quiet", "Download it"), { href: url, download: name }),
    );
    cues.prepend(box);
  }

  function finish(summary) {
    const s = summary.stats;
    const count = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
    const parts = [`Full time. ${count(s.aired ?? 0, "cue")} aired verified`];
    if (s.aired_detection_only) parts.push(`${s.aired_detection_only} detection-only`);
    if (s.rejected) parts.push(`${count(s.rejected, "claim")} refused and rewritten`);
    if (summary.hidden_by_focus) parts.push(`${count(summary.hidden_by_focus, "other moment")} left out by player focus`);
    notice(`${parts.join(", ")}. Model cost $${summary.cost_usd.toFixed(4)}.`, true);
    setLevel("idle", "Full time");
    stop();
  }

  function notice(text, good = false) {
    const item = el("li", `notice${good ? " good" : ""}`, text);
    cues.prepend(item);
  }

  function setLevel(level, text) {
    const node = $("[data-level]");
    node.dataset.level = level;
    node.textContent = text;
  }

  function drawTally() {
    $("[data-refused]").textContent = tally.refused;
    $("[data-checked]").textContent = tally.checked;
    $("[data-cost]").textContent = `$${tally.cost.toFixed(4)}`;
  }
})();
