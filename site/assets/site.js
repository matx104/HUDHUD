// Fills the page from config.js (product name, links) and draws the evidence chain from
// data/chain.js, which scripts/site_sample.py generates from a real pipeline run.
(() => {
  const site = window.SITE ?? {};
  const chain = window.CHAIN;

  document.querySelectorAll("[data-product-name]").forEach((el) => { el.textContent = site.productName ?? ""; });
  if (site.productName) document.title = `${site.productName}: evidence-checked match commentary`;
  document.querySelectorAll("[data-repo-link]").forEach((el) => { el.href = site.repoUrl ?? "#"; });
  if (site.videoUrl) {
    const video = document.querySelector("[data-video-link]");
    const link = Object.assign(document.createElement("a"), {
      className: "button button-quiet", href: site.videoUrl, textContent: "Watch the 110-second demo",
    });
    video.replaceWith(link);
  }

  if (!chain) return;

  // The Critic's reason codes, in words a viewer understands.
  const REASONS = {
    no_evidence: "Cites no events at all",
    unknown_event: "Cites an event that doesn't exist",
    future_event: "Cites an event that hadn't happened yet",
    stale_event: "Cites events too old to support it",
    assertion_mismatch: "A number in it doesn't match the events",
    insufficient_evidence: "Not enough evidence for the claim",
    no_rule: "No rule yet for checking this kind of claim",
  };

  const board = document.querySelector(".board");
  const body = board.querySelector(".board-body");
  const slot = (name) => board.querySelector(`[data-chain="${name}"]`);
  const el = (tag, cls, text) => Object.assign(document.createElement(tag), { className: cls ?? "", textContent: text ?? "" });

  slot("minute").textContent = chain.minute;
  slot("headline").textContent = chain.headline;

  function render(view) {
    const draft = view === "draft";
    const cited = new Set(draft ? chain.draft.citations : chain.aired.evidence);
    const late = new Map(chain.draft.reasons.filter((r) => r.code === "future_event").map((r) => [r.detail.split(" ")[0], r]));
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

  board.querySelectorAll(".switch button").forEach((button) => {
    button.addEventListener("click", () => {
      board.classList.remove("is-drawing");
      board.querySelectorAll(".switch button").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
      render(button.dataset.view);
      body.classList.remove("is-swapping");
      void body.offsetWidth; // restart the swap animation
      body.classList.add("is-swapping");
    });
  });

  board.classList.add("is-drawing");
  render("aired");
})();
