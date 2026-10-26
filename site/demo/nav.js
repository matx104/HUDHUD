// The rooms' bar (nav.css): the judges' guide is lit on a first visit, until it is opened once,
// and closes on a click elsewhere or Escape. A take recorded with ?autostart=1 never sees it lit.
(() => {
  const guide = document.querySelector("[data-guide]");
  if (!guide) return;
  const seen = "hudhud.guide.seen";
  const read = () => {
    try {
      return Boolean(localStorage.getItem(seen));
    } catch {
      return true; // storage blocked: no reminder that could never go out
    }
  };
  if (!read() && !new URLSearchParams(location.search).has("autostart")) guide.dataset.fresh = "";
  guide.addEventListener("toggle", () => {
    if (!guide.open) return;
    delete guide.dataset.fresh;
    try {
      localStorage.setItem(seen, "1");
    } catch {
      // Storage blocked: lit again on the next visit, no harm done.
    }
  });
  document.addEventListener("click", (event) => {
    if (guide.open && !guide.contains(event.target)) guide.open = false;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !guide.open) return;
    guide.open = false;
    guide.querySelector("summary").focus();
  });
})();
