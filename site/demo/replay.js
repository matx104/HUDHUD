// The studio, replayed: the showcase site can't reach the private studio, so this stands in for it,
// in front of the studio's own pages (scripts/site_demo.py copies them here). It plays one match
// recorded from the deployed studio to the page as the page would have received it, and answers
// the questions recorded after full time with their real answers and proofs. Every hash the pages
// check (the ledger, each answer's proof) is checked in the visitor's browser, against the
// recorded files, by the studio's own code.
(function () {
  const loaded = fetch("recording.json").then((r) => r.json());
  const realFetch = window.fetch.bind(window);
  const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  const plain = (q) => q.toLowerCase().replace(/[^\p{L}\p{N} ]/gu, "").replace(/\s+/g, " ").trim();
  const ONLY_RECORDED = "This is a recorded match, so it can only answer the questions recorded with it: try one of those offered. The live studio answers anything.";

  // A stream, from the recording: at the pace it arrived, or all at once for a match "played to
  // full time in a few seconds" (speed=0).
  class Replay {
    constructor(url) {
      this.listeners = {};
      this.readyState = 0;
      this.instant = new URL(url, location.href).searchParams.get("speed") === "0";
      loaded.then((recording) => this.play(recording.events));
    }
    addEventListener(kind, handler) {
      (this.listeners[kind] ??= []).push(handler);
    }
    close() {
      this.readyState = Replay.CLOSED;
      clearTimeout(this.timer);
    }
    play(events) {
      if (this.readyState === Replay.CLOSED) return;
      this.readyState = 1;
      const started = performance.now();
      let i = 0;
      const step = () => {
        const now = performance.now() - started;
        while (i < events.length && (this.instant || events[i][0] <= now) && this.readyState !== Replay.CLOSED) {
          const [, kind, data] = events[i++];
          for (const handler of this.listeners[kind] ?? []) handler({ data: JSON.stringify(data) });
        }
        if (i < events.length && this.readyState !== Replay.CLOSED) this.timer = setTimeout(step, this.instant ? 0 : 40);
      };
      step();
    }
  }
  Replay.CLOSED = 2;
  window.EventSource = Replay;

  window.fetch = async (input, init = {}) => {
    const url = new URL(String(input), location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith("/api/")) return realFetch(input, init);
    const recording = await loaded;
    const path = url.pathname;
    if (path === "/api/config") {
      const seed = recording.events[0][2].seed;
      return json({ ...recording.config, matches: recording.config.matches.filter((m) => m.seed === seed) });
    }
    if (path.endsWith("/ask")) {
      const asked = plain(JSON.parse(init.body ?? "{}").question ?? "");
      const answer = recording.answers.find((a) => plain(a.question) === asked);
      return answer ? json(answer) : json({ detail: ONLY_RECORDED }, 409);
    }
    if (path.endsWith("/suggest")) return json({ questions: recording.answers.map((a) => a.question) });
    if (path.endsWith("/ledger/proof")) {
      const item = url.searchParams.get("item");
      const answer = recording.answers.find((a) => `answer:${a.id}` === item);
      return answer ? json(answer.proof) : json({ detail: "no such entry in this recording" }, 404);
    }
    if (path.endsWith("/ledger")) return realFetch("ledger.json");
    return json({ detail: "the recorded match can't do that: the live studio can" }, 409);
  };
})();
