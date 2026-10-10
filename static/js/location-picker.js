(() => {
  "use strict";
  const normalize = (value) => String(value || "").trim().replace(/[ي]/g, "ی").replace(/[ك]/g, "ک");
  const pending = new WeakMap();
  async function suggest(input) {
    const query = normalize(input.value);
    const listId = input.getAttribute("list") || "iranCityOptions";
    const list = document.getElementById(listId);
    if (!list || query.length < 2) {
      if (list) list.replaceChildren();
      return;
    }
    const previous = pending.get(input);
    if (previous) clearTimeout(previous);
    const timer = setTimeout(async () => {
      try {
        const response = await fetch("/api/locations?q=" + encodeURIComponent(query), {
          credentials: "same-origin",
          headers: { "Accept": "application/json" }
        });
        if (!response.ok) return;
        const result = await response.json();
        if (normalize(input.value) !== query) return;
        list.replaceChildren(...(result.items || []).map((item) => {
          const option = document.createElement("option");
          option.value = item.name;
          return option;
        }));
      } catch (_) {
        // Location entry remains free-text if the suggestion service is unavailable.
      }
    }, 140);
    pending.set(input, timer);
  }
  function init() {
    document.querySelectorAll("input[data-iran-location], input#citySelect").forEach((input) => {
      input.addEventListener("input", () => suggest(input));
      input.setAttribute("autocomplete", "off");
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();