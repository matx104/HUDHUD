// The studio page: opens one match as Server-Sent Events and renders what the court does with it.
// The server sends hello (teams, session), clock (minute, score), shot, output (cue, rejection,
// spiked, degradation) and end. Nothing here computes a fact: every number on screen came from
// the server, and every line came through the Critic.
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
  let source = null;
  let session = null;
  let teams = null;
  let tally = { refused: 0, checked: 0, cost: 0 };

  fetch("/api/config")
    .then((r) => r.json())
    .then((config) => {
      document.querySelectorAll("[data-product]").forEach((n) => (n.textContent = config.product));
      document.title = `${config.product} studio`;
      for (const m of config.matches) {
        const option = el("option", "", `${m.home.name} v ${m.away.name}`);
        option.value = m.seed;
        $("[data-matches]").append(option);
      }
      if (!config.models) form.narration.value = "template";
    });

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
      stress: $("[data-stress]").checked ? "0.25" : "0",
    });
    source = new EventSource(`/api/stream?${params}`);
    source.addEventListener("hello", (e) => hello(JSON.parse(e.data)));
    source.addEventListener("clock", (e) => clock(JSON.parse(e.data)));
    source.addEventListener("shot", (e) => shot(JSON.parse(e.data)));
    source.addEventListener("output", (e) => output(JSON.parse(e.data)));
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
    teams = { home: data.home, away: data.away };
    for (const side of ["home", "away"]) {
      const node = $(`[data-${side}]`);
      node.querySelector("b").textContent = data[side].short;
      node.title = data[side].name;
      node.style.setProperty("--team", data[side].color);
    }
    const who = data.narration === "foundry" ? "AI models on Microsoft Foundry write the commentary" : "The offline template writes the commentary";
    notice(`${data.home.name} v ${data.away.name}, ${data.competition}. ${who}.`, true);
    for (const text of data.notices) notice(text);
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

  function cue(c) {
    const item = el("li", `cue${c.status === "verified" ? "" : " detection"}`);
    const head = el("header");
    head.append(el("span", "minute", c.minute), el("span", "headline", c.headline));
    if (c.status !== "verified") head.append(el("span", "tag", "Detection only"));
    else if (c.attempts > 1) head.append(el("span", "tag", `Aired on attempt ${c.attempts}`));
    const evidence = el("div", "evidence");
    for (const id of c.evidence) evidence.append(el("code", "", id));
    item.append(head, el("p", "", c.text));
    if (c.players?.length) item.append(tags(c.players));
    item.append(evidence);
    if (c.receipt) item.append(receipt(c.receipt));
    cues.prepend(item);
    tally.checked += c.receipt?.numbers_checked ?? 0;
    tally.cost += c.receipt?.cost_usd ?? 0;
    drawTally();
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

  function finish(summary) {
    const s = summary.stats;
    const parts = [`Full time. ${s.aired ?? 0} cues aired verified`];
    if (s.aired_detection_only) parts.push(`${s.aired_detection_only} detection-only`);
    if (s.rejected) parts.push(`${s.rejected} claims refused and rewritten`);
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
