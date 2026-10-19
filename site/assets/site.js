// Runs the one-file site. Identity and links come from config.js, the claim from data/chain.js
// and the match from data/match.js (both written by scripts/site_sample.py from a real pipeline
// run). Each <section data-page> is a page; the hash router shows one at a time, with
// router.js holding the pure route logic. field.js draws the hero's particles.
(() => {
  const site = window.SITE ?? {};
  const chain = window.CHAIN;
  const match = window.MATCH;
  const name = site.productName ?? "";
  const calm = matchMedia("(prefers-reduced-motion: reduce)");

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const el = (tag, cls, text) => Object.assign(document.createElement(tag), { className: cls ?? "", textContent: text ?? "" });
  const svg = (tag, attrs = {}) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };

  // The Critic's reason codes, in words a viewer understands.
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
  // Events the first draft cited before they had happened.
  const late = new Set(chain?.draft.reasons.filter((r) => r.code === "future_event").map((r) => r.detail.split(" ")[0]));
  const ids = (cls, list) => {
    const p = el("p", cls, "Cites ");
    list.forEach((id, i) => p.append(i ? ", " : "", el("code", late.has(id) ? "late" : "", id)));
    return p;
  };

  identity();
  const hooks = {};
  if (chain) {
    drawBoard();
    drawSteps();
    hooks.problem = exhibit();
  }
  if (match) hooks.data = drawMatch();
  drawSignal();
  if (calm.matches) $$("[data-diagram], [data-signal]").forEach((s) => s.pauseAnimations?.());
  startCountdown();
  // The control room (#/control): the owner's shortcuts into Azure, and the proof for everyone.
  if (window.OPS) drawControlRoom(window.OPS);
  if (window.DOCTOR) drawDoctor(window.DOCTOR);
  if (window.PROOF?.length) drawProof(window.PROOF);
  if (window.REALISM) drawRealism(window.REALISM);
  if (window.FOUNDRY_EVAL) drawFoundryEval(window.FOUNDRY_EVAL);
  placeEmblems();
  startProgress();
  startMenu();
  startReveals();
  startRouter();

  // Every chapter heading gets the crest in its centre circle (the not-found page doesn't).
  function placeEmblems() {
    const emblem = $("#head-emblem");
    for (const head of $$("[data-page]:not([data-page='missing']) .page-head")) {
      head.append(emblem.content.cloneNode(true));
    }
  }

  // The line along the header's lower edge: how far down the current page the reader is.
  function startProgress() {
    const bar = $("[data-progress]");
    let queued = false;
    const draw = () => {
      queued = false;
      const room = document.documentElement.scrollHeight - innerHeight;
      bar.style.setProperty("--read", room > 0 ? Math.min(1, scrollY / room).toFixed(4) : "0");
    };
    const later = () => { if (!queued) { queued = true; requestAnimationFrame(draw); } };
    addEventListener("scroll", later, { passive: true });
    addEventListener("resize", later);
    document.addEventListener("page:change", later);
  }

  function drawControlRoom(ops) {
    const grid = $("[data-ops]");
    for (const group of ops.groups) {
      const box = el("section", "control-group");
      const list = el("ul");
      for (const link of group.links) {
        const a = Object.assign(el("a", "control-link"), { href: link.href, target: "_blank", rel: "noopener" });
        a.append(el("strong", "", link.label), el("span", "", link.detail));
        const item = el("li");
        item.append(a);
        list.append(item);
      }
      box.append(el("h2", "", group.title), list);
      grid.append(box);
    }
    const when = new Date(ops.generated).toLocaleDateString([], { dateStyle: "medium" });
    $("[data-ops-when]").textContent = `Links generated ${when}.`;
  }

  // Foundry's judges, before and after the Narrator's instructions changed: a small table.
  function drawFoundryEval(r) {
    const table = el("table");
    const head = el("tr");
    for (const h of ["Judged for", "Before", "After"]) head.append(el("th", "", h));
    table.append(head);
    for (const metric of Object.keys(r.after)) {
      const row = el("tr");
      row.append(el("td", "", metric[0].toUpperCase() + metric.slice(1)), el("td", "", String(r.before[metric].mean)), el("td", "", String(r.after[metric].mean)));
      table.append(row);
    }
    const note = el("p", "eval-note", `Means out of 5. ${r.writer} wrote, ${r.judge} judged; unseen matches.`);
    $("[data-foundry-eval]").append(table, note);
  }

  // How real is the synthetic football: the verdict in words, then goals a match as paired bars.
  function drawRealism(r) {
    $("[data-realism]").hidden = false;
    $("[data-realism-count]").textContent = r.real.matches.toLocaleString("en-GB");
    $("[data-realism-verdict]").append(...r.verdict.map((line) => el("li", "", line)));
    const bars = $("[data-realism-bars]");
    const top = Math.max(...Object.values(r.real.goals_spread_pct), ...Object.values(r.synthetic.goals_spread_pct));
    const legend = el("p", "realism-legend");
    legend.append(el("span", "key real", "Real"), el("span", "key synthetic", "Synthetic"));
    bars.append(legend);
    for (const [goals, real] of Object.entries(r.real.goals_spread_pct)) {
      const syn = r.synthetic.goals_spread_pct[goals];
      const row = el("div", "realism-row");
      const pair = el("div", "realism-pair");
      for (const [cls, value] of [["real", real], ["synthetic", syn]]) {
        const bar = el("span", `bar ${cls}`);
        bar.style.setProperty("--w", `${(100 * value) / top}%`);
        bar.append(el("b", "", `${value}%`));
        pair.append(bar);
      }
      row.append(el("span", "realism-goals", `${goals} ${goals === "1" ? "goal" : "goals"}`), pair);
      bars.append(row);
    }
  }

  function drawDoctor(doctor) {
    const passed = doctor.checks.filter((c) => c.ok).length;
    const when = new Date(doctor.checked).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    const head = el("p", "doctor-head", `${passed} of ${doctor.checks.length} checks pass, ${when}`);
    const list = el("ul", "doctor-list");
    for (const c of doctor.checks) {
      const item = el("li", c.ok ? (c.warn ? "warn" : "pass") : "fail");
      item.append(el("span", "mark", c.ok ? (c.warn ? "!" : "✔") : "✘"), el("span", "", c.check));
      if (c.detail) item.append(el("small", "", c.detail));
      list.append(item);
    }
    $("[data-doctor]").append(head, list);
  }

  function drawProof(shots) {
    for (const shot of shots) {
      const figure = el("figure", "shot");
      const img = Object.assign(document.createElement("img"), { src: shot.src, alt: shot.alt, loading: "lazy" });
      figure.append(img, el("figcaption", "", shot.caption));
      $("[data-proof-grid]").append(figure);
    }
    $("[data-proof-shots]").hidden = false;
  }

  // The hackathon clock: counts to the submission deadline in config.js, then says so.
  function startCountdown() {
    const end = Date.parse(site.deadline ?? "");
    const clocks = $$("[data-countdown]");
    if (Number.isNaN(end)) return clocks.forEach((c) => { c.hidden = true; });
    const when = $("[data-countdown-when]");
    if (when) {
      const local = new Date(end).toLocaleString(undefined, { weekday: "long", day: "numeric", month: "long", hour: "numeric", minute: "2-digit" });
      when.textContent = `Closes Tuesday 27 October at 11:59 PM Pacific, which is ${local} where you are.`;
    }
    const pad = (n) => String(n).padStart(2, "0");
    let timer = 0;
    const tick = () => {
      const left = Math.max(0, end - Date.now());
      const s = Math.floor(left / 1000);
      for (const clock of clocks) {
        clock.dataset.state = left ? "open" : "closed";
        $("[data-countdown-clock]", clock).textContent = left
          ? `${Math.floor(s / 86400)}d ${pad(Math.floor(s / 3600) % 24)}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`
          : "Top six notified by 10 November";
        $("[data-countdown-label]", clock).textContent = left
          ? clock.classList.contains("countdown-head") ? "Closes in" : "Submissions close in"
          : "Submissions closed";
      }
      if (!left) clearInterval(timer);
    };
    tick();
    timer = setInterval(tick, 1000);
  }

  function identity() {
    $$("[data-product-name]").forEach((n) => { n.textContent = name; });
    $$("[data-product-mark]").forEach((n) => { n.textContent = site.productMark ?? name; });
    $$("[data-repo-link]").forEach((n) => { n.href = site.repoUrl ?? "#"; });
    const share = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(site.siteUrl ?? location.origin)}`;
    $$("[data-share-linkedin]").forEach((n) => { n.href = share; });
    $$("[data-when-repo]").forEach((n) => { n.hidden = (n.dataset.whenRepo === "public") !== Boolean(site.repoPublic); });
    // The live studio leads, when visitors may open it: a match to watch, with the Critic at work.
    if (site.studioUrl && site.studioPublic) {
      $(".page-home .actions").prepend(Object.assign(el("a", "button", "Watch a live match"), { href: site.studioUrl }));
      $(".page-home .actions .button[href='#/problem']")?.classList.add("button-quiet");
      $$("[data-studio-link]").forEach((n) => { n.href = site.studioUrl; n.hidden = false; });
    }
    $$("[data-kit-link]").forEach((n) => { n.href = site.kitUrl ?? "#"; n.hidden = !site.kitUrl; });
    const note = $("[data-video-link]");
    if (site.videoUrl && note) {
      $(".page-home .actions").append(Object.assign(el("a", "button button-quiet", "Watch the 110-second demo"), { href: site.videoUrl }));
      note.remove();
    }
    $("[data-skip]").addEventListener("click", (e) => {
      e.preventDefault(); // a bare #main would read as a route
      $("#main").focus();
    });
  }

  function drawBoard() {
    const board = $(".board");
    const body = $(".board-body", board);
    const slot = (key) => $(`[data-chain="${key}"]`, board);
    $$('[data-chain="minute"]').forEach((n) => { n.textContent = chain.minute; });
    $$('[data-chain="headline"]').forEach((n) => { n.textContent = chain.headline; });

    function render(view) {
      const draft = view === "draft";
      const cited = new Set(draft ? chain.draft.citations : chain.aired.evidence);
      slot("claim").textContent = draft ? chain.draft.text : chain.aired.text;

      const list = slot("events");
      list.replaceChildren();
      let i = 0;
      const events = chain.events.filter((e) => draft || cited.has(e.id));
      events.forEach((e, idx) => {
        const node = el("li", "node");
        node.dataset.state = !cited.has(e.id) ? "uncited" : e.after_claim ? "late" : "cited";
        node.style.setProperty("--i", i++);
        node.append(el("span", "eid", e.id), el("span", "emin", e.minute), el("span", "etext", e.text));
        if (draft && late.has(e.id)) node.append(el("span", "why", "Happened after the claim"));
        list.append(node);
        // The moment the claim was made sits between the last event it could see and the next one.
        const next = events[idx + 1];
        if (!e.after_claim && (!next || next.after_claim)) {
          const now = el("li", "now");
          now.style.setProperty("--i", i++);
          now.append("Claim made here, as of ", el("code", "", chain.as_of));
          list.append(now);
        }
      });

      const verdict = slot("verdict");
      verdict.style.setProperty("--n", i);
      verdict.replaceChildren();
      if (draft) {
        verdict.dataset.verdict = "rejected";
        const why = chain.draft.reasons.map((r) => REASONS[r.code] ?? r.code).join(". ");
        verdict.append(el("strong", "", "Rejected by the Critic"), el("p", "", `${why}. Sent back to the Narrator for a rewrite.`));
      } else {
        verdict.dataset.verdict = "verified";
        const nth = ["first", "second", "third"][chain.aired.attempts - 1] ?? `${chain.aired.attempts}th`;
        const dropped = chain.draft.citations.filter((id) => !cited.has(id));
        const rewrite = dropped.length ? `The rewrite dropped ${dropped.join(", ")}. ` : "";
        verdict.append(el("strong", "", `Verified on the ${nth} attempt`), el("p", "", `${rewrite}Every cited event happened before the claim, and the Critic recomputed each number from them.`));
      }
    }

    $$(".switch button", board).forEach((button) => {
      button.addEventListener("click", () => {
        board.classList.remove("is-drawing");
        $$(".switch button", board).forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
        render(button.dataset.view);
        body.classList.remove("is-swapping");
        void body.offsetWidth; // restart the swap animation
        body.classList.add("is-swapping");
      });
    });
    board.classList.add("is-drawing");
    render("aired");
  }

  // How it works: the front page's claim, step by step.
  function drawSteps() {
    const fill = (key, ...nodes) => $(`[data-example="${key}"]`)?.append(...nodes);
    const quote = (text) => el("blockquote", "", text);
    const asOf = chain.events.find((e) => e.id === chain.as_of);

    const head = el("p", "ex-head");
    head.append(el("span", "minute", chain.minute), el("span", "", chain.headline));
    fill("spot", head, el("p", "ex-note", `Flagged the moment ${chain.as_of} arrived: ${asOf ? asOf.text : "the goal"}.`));

    fill("write", quote(chain.draft.text), ids("ex-ids", chain.draft.citations));

    const attempt = (outcome, title, text) => {
      const box = el("div", "attempt");
      box.dataset.outcome = outcome;
      box.append(el("strong", "", title), el("span", "", text));
      return box;
    };
    const n = chain.aired.attempts;
    const reasons = chain.draft.reasons.map((r) => `${REASONS[r.code] ?? r.code}: ${r.detail}.`).join(" ");
    const dropped = chain.draft.citations.filter((id) => !chain.aired.evidence.includes(id));
    const steps = [attempt("rejected", "Attempt 1: rejected", reasons)];
    if (n > 2) steps.push(attempt("rejected", `Attempts 2 to ${n - 1}: rejected`, "Rewritten and checked again."));
    const fixed = dropped.length ? `The rewrite dropped ${dropped.join(", ")}. ` : "";
    steps.push(attempt("verified", `Attempt ${n}: verified`, `${fixed}Every cited event came before the claim, and every number matched.`));
    fill("check", ...steps);

    fill("air", quote(chain.aired.text), ids("ex-ids", chain.aired.evidence),
      el("p", "ex-note", "This is the analyst cue. Casual fans see the first sentence."));
  }

  // The problem: the rejected draft types itself out, then gets the red card.
  function exhibit() {
    const fig = $(".exhibit");
    const typed = $("[data-typed]", fig);
    $("[data-typed-full]", fig).textContent = chain.draft.text;
    $("[data-exhibit-cites]", fig).replaceWith(ids("exhibit-cites", chain.draft.citations));
    $("[data-exhibit-verdict]", fig).textContent = `Rejected. ${chain.draft.reasons.map((r) => r.detail).join(". ")}.`;
    let timers = [];
    return function play() {
      timers.forEach(clearTimeout);
      timers = [];
      fig.classList.remove("is-cited", "is-done");
      const text = chain.draft.text;
      if (calm.matches) {
        typed.textContent = text;
        fig.classList.add("is-cited", "is-done");
        return;
      }
      typed.textContent = "";
      typed.classList.add("is-typing");
      [...text].forEach((_, i) => timers.push(setTimeout(() => { typed.textContent = text.slice(0, i + 1); }, 400 + i * 26)));
      const end = 400 + text.length * 26;
      timers.push(setTimeout(() => typed.classList.remove("is-typing"), end + 200));
      timers.push(setTimeout(() => fig.classList.add("is-cited"), end + 400));
      timers.push(setTimeout(() => fig.classList.add("is-done"), end + 1500));
    };
  }

  // Data: the match's totals and every shot, on a pitch drawn to scale (105 x 68 m).
  function drawMatch() {
    const { home, away } = match;
    const stats = $("[data-stats]");
    for (const [label, value] of [["Events", match.events], ["Passes", match.passes], ["Shots", home.shots + away.shots], ["Goals", home.goals + away.goals]]) {
      const cell = el("div");
      cell.append(el("dt", "", label), el("dd", "", value.toLocaleString("en")));
      stats.append(cell);
    }
    const head = $("[data-shotmap-head]");
    head.append(el("span", "side-home", `${home.name} ${home.goals}`), el("span", "side-away", `${away.goals} ${away.name}`));

    const map = $("[data-shotmap]");
    const line = (attrs) => map.append(svg("rect", { class: "pitch-line", ...attrs }));
    map.append(svg("rect", { class: "pitch-grass", x: 0, y: 0, width: 105, height: 68 }));
    line({ x: 0, y: 0, width: 105, height: 68 });
    map.append(svg("path", { class: "pitch-line", d: "M52.5 0V68" }));
    map.append(svg("circle", { class: "pitch-line", cx: 52.5, cy: 34, r: 9.15 }));
    for (const x of [0, 88.5]) line({ x, y: 13.84, width: 16.5, height: 40.32 });
    for (const x of [0, 99.5]) line({ x, y: 24.84, width: 5.5, height: 18.32 });
    for (const x of [-1.6, 105]) line({ x, y: 30.34, width: 1.6, height: 7.32 });

    // Shots arrive in the shooter's attacking frame (goal at x = 105). The home side attacks
    // right on this map, so the away side's shots are turned round to face the left goal.
    match.shots.forEach((shot, i) => {
      const homeSide = shot.team === "home";
      const cx = homeSide ? shot.x : 105 - shot.x;
      const cy = homeSide ? shot.y : 68 - shot.y;
      const r = 0.9 + shot.xg * 3.2;
      const goal = shot.outcome === "goal";
      const dot = svg("circle", { class: `shot shot-${shot.team}${goal ? " is-goal" : ""}`, cx, cy, r, style: `--i:${i}` });
      dot.append(svg("title"));
      dot.firstChild.textContent = `${shot.minute} ${shot.player}, xG ${shot.xg.toFixed(2)}, ${shot.outcome.replace("_", " ")}`;
      if (goal) map.append(svg("circle", { class: "goal-ring", cx, cy, r: r + 1.3, style: `--i:${i}` }));
      map.append(dot);
    });
    $("[data-shotmap-caption]").textContent = `Every shot in synthetic match seed ${match.seed}. ${home.name} (green) attack to the right, ${away.name} (white) to the left. Bigger circles are better chances; filled circles are goals.`;

    const fig = $(".shotmap");
    return () => {
      fig.classList.remove("is-live");
      void fig.offsetWidth;
      fig.classList.add("is-live");
    };
  }

  // Recovery: the cue stream as a signal that changes colour through a failure but never breaks.
  function drawSignal() {
    const box = $("[data-signal]");
    if (!box) return;
    const base = 78;
    const wave = (x0, x1, amp, step) => {
      let d = `M${x0} ${base}`;
      for (let x = x0; x + step <= x1; x += step) {
        d += ` L${x + step * 0.35} ${base} L${x + step * 0.45} ${base - amp} L${x + step * 0.55} ${base + amp * 0.6} L${x + step * 0.65} ${base} L${x + step} ${base}`;
      }
      return `${d} L${x1} ${base}`;
    };
    const parts = [
      { d: wave(0, 380, 34, 50), cls: "sig-full", label: "Full service", x: 0 },
      { d: wave(380, 700, 14, 40), cls: "sig-degraded", label: "Detection only", x: 392 },
      { d: wave(700, 1000, 34, 50), cls: "sig-full", label: "Recovered", x: 712 },
    ];
    for (const part of parts) {
      box.append(svg("path", { class: `sig ${part.cls}`, d: part.d }));
      const label = svg("text", { class: "sig-label", x: part.x, y: 145 });
      label.textContent = part.label;
      box.append(label);
    }
    box.append(svg("path", { class: "sig-fail", d: "M380 18V128" }));
    const fail = svg("text", { class: "sig-fail-label", x: 390, y: 22 });
    fail.textContent = "Narrator down: retry, then fall back";
    box.append(fail);
    const back = svg("text", { class: "sig-label", x: 712, y: 22 });
    back.textContent = "Back, and announced on air";
    box.append(back);
    const head = svg("circle", { class: "sig-head", r: 5 });
    head.append(svg("animateMotion", { dur: "7s", repeatCount: "indefinite", path: parts.map((p) => p.d).join(" ") }));
    box.append(head);
  }

  function startMenu() {
    const button = $(".menu-button");
    const panel = $("#chapters");
    const label = $("[data-menu-label]", button);
    const set = (open) => {
      panel.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      label.textContent = open ? "Close" : "Chapters";
      document.body.classList.toggle("menu-open", open);
    };
    button.addEventListener("click", () => {
      set(panel.hidden);
      if (!panel.hidden) $("a", panel)?.focus();
    });
    panel.addEventListener("click", (e) => { if (e.target.closest("a")) set(false); });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !panel.hidden) {
        set(false);
        button.focus();
      }
    });
    window.addEventListener("hashchange", () => set(false));
  }

  function startReveals() {
    const items = $$("[data-reveal]");
    if (!("IntersectionObserver" in window)) return items.forEach((n) => n.classList.add("is-revealed"));
    const seen = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-revealed");
        seen.unobserve(entry.target);
      }
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.06 });
    for (const item of items) {
      // Siblings that arrive together come in one after another.
      const order = [...item.parentElement.children].filter((c) => c.hasAttribute("data-reveal")).indexOf(item);
      item.style.transitionDelay = `${Math.min(order, 6) * 70}ms`;
      seen.observe(item);
    }
  }

  function startRouter() {
    const sections = $$("[data-page]");
    const missing = $('[data-page="missing"]');
    // Aside pages (the control room) can be visited but stay out of the chapters and the pager.
    const story = sections.filter((s) => s !== missing && !("aside" in s.dataset));
    const keys = sections.filter((s) => s !== missing).map((s) => s.dataset.page).filter(Boolean);
    const pager = $("[data-pager]");
    const sting = $(".sting");
    let current = null;
    let pending = 0;

    const chapter = (page, i) => {
      const item = el("li");
      const link = Object.assign(el("a"), { href: `#/${page.dataset.page}` });
      link.append(el("span", "no", String(i).padStart(2, "0")), el("strong", "", page.dataset.title), el("span", "", page.dataset.summary));
      item.append(link);
      return item;
    };
    $("[data-chapter-menu]").append(...story.map(chapter));
    $("[data-chapter-index]").append(...story.slice(1).map((page, i) => chapter(page, i + 1)));

    const pagerLink = (page, cls, label) => {
      const link = Object.assign(el("a", cls), { href: `#/${page.dataset.page}` });
      link.append(el("span", "", label), el("strong", "", page.dataset.title));
      return link;
    };

    function swap(target, first) {
      current?.classList.remove("is-current", "is-entering");
      target.classList.add("is-current");
      if (!first) target.classList.add("is-entering");
      current = target;

      const key = target.dataset.page;
      document.title = key === "" ? `${name}: AI match commentary that proves every call` : `${target.dataset.title}: ${name}`;
      $$('a[href^="#/"]').forEach((a) => {
        if (target !== missing && a.getAttribute("href") === `#/${key}`) a.setAttribute("aria-current", "page");
        else a.removeAttribute("aria-current");
      });

      pager.replaceChildren();
      const i = story.indexOf(target);
      if (i > 0) pager.append(pagerLink(story[i - 1], "prev", "Previous"));
      if (i >= 0 && i < story.length - 1) pager.append(pagerLink(story[i + 1], "next", "Next"));

      if (!first) {
        window.scrollTo(0, 0);
        $("h1", target)?.focus({ preventScroll: true });
      }
      hooks[key]?.();
      document.dispatchEvent(new CustomEvent("page:change", { detail: { page: key } }));
    }

    function show(first) {
      const route = resolveRoute(location.hash, keys);
      if (route.redirect) history.replaceState(null, "", route.redirect);
      const target = route.page === null ? missing : sections.find((s) => s.dataset.page === route.page);
      if (route.page === null) $("[data-missing-path]").textContent = `#/${route.path}`;
      if (target === current) return;
      clearTimeout(pending);
      if (first || calm.matches) return swap(target, first);
      // The broadcast sting covers the screen from 40% to 60% of its 800 ms; the page changes then.
      sting.classList.remove("is-playing");
      void sting.offsetWidth;
      sting.classList.add("is-playing");
      pending = setTimeout(() => swap(target, false), 400);
    }

    window.addEventListener("hashchange", () => show(false));
    show(true);
  }
})();
