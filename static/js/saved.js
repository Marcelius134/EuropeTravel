// EuropeTravel: save regions and cities to come back to.
// The list lives in this browser only (localStorage); nothing is sent to the server.
(function () {
  "use strict";

  const ET = window.ET;
  const { state, on, emit, h } = ET;

  const STORAGE_KEY = "et-saved";
  const MAX_SAVED = 40;

  const section = document.getElementById("saved");
  const list = document.getElementById("saved-list");
  const note = document.getElementById("saved-note");

  const HEART =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';
  const HEART_FULL =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" fill="currentColor" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>';

  function icon(markup) {
    const holder = document.createElement("span");
    holder.innerHTML = markup;
    return holder.firstChild;
  }

  // ---------- Storage ----------

  let storageWorks = true;

  function isEntry(entry) {
    return (
      entry &&
      (entry.kind === "region" || entry.kind === "city") &&
      typeof entry.id === "string" &&
      typeof entry.name === "string"
    );
  }

  function load() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      return Array.isArray(stored) ? stored.filter(isEntry).slice(0, MAX_SAVED) : [];
    } catch (error) {
      storageWorks = false;
      return [];
    }
  }

  function store() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
      storageWorks = true;
    } catch (error) {
      storageWorks = false;
    }
  }

  let saved = load(); // newest first: [{ kind, id, name, where }]

  function isSaved(kind, id) {
    return saved.some((entry) => entry.kind === kind && entry.id === id);
  }

  function toggle(entry) {
    if (isSaved(entry.kind, entry.id)) {
      saved = saved.filter((other) => !(other.kind === entry.kind && other.id === entry.id));
    } else {
      saved = [entry].concat(saved).slice(0, MAX_SAVED);
    }
    store();
    render();
    emit("saved:changed", { saved });
  }

  // ---------- The button on a card ----------

  function saveButton(entry) {
    const kept = isSaved(entry.kind, entry.id);
    const button = h(
      "button",
      {
        type: "button",
        class: "action-button",
        "data-action": "save",
        "aria-pressed": String(kept),
        onclick: () => {
          toggle(entry);
          button.replaceWith(saveButton(entry));
        },
      },
      icon(kept ? HEART_FULL : HEART),
      kept ? "Saved" : "Save"
    );
    button.entry = entry;
    return button;
  }

  on("region:render", ({ region, actions }) => {
    actions.unshift(saveButton({ kind: "region", id: region.id, name: region.name, where: region.country_name }));
  });

  on("city:render", ({ city, actions }) => {
    actions.unshift(
      saveButton({ kind: "city", id: city.id, name: city.name, where: city.region_name + ", " + city.country_name })
    );
  });

  // ---------- The list in the side panel ----------

  function open(entry) {
    if (entry.kind === "region") ET.selectRegion(entry.id);
    else ET.openCity(entry.id);
  }

  function scoreOf(entry) {
    if (entry.kind !== "region" || !ET.hasFilters()) return null;
    const result = state.scores[entry.id];
    return result && result.score !== null ? result.score + "%" : null;
  }

  function render() {
    section.hidden = saved.length === 0;
    list.replaceChildren(
      ...saved.map((entry) =>
        h(
          "li",
          {},
          h(
            "button",
            { type: "button", class: "saved__open", onclick: () => open(entry) },
            h("span", { class: "saved__name" }, entry.name, h("small", {}, entry.where || "")),
            scoreOf(entry) && h("span", { class: "saved__score" }, scoreOf(entry))
          ),
          h(
            "button",
            { type: "button", class: "saved__remove", "aria-label": "Remove " + entry.name + " from saved", onclick: () => removeEntry(entry) },
            "×"
          )
        )
      )
    );
    note.hidden = storageWorks;
    note.textContent = storageWorks
      ? ""
      : "This browser isn't letting the page keep data, so the list will be gone when you close the tab.";
  }

  function removeEntry(entry) {
    toggle(entry);
    // If that place's card is open, its button has to switch back to "Save".
    const button = document.querySelector('#drawer-actions [data-action="save"]');
    if (button && button.entry && button.entry.kind === entry.kind && button.entry.id === entry.id) {
      button.replaceWith(saveButton(button.entry));
    }
  }

  on("match:updated", render);
  render();

  ET.savedPlaces = () => saved.slice();
})();
