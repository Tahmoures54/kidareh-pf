(() => {
  "use strict";
  const normalize = (value) => String(value || "").trim().replace(/[ي]/g, "ی").replace(/[ك]/g, "ک");
  const timers = new WeakMap();

  async function suggestDatalist(input) {
    const query = normalize(input.value);
    const listId = input.getAttribute("list") || "iranCityOptions";
    const list = document.getElementById(listId);
    if (!list || query.length < 2) {
      if (list) list.replaceChildren();
      return;
    }
    const previous = timers.get(input);
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
          option.label = [item.type === "village" ? "روستا" : "شهر", item.province, item.county].filter(Boolean).join(" · ");
          return option;
        }));
      } catch (_) {
        // Keep manual entry available if suggestions cannot be loaded.
      }
    }, 140);
    timers.set(input, timer);
  }

  function initCityCombobox() {
    const root = document.getElementById("marketCityCombobox");
    const input = document.getElementById("citySelect");
    const list = document.getElementById("marketCityOptions");
    const toggle = document.getElementById("toggleMarketCityPicker");
    if (!root || !input || !list) return;

    let requestNumber = 0;
    let debounceTimer = null;
    let activeIndex = -1;
    let items = [];

    function close() {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      activeIndex = -1;
    }

    function render(itemsToRender, query) {
      items = itemsToRender;
      activeIndex = -1;
      list.replaceChildren();
      if (!items.length) {
        const empty = document.createElement("div");
        empty.className = "market-city-empty";
        empty.textContent = query.length < 2
          ? "برای جست‌وجوی شهر یا روستا، حداقل دو حرف بنویسید."
          : "نتیجه‌ای پیدا نشد؛ املای نام را بررسی کنید.";
        list.appendChild(empty);
      } else {
        items.forEach((item, index) => {
          const option = document.createElement("button");
          option.type = "button";
          option.className = "market-city-option";
          option.setAttribute("role", "option");
          option.setAttribute("aria-selected", "false");
          option.dataset.index = String(index);
          const name = document.createElement("span");
          name.className = "market-city-option-name";
          name.textContent = item.name;
          const meta = document.createElement("small");
          meta.className = "market-city-option-meta";
          meta.textContent = [
            item.type === "village" ? "روستا" : "شهر",
            item.province,
            item.county
          ].filter(Boolean).join(" · ");
          option.append(name, meta);
          option.addEventListener("mousedown", (event) => event.preventDefault());
          option.addEventListener("click", () => selectItem(item));
          list.appendChild(option);
        });
      }
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
    }

    async function fetchSuggestions() {
      const query = normalize(input.value);
      const thisRequest = ++requestNumber;
      try {
        const url = query.length >= 2
          ? "/api/locations?q=" + encodeURIComponent(query)
          : "/api/locations";
        const response = await fetch(url, {
          credentials: "same-origin",
          headers: { "Accept": "application/json" }
        });
        if (!response.ok) throw new Error("location lookup failed");
        const result = await response.json();
        if (thisRequest !== requestNumber || normalize(input.value) !== query) return;
        render(result.items || [], query);
      } catch (_) {
        if (thisRequest !== requestNumber) return;
        render([], query);
      }
    }

    function scheduleSuggestions() {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(fetchSuggestions, normalize(input.value).length < 2 ? 0 : 160);
    }

    function selectItem(item) {
      input.value = item.name;
      input.dataset.selectedType = item.type || "city";
      input.dataset.selectedId = item.id == null ? "" : String(item.id);
      input.dispatchEvent(new Event("change", { bubbles: true }));
      close();
    }

    function moveActive(delta) {
      if (list.hidden) {
        fetchSuggestions();
        return;
      }
      const options = Array.from(list.querySelectorAll(".market-city-option"));
      if (!options.length) return;
      activeIndex = (activeIndex + delta + options.length) % options.length;
      options.forEach((option, index) => {
        const active = index === activeIndex;
        option.classList.toggle("active", active);
        option.setAttribute("aria-selected", active ? "true" : "false");
      });
      options[activeIndex].scrollIntoView({ block: "nearest" });
    }

    input.addEventListener("focus", fetchSuggestions);
    input.addEventListener("click", () => {
      if (list.hidden) fetchSuggestions();
    });
    input.addEventListener("input", () => {
      delete input.dataset.selectedType;
      delete input.dataset.selectedId;
      scheduleSuggestions();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        moveActive(1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        moveActive(-1);
      } else if (event.key === "Enter" && !list.hidden) {
        const options = Array.from(list.querySelectorAll(".market-city-option"));
        if (activeIndex >= 0 && items[activeIndex]) {
          event.preventDefault();
          selectItem(items[activeIndex]);
        } else if (options.length === 1 && items[0]) {
          event.preventDefault();
          selectItem(items[0]);
        }
      } else if (event.key === "Escape") {
        close();
      }
    });
    toggle?.addEventListener("click", () => {
      if (list.hidden) {
        input.focus();
        fetchSuggestions();
      } else {
        close();
      }
    });
    document.addEventListener("click", (event) => {
      if (!root.contains(event.target)) close();
    });
    input.addEventListener("blur", () => {
      window.setTimeout(() => {
        if (!root.contains(document.activeElement)) close();
      }, 120);
    });
  }

  function init() {
    initCityCombobox();
    document.querySelectorAll("input[data-iran-location]").forEach((input) => {
      input.addEventListener("input", () => suggestDatalist(input));
      input.setAttribute("autocomplete", "off");
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();