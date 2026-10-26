// Ask the match, on its own page: open a match (the whole of it, played in a few seconds, or live),
// then ask it anything, typed or out loud. The page computes nothing: every number in an answer was
// counted by code from the match's events and checked by the Critic (court.ask), and every answer
// is sealed into the match's ledger (court.ledger), which this page can check by itself.
(() => {
  const $ = (sel) => document.querySelector(sel);
  const el = (tag, cls, text) => Object.assign(document.createElement(tag), { className: cls ?? "", textContent: text ?? "" });
  const svg = (tag, attrs) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };
  const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

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
  const VERDICT = {
    verified: (a) => `Checked by the Critic: ${plural(a.receipt.numbers_checked, "number")} matched the events${a.receipt.attempts > 1 ? `, on attempt ${a.receipt.attempts}` : ""}`,
    cannot: () => "The events can't answer this: fixed words, not a model's",
    refused: (a) => `No answer could be proven: the Critic refused ${plural(a.refused.length, "draft")}`,
  };
  // A tick, for a checked answer.
  const tick = () => {
    const mark = svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" });
    mark.append(svg("path", { d: "M5 12.5l4.5 4.5L19 7.5", fill: "none", stroke: "currentColor", "stroke-width": "2.4", "stroke-linecap": "round", "stroke-linejoin": "round" }));
    return mark;
  };

  const pick = $("[data-pick]");
  const askForm = $("[data-ask]");
  const thread = $("[data-thread]");
  const mic = $("[data-mic]");
  let matches = [];
  let voice = false;
  let source = null;
  let session = null;
  let chain = [];
  let pending = null; // a question from the address, asked once the match is ready

  fetch("/api/config")
    .then((r) => r.json())
    .then((config) => {
      document.querySelectorAll("[data-product]").forEach((n) => (n.textContent = config.product));
      document.title = `Ask the match: ${config.product}`;
      matches = config.matches;
      for (const m of matches) $("[data-matches]").append(Object.assign(el("option", "", `${m.home.name} v ${m.away.name}`), { value: m.seed }));
      if (!config.models) pick.narration.value = "template";
      voice = config.voice && window.Voice.available();
      // ?seed=21&when=full&narration=foundry&lang=ur&q=Who%20scored%3F&autostart=1
      const params = new URLSearchParams(location.search);
      for (const name of ["seed", "narration", "lang"]) {
        const value = params.get(name);
        if (value !== null && [...pick.elements[name].options].some((o) => o.value === value)) pick.elements[name].value = value;
      }
      if (params.get("when") === "live") pick.querySelector("[value=live]").checked = true;
      pending = params.get("q");
      if (params.get("autostart") === "1") open();
    });

  pick.addEventListener("submit", (event) => {
    event.preventDefault();
    open();
  });

  // ---------- the match ----------
  function open() {
    source?.close();
    const full = pick.when.value === "full";
    session = null;
    chain = [];
    thread.replaceChildren();
    $("[data-empty]").hidden = false;
    $("[data-shots]").replaceChildren();
    $("[data-card]").hidden = false;
    $("[data-blocks]").textContent = "no blocks yet";
    $("[data-seal]").textContent = "none yet";
    $("[data-verify-ledger]").hidden = true;
    $("[data-ledger-result]").textContent = "";
    $("[data-left]").textContent = "";
    ready(false, full ? "The match is being played: ask once it reaches full time" : "Waiting for kick-off");
    $("[data-status]").textContent = full ? "Playing the whole match" : "Live";
    const params = new URLSearchParams({
      seed: pick.seed.value,
      narration: pick.narration.value,
      lang: pick.lang.value,
      mode: "analyst",
      stress: "0",
      speed: full ? "0" : "30",
      start: full ? "90" : "60",
    });
    source = new EventSource(`/api/stream?${params}`);
    const listen = (kind, handler) => source.addEventListener(kind, (e) => handler(JSON.parse(e.data)));
    listen("hello", (d) => {
      session = d.session;
      for (const side of ["home", "away"]) {
        const node = $(`.score [data-side=${side}]`);
        node.querySelector("b").textContent = d[side].short;
        node.title = d[side].name;
        node.style.setProperty("--team", d[side].color);
      }
      for (const text of d.notices) note(text);
    });
    listen("clock", (d) => {
      $("[data-clock]").textContent = d.minute;
      $("[data-score]").textContent = `${d.score[0]} – ${d.score[1]}`;
      if (!full && session && askForm.question.disabled) {
        ready(true, "Ask about the match so far");
        suggest();
      }
    });
    listen("shot", shot);
    listen("block", (b) => {
      chain.push(b);
      $("[data-blocks]").textContent = `${plural(chain.length, "block")}, the latest ${b.minute}`;
      $("[data-seal]").textContent = b.hash;
    });
    listen("end", (summary) => {
      $("[data-status]").textContent = "Full time: ask about the whole match";
      $("[data-clock]").textContent = "FT";
      $("[data-verify-ledger]").hidden = false;
      if (summary.ledger) $("[data-blocks]").textContent = `sealed at full time: ${plural(summary.ledger.blocks, "block")}, ${plural(summary.ledger.entries, "entry", "entries")}`;
      source.close();
      ready(true, "Ask anything about the whole match");
      suggest();
      if (pending) {
        const q = pending;
        pending = null;
        ask(q);
      }
    });
    source.addEventListener("error", (e) => {
      if (e.data) note(`Sorry: ${JSON.parse(e.data).detail}.`);
      source.close();
    });
  }

  function ready(on, placeholder) {
    askForm.question.disabled = !on;
    $("[data-ask-go]").disabled = !on;
    mic.hidden = !voice;
    mic.disabled = !on;
    askForm.question.placeholder = placeholder;
  }

  function shot(d) {
    // Shot coordinates face the shooter's goal (x = 105): home attacks right, away left.
    const home = d.team === "home";
    const dot = svg("circle", { cx: home ? d.x : 105 - d.x, cy: home ? d.y : 68 - d.y, r: 1 + 4 * d.xg, class: `shot ${d.outcome === "goal" ? "goal" : "miss"}`, fill: $(`.score [data-side=${d.team}]`).style.getPropertyValue("--team") || "#fff" });
    dot.dataset.id = d.id;
    dot.append(svg("title", {}));
    dot.firstChild.textContent = `${d.minute} ${d.player}: ${d.outcome.replace("_", " ")}, xG ${d.xg.toFixed(2)}`;
    $("[data-shots]").append(dot);
  }

  async function suggest() {
    if (!session) return;
    const response = await fetch(`/api/sessions/${session}/suggest`).catch(() => null);
    if (!response?.ok) return;
    const { questions } = await response.json();
    $("[data-chips]").replaceChildren(...questions.map((q) => {
      const chip = Object.assign(el("button", "", q), { type: "button" });
      chip.addEventListener("click", () => ask(q));
      return chip;
    }));
  }

  // ---------- asking ----------
  askForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = askForm.question.value.trim();
    if (question) ask(question);
  });

  async function ask(question, aloud = false) {
    if (!session || askForm.question.disabled) return;
    $("[data-empty]").hidden = true;
    const asked = el("li", "asked");
    asked.append(el("small", "", "You asked"), document.createTextNode(question));
    const thinking = el("li", "reply thinking");
    thinking.append(el("p", "verdict", "Counting from the events, then the Critic checks"));
    thread.append(asked, thinking);
    thinking.scrollIntoView({ block: "end", behavior: "smooth" });
    askForm.question.value = "";
    ready(false, "Checking");
    try {
      const response = await fetch(`/api/sessions/${session}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const a = await response.json().catch(() => ({}));
      if (!response.ok) {
        thinking.replaceWith(Object.assign(el("li", "reply cannot"), { textContent: response.status === 422 ? "Ask in 200 characters or fewer." : `${a.detail ?? "That question couldn't be asked"}.` }));
        return;
      }
      const item = reply(a);
      thinking.replaceWith(item);
      item.scrollIntoView({ block: "end", behavior: "smooth" });
      $("[data-left]").textContent = `${plural(a.left, "question")} left for this match.`;
      if (aloud) speak(a);
      suggest();
    } catch {
      thinking.replaceWith(Object.assign(el("li", "reply cannot"), { textContent: "The studio didn't answer. Try again." }));
    } finally {
      ready(true, "Ask a follow-up, or anything else");
      askForm.question.focus();
    }
  }

  function reply(a) {
    const item = el("li", `reply ${a.status}`);
    const verdict = el("p", "verdict");
    if (a.status === "verified") verdict.append(tick());
    verdict.append(document.createTextNode(VERDICT[a.status](a)));
    const said = Object.assign(el("p", "said", a.text), { lang: a.lang, dir: a.lang === "en" ? "ltr" : "rtl" });
    item.append(verdict, said);
    if (a.original) {
      const english = el("details");
      english.append(el("summary", "", "In English, as the Critic checked it"), el("p", "", a.original));
      item.append(english);
    }
    // What the Scout's tools counted: the facts the answer stands on, each with its events.
    if (a.facts.length) {
      const facts = el("details");
      facts.append(el("summary", "", `What code counted (${plural(a.facts.length, "fact")})`));
      const list = el("ol");
      for (const f of a.facts) {
        const row = el("li", "", f.says);
        const evidence = el("div", "evidence");
        for (const id of f.evidence.slice(-8)) evidence.append(el("code", "", id));
        if (f.evidence.length > 8) evidence.append(el("code", "", `+${f.evidence.length - 8}`));
        row.append(evidence);
        list.append(row);
      }
      facts.append(list);
      item.append(facts);
    }
    if (a.refused.length) {
      const struck = el("ul", "struck");
      for (const r of a.refused) {
        const row = el("li");
        row.append(el("s", "", r.text));
        for (const reason of r.reasons) row.append(el("small", "", `${REASONS[reason.code] ?? reason.code}: ${reason.detail}`));
        struck.append(row);
      }
      item.append(struck);
    }
    // The shots it cites, lit on the map.
    for (const dot of document.querySelectorAll(".pitch .shot")) dot.classList.toggle("cited", a.evidence.includes(dot.dataset.id));
    // Where it is sealed, and a check anyone can run here.
    const proof = el("div", "proof");
    const block = a.ledger?.block;
    proof.append(el("span", "", block === null || block === undefined ? "Joins the ledger's next block" : `Sealed in block ${block}`));
    const check = Object.assign(el("button", "quiet", "Verify this answer"), { type: "button" });
    const result = el("span", "proof-result");
    check.addEventListener("click", () => verifyAnswer(a, result));
    proof.append(check, result);
    item.append(proof);
    return item;
  }

  // The answer's proof, checked in this browser: its text is its leaf, the Merkle path reaches its
  // block's root, and each block after it links on to the seal.
  async function verifyAnswer(a, result) {
    const response = await fetch(`/api/sessions/${session}/ledger/proof?item=${encodeURIComponent(`answer:${a.id}`)}`);
    if (response.status === 404) {
      result.className = "proof-result";
      result.textContent = "It joins the ledger when this minute's block is sealed: try again in a moment.";
      return;
    }
    const proof = await response.json();
    const failed = await window.Ledger.verifyProof(proof);
    const shown = JSON.parse(proof.text);
    const same = shown.text === a.text && shown.question === a.question;
    result.className = `proof-result ${failed || !same ? "bad" : "good"}`;
    result.textContent = failed
      ? `Not verified: ${failed}.`
      : !same
        ? "Not verified: the ledger holds different words from the answer on screen."
        : `Verified in this browser: the answer hashes to its leaf, ${proof.path.length ? `a Merkle path of ${plural(proof.path.length, "step")} reaches block ${proof.block.height}'s root` : `which is block ${proof.block.height}'s root, as its only entry`}, and ${proof.after.length ? `${plural(proof.after.length, "later block")} link on to the seal` : "that block is the seal"}.`;
  }

  $("[data-verify-ledger]").addEventListener("click", async () => {
    const result = $("[data-ledger-result]");
    const ledger = await (await fetch(`/api/sessions/${session}/ledger`)).json();
    const outcome = await window.Ledger.verifyLedger(ledger);
    const live = chain.at(-1)?.hash;
    const fine = outcome.ok && ledger.blocks.some((b) => b.hash === live);
    result.className = `seal-result ${fine ? "good" : "bad"}`;
    result.textContent = fine
      ? `Verified here: ${plural(outcome.blocks, "block")}, ${plural(outcome.entries, "entry", "entries")}, every hash recomputed, and the seal sealed live is in the chain.`
      : `Not verified: ${outcome.problems[0] ?? "the seal sealed live isn't in the chain"}.`;
  });

  function note(text) {
    $("[data-empty]").hidden = true;
    thread.append(Object.assign(el("li", "reply cannot"), { textContent: text }));
  }

  // ---------- out loud ----------
  let recording = null;
  mic.addEventListener("click", async () => {
    if (recording) return stopListening();
    try {
      recording = { take: await window.Voice.start(), timer: setTimeout(stopListening, 12000) };
      mic.setAttribute("aria-pressed", "true");
      $("[data-mic-label]").textContent = "Listening. Tap to stop";
    } catch {
      $("[data-left]").textContent = "The microphone wasn't allowed. Type the question instead.";
    }
  });

  async function stopListening() {
    const r = recording;
    recording = null;
    if (!r) return;
    clearTimeout(r.timer);
    const body = await r.take.finish();
    mic.setAttribute("aria-pressed", "false");
    $("[data-mic-label]").textContent = "Hearing it";
    try {
      const response = await fetch(`/api/sessions/${session}/listen`, { method: "POST", headers: { "Content-Type": "audio/wav" }, body });
      const heard = await response.json().catch(() => ({}));
      if (!response.ok) $("[data-left]").textContent = `${heard.detail ?? "That couldn't be heard"}.`;
      else await ask(heard.text, true);
    } finally {
      $("[data-mic-label]").textContent = "Say it";
    }
  }

  // Asked out loud, answered out loud: the voice reads exactly the answer, by its id.
  async function speak(a) {
    const response = await fetch(`/api/sessions/${session}/speak?cue=${encodeURIComponent(a.id)}`).catch(() => null);
    if (!response?.ok) return;
    const url = URL.createObjectURL(await response.blob());
    const audio = new Audio(url);
    audio.onended = () => URL.revokeObjectURL(url);
    audio.play().catch(() => URL.revokeObjectURL(url));
  }
})();
