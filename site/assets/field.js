// The hero's event field. Particles drift across a faint pitch like play; every second or two a
// few of them link into an evidence chain that turns gold when it is verified, or red when it
// isn't. It runs only while the home page is on screen, and draws one still frame for viewers
// who ask for reduced motion.
(() => {
  const canvas = document.querySelector(".field");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const calm = matchMedia("(prefers-reduced-motion: reduce)");
  const RGB = { chalk: "244, 241, 232", lime: "184, 245, 61", gold: "201, 162, 39", card: "242, 92, 84" };
  const CHAIN_MS = 2600; // one chain: drawn over 0.6 of this, verdict to 1.4, faded by 1.9
  const VERIFIED_SHARE = 0.8;

  let w = 0;
  let h = 0;
  let dots = [];
  let chains = [];
  let pointer = null;
  let raf = 0;
  let last = 0;
  let nextChain = 0;
  let onScreen = true;
  let onHome = canvas.closest("[data-page]")?.classList.contains("is-current") ?? true;

  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const spawn = (x) => ({
    x,
    y: Math.random() * h,
    vx: 10 + Math.random() * 26,
    vy: (Math.random() - 0.5) * 8,
    r: Math.random() < 0.15 ? 2.4 : 1 + Math.random(),
    hot: Math.random() < 0.14,
  });

  function resize() {
    const box = canvas.getBoundingClientRect();
    if (!box.width || !box.height) return; // hidden page: wait until it is shown
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = box.width;
    h = box.height;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.round(Math.min(150, Math.max(40, (w * h) / 8000)));
    dots = Array.from({ length: count }, () => spawn(Math.random() * w));
    chains = [];
    if (calm.matches) frame(performance.now(), true);
  }

  function pitch() {
    const m = 24;
    const pw = w - m * 2;
    const ph = h - m * 2;
    const box = pw * 0.16;
    const tall = ph * 0.6;
    ctx.strokeStyle = `rgba(${RGB.chalk}, 0.06)`;
    ctx.lineWidth = 1;
    ctx.strokeRect(m, m, pw, ph);
    ctx.beginPath();
    ctx.moveTo(w / 2, m);
    ctx.lineTo(w / 2, h - m);
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, Math.min(ph * 0.17, 120), 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeRect(m, h / 2 - tall / 2, box, tall);
    ctx.strokeRect(w - m - box, h / 2 - tall / 2, box, tall);
  }

  // A claim: one event and the two or three earlier ones nearest it, joined in order of play.
  // Heads come from anywhere but the far edges, so no node leaves the field mid-chain.
  function link(t) {
    const pool = dots.filter((d) => d.x > w * 0.12 && d.x < w - 220);
    if (!pool.length) return;
    const head = pool[Math.floor(Math.random() * pool.length)];
    const near = dots
      .filter((d) => d !== head && d.x < head.x && dist(d, head) < 170)
      .sort((a, b) => dist(a, head) - dist(b, head))
      .slice(0, 2 + Math.round(Math.random()));
    if (near.length < 2) return;
    chains.push({ nodes: [...near.sort((a, b) => a.x - b.x), head], born: t, verified: Math.random() < VERIFIED_SHARE });
  }

  function drawChain(c, t) {
    const p = (t - c.born) / CHAIN_MS;
    if (p > 1.9) return false;
    const fade = p > 1.4 ? Math.max(0, 1 - (p - 1.4) / 0.5) : 1;
    const segs = c.nodes.length - 1;
    const drawn = Math.min(1, p / 0.6) * segs;

    ctx.lineWidth = 1.5;
    ctx.strokeStyle = `rgba(${RGB.lime}, ${0.75 * fade})`;
    ctx.beginPath();
    ctx.moveTo(c.nodes[0].x, c.nodes[0].y);
    for (let i = 1; i <= segs; i++) {
      const f = Math.min(1, Math.max(0, drawn - (i - 1)));
      if (f <= 0) break;
      const a = c.nodes[i - 1];
      const b = c.nodes[i];
      ctx.lineTo(a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f);
    }
    ctx.stroke();
    ctx.fillStyle = `rgba(${RGB.lime}, ${fade})`;
    c.nodes.forEach((n, i) => {
      if (i > drawn) return;
      ctx.beginPath();
      ctx.arc(n.x, n.y, 2.6, 0, Math.PI * 2);
      ctx.fill();
    });

    if (p > 0.65) {
      const head = c.nodes[segs];
      const q = Math.min(1, (p - 0.65) / 0.5);
      const color = c.verified ? RGB.gold : RGB.card;
      ctx.strokeStyle = `rgba(${color}, ${(1 - q * 0.6) * fade})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(head.x, head.y, 4 + q * 18, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = `rgba(${color}, ${fade})`;
      ctx.beginPath();
      ctx.arc(head.x, head.y, 3.5, 0, Math.PI * 2);
      ctx.fill();
    }
    return true;
  }

  function frame(t, still) {
    const dt = Math.min(0.05, (t - last) / 1000 || 0);
    last = t;
    ctx.clearRect(0, 0, w, h);
    pitch();

    if (!still) {
      for (const d of dots) {
        d.x += d.vx * dt;
        d.y += d.vy * dt;
        if (d.y < 0 || d.y > h) d.vy *= -1;
        if (d.x > w + 10) Object.assign(d, spawn(-10));
      }
    }
    if (pointer) {
      ctx.lineWidth = 1;
      for (const d of dots) {
        const gap = dist(d, pointer);
        if (gap > 140) continue;
        ctx.strokeStyle = `rgba(${RGB.lime}, ${0.35 * (1 - gap / 140)})`;
        ctx.beginPath();
        ctx.moveTo(pointer.x, pointer.y);
        ctx.lineTo(d.x, d.y);
        ctx.stroke();
      }
    }
    for (const d of dots) {
      ctx.fillStyle = d.hot ? `rgba(${RGB.lime}, 0.7)` : `rgba(${RGB.chalk}, 0.32)`;
      ctx.beginPath();
      ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
      ctx.fill();
    }

    if (still) {
      // One finished chain, caught at its verdict.
      if (!chains.length) link(t - CHAIN_MS * 1.1);
    } else if (t > nextChain) {
      link(t);
      nextChain = t + 900 + Math.random() * 1400;
    }
    chains = chains.filter((c) => drawChain(c, t));
  }

  function loop(t) {
    frame(t, false);
    raf = requestAnimationFrame(loop);
  }

  function update() {
    const run = onScreen && onHome && !document.hidden && !calm.matches && w > 0;
    if (run && !raf) {
      last = performance.now();
      raf = requestAnimationFrame(loop);
    } else if (!run && raf) {
      cancelAnimationFrame(raf);
      raf = 0;
    }
  }

  new ResizeObserver(() => { resize(); update(); }).observe(canvas);
  new IntersectionObserver(([entry]) => { onScreen = entry.isIntersecting; update(); }).observe(canvas);
  document.addEventListener("visibilitychange", update);
  document.addEventListener("page:change", (e) => { onHome = e.detail.page === ""; update(); });
  calm.addEventListener("change", () => {
    update();
    if (calm.matches) frame(performance.now(), true);
  });
  const hero = canvas.parentElement;
  hero.addEventListener("pointermove", (e) => {
    const box = canvas.getBoundingClientRect();
    pointer = { x: e.clientX - box.left, y: e.clientY - box.top };
  });
  hero.addEventListener("pointerleave", () => { pointer = null; });
})();
