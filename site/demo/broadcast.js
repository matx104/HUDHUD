// The program feed, from the recording: every "output" event is a cue in the studio's
// own contract, and this page draws it the way a broadcast graphics system would —
// nothing hand-placed, everything from the JSON. The panel beside the frame shows the
// contract live, cue by cue. Play runs the take at its recorded pace; Next line jumps
// to the following cue for an impatient director.
(() => {
  const $ = (id) => document.getElementById(id);
  const params = new URLSearchParams(location.search);
  const autostart = params.get("autostart") === "1";

  let events = [];
  let i = 0;
  let playing = false;
  let startedAt = 0;   // performance.now() when the take resumed
  let baseOffset = 0;  // event time the take resumed from
  let timer = 0;

  fetch("recording.json")
    .then((r) => r.json())
    .then((recording) => {
      events = recording.events;
      hello(events.find(([, kind]) => kind === "hello")?.[2]);
      if (autostart) play();
    });

  function hello(data) {
    if (!data) return;
    $("homeShort").textContent = data.home.short;
    $("awayShort").textContent = data.away.short;
    document.querySelector(".meet").textContent =
      `${data.competition} · ${data.home.name} v ${data.away.name} · seed ${data.seed}, recorded from the live studio`;
  }

  function play() {
    if (playing || i >= events.length) return;
    playing = true;
    $("play").setAttribute("aria-pressed", "true");
    $("play").textContent = "⏸ Pause";
    startedAt = performance.now();
    tick();
  }

  function pause() {
    playing = false;
    clearTimeout(timer);
    $("play").setAttribute("aria-pressed", "false");
    $("play").textContent = "▶ Play";
  }

  function tick() {
    if (!playing) return;
    const now = baseOffset + performance.now() - startedAt;
    while (i < events.length && events[i][0] <= now) handle(events[i++]);
    if (i >= events.length) return pause();
    timer = setTimeout(tick, 60);
  }

  function seekTo(offset) {
    // Draw the state as if the take had played to this point, then hold.
    clearTimeout(timer);
    i = 0;
    const held = [];
    while (i < events.length && events[i][0] < offset) {
      const event = events[i++];
      if (event[1] === "output") held.push(event);
      else if (event[1] === "clock") minute(event[2]);
    }
    if (held.length) cue(held.at(-1)[2]);
    baseOffset = offset;
    startedAt = performance.now();
    if (playing) tick();
  }

  function nextLine() {
    const from = playing ? baseOffset + performance.now() - startedAt : baseOffset;
    const upcoming = events.find(([at, kind]) => kind === "output" && at > from + 1);
    seekTo(upcoming ? upcoming[0] + 1 : events.at(-1)[0]);
  }

  function handle([, kind, data]) {
    if (kind === "clock") minute(data);
    else if (kind === "output" && data.type === "cue") cue(data);
    else if (kind === "end") pause();
  }

  function minute(data) {
    const m = data?.minute;
    if (m) $("minute").textContent = m;
    timecode(data);
  }

  function timecode() {
    const t = baseOffset + (playing ? performance.now() - startedAt : 0);
    const s = Math.floor(t / 1000);
    const f = Math.floor((t % 1000) / 40);
    $("tc").textContent = [Math.floor(s / 60), s % 60].map((n) => String(n).padStart(2, "0")).join(":") + `:${String(f).padStart(2, "0")}`;
  }
  setInterval(timecode, 250);

  function cue(c) {
    $("idle").hidden = true;
    const lower = $("lower");
    lower.hidden = true;
    void lower.offsetWidth; // restart the strap animation on every cue
    lower.hidden = false;

    $("strap").textContent = c.headline;
    $("line").textContent = c.text;
    $("cites").replaceChildren();
    $("cites").append("evidence  ");
    (c.evidence ?? []).forEach((id, n) => {
      if (n) $("cites").append("  ");
      $("cites").append(Object.assign(document.createElement("code"), { textContent: id }));
    });
    const r = c.receipt ?? {};
    $("meta").textContent =
      `✓ ${c.status} · attempt ${c.attempts} · ${r.writer ?? "code"} · ${(r.latency_ms / 1000).toFixed(1)}s · $${(r.cost_usd ?? 0).toFixed(4)} · ttl ${Math.round(c.ttl_s)}s`;

    const players = $("players");
    players.replaceChildren();
    for (const p of c.players ?? []) {
      const tag = document.createElement("span");
      tag.innerHTML = `<b>#${p.number} ${p.name}</b> · ${p.role}`;
      players.append(tag);
    }
    if (c.call) {
      const call = document.createElement("span");
      call.className = "card";
      call.textContent = `${c.call.card ?? ""} ${c.call.restart}`.trim() + ` · law 12 · ${c.call.profile}`;
      players.append(call);
    }

    const score = c.headline.match(/(\d+)\s*[–-]\s*(\d+)/);
    if (score) $("score").textContent = `${score[1]}–${score[2]}`;

    $("json").textContent = JSON.stringify(c, null, 2);
  }

  $("play").addEventListener("click", () => (playing ? pause() : play()));
  $("next").addEventListener("click", nextLine);
  $("reset").addEventListener("click", () => {
    pause();
    i = 0;
    baseOffset = 0;
    startedAt = performance.now();
    $("lower").hidden = true;
    $("idle").hidden = false;
    $("json").textContent = "waiting for the first line…";
    $("minute").textContent = "50'";
    $("score").textContent = "0–0";
  });
})();
