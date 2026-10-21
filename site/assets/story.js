// The explained page's eight scenes (index.html, #/explained). Each lights up
// while it's on screen and goes quiet when it leaves, so nothing animates in a
// page the reader can't see; the hash and chain scenes break on purpose, at a
// button. CSS carries the motion (site.css, gated behind .is-live and the
// viewer's reduced-motion setting), so this file stays about intent.
(() => {
  const scenes = document.querySelectorAll("[data-scene]");
  if (!scenes.length) return;

  if ("IntersectionObserver" in window) {
    const watcher = new IntersectionObserver((entries) => {
      for (const entry of entries) entry.target.classList.toggle("is-live", entry.isIntersecting);
    }, { threshold: 0.25 });
    scenes.forEach((scene) => watcher.observe(scene));
  } else {
    scenes.forEach((scene) => scene.classList.add("is-live"));
  }

  // The two tamper buttons: toggle the scene's broken state and keep the label
  // honest about what pressing it again will do.
  for (const scene of scenes) {
    const toggle = scene.querySelector("[data-scene-toggle]");
    if (!toggle) continue;
    const intact = toggle.dataset.labelIntact ?? "Try it";
    const broken = toggle.dataset.labelBroken ?? "Reset";
    const sync = () => {
      const on = scene.classList.contains("is-tampered");
      toggle.setAttribute("aria-pressed", String(on));
      toggle.textContent = on ? broken : intact;
    };
    toggle.addEventListener("click", () => {
      scene.classList.toggle("is-tampered");
      sync();
    });
    sync();
  }
})();
