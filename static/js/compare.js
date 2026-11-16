// EuropeTravel: compare two or three regions side by side.
// Regions are picked with the "Compare" button on a region card and wait in a
// small tray over the map until the traveller opens the comparison.
(function () {
  "use strict";

  const ET = window.ET;
  const { state, on, emit, h, api } = ET;

  const MAX_REGIONS = 3;
  state.compare = []; // region ids, in the order they were picked
  state.compareOpen = false;

  const tray = document.getElementById("compare-tray");
  const panel = document.getElementById("compare");
  const panelBody = document.getElementById("compare-body");
  const panelTitle = document.getElementById("compare-title");

  const ICON =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 4v16M12 4v16M19 4v16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';

  function icon(markup) {
    const holder = document.createElement("span");
    holder.innerHTML = markup;
    return holder.firstChild;
  }

  function nameOf(id) {
    return state.names[id] ? state.names[id].name : id;
  }

  // ---------- Choosing regions ----------

  function setCompare(ids) {
    const known = ids.filter((id, index) => state.names[id] && ids.indexOf(id) === index);
    state.compare = known.slice(0, MAX_REGIONS);
    if (state.compare.length < 2 && state.compareOpen) closeCompare();
    renderTray();
    if (state.compareOpen) renderCompare();
    emit("compare:changed", { ids: state.compare });
  }

  function toggleCompare(id) {
    if (state.compare.includes(id)) setCompare(state.compare.filter((other) => other !== id));
    else if (state.compare.length < MAX_REGIONS) setCompare(state.compare.concat(id));
  }

  function compareButton(regionId) {
    const chosen = state.compare.includes(regionId);
    const full = !chosen && state.compare.length >= MAX_REGIONS;
    const button = h(
      "button",
      {
        type: "button",
        class: "action-button",
        "data-action": "compare",
        "aria-pressed": String(chosen),
        disabled: full,
        title: full ? "You can compare up to " + MAX_REGIONS + " regions. Remove one first." : null,
        onclick: () => {
          toggleCompare(regionId);
          button.replaceWith(compareButton(regionId));
        },
      },
      icon(ICON),
      chosen ? "In the comparison" : "Compare"
    );
    return button;
  }

  on("region:render", ({ region, actions }) => {
    actions.push(compareButton(region.id));
  });

  // Keep the button on an open region card right when the tray changes the list.
  on("compare:changed", () => {
    const button = document.querySelector('#drawer-actions [data-action="compare"]');
    if (button && state.selected && state.view === "region") button.replaceWith(compareButton(state.selected));
  });

  function renderTray() {
    tray.hidden = state.compare.length === 0 || state.compareOpen;
    if (tray.hidden) return;
    const count = state.compare.length;
    tray.replaceChildren(
      h(
        "ul",
        { class: "tray__list" },
        state.compare.map((id) =>
          h(
            "li",
            { class: "tray__chip" },
            h("button", { type: "button", class: "tray__name", onclick: () => ET.selectRegion(id) }, nameOf(id)),
            h(
              "button",
              { type: "button", class: "tray__remove", "aria-label": "Remove " + nameOf(id), onclick: () => toggleCompare(id) },
              "×"
            )
          )
        )
      ),
      count < 2
        ? h("span", { class: "tray__hint" }, "Add one more region to compare")
        : h("button", { type: "button", class: "tray__go", onclick: openCompare }, "Compare " + count + " regions")
    );
  }

  // ---------- The comparison ----------

  function periodAverage(series) {
    const months = state.month ? [state.month] : [6, 7, 8];
    return months.reduce((sum, month) => sum + series[month - 1], 0) / months.length;
  }

  function meter(level) {
    const steps = { low: 1, medium: 2, high: 3 }[level] || 0;
    return h(
      "span",
      { class: "meter", "aria-hidden": "true" },
      [1, 2, 3].map((step) => h("i", { class: step <= steps ? "is-on" : "" }))
    );
  }

  // One cell of a filter row: the level in words, a meter, and the real number where there is one.
  function levelCell(region, filter) {
    const level = region.levels[filter.name];
    if (!level.level) return h("span", { class: "compare__unknown" }, "Not known yet");
    let detail = null;
    if (filter.name === "temperature") detail = Math.round(periodAverage(region.climate.temp_max_c)) + " °C";
    if (filter.name === "rainfall") detail = Math.round(periodAverage(region.climate.precip_mm)) + " mm a month";
    const result = state.scores[region.id];
    const match = state.filters[filter.name] && result && result.matches[filter.name] !== undefined ? result.matches[filter.name] : null;
    return h(
      "span",
      { class: "compare__level" },
      h("span", { class: "compare__level-top" }, meter(level.level), level.level_label),
      detail && h("small", {}, detail),
      match !== null && h("small", { class: match >= state.threshold ? "is-fit" : "" }, match + "% match")
    );
  }

  function fitCell(region) {
    const result = state.scores[region.id];
    if (!result) return h("span", {}, "");
    if (result.score === null) {
      return h("span", { class: "compare__unknown" }, "Can't be scored: no data for " + ET.missingLabels(result.missing));
    }
    const lit = result.score >= state.threshold;
    return h(
      "span",
      { class: "compare__fit" + (lit ? " is-fit" : "") },
      result.score + "%",
      h("small", {}, lit ? "Lit on the map" : "Below your " + state.threshold + "% line")
    );
  }

  function monthsCell(year) {
    if (!year || year.scores.some((score) => score === null)) return h("span", { class: "compare__unknown" }, "Not known yet");
    const fitting = year.scores.map((score, index) => (score >= state.threshold ? index + 1 : null)).filter(Boolean);
    if (fitting.length === 0) return h("span", {}, "No month reaches " + state.threshold + "%");
    const words = ET.describeMonths(fitting, state.meta.months);
    return h("span", {}, words.charAt(0).toUpperCase() + words.slice(1));
  }

  function row(label, note, cells) {
    return h(
      "div",
      { class: "compare__row", role: "row" },
      h("div", { class: "compare__label", role: "rowheader" }, label, note && h("small", {}, note)),
      cells.map((cell) => h("div", { class: "compare__cell", role: "cell" }, cell))
    );
  }

  function table(entries) {
    const regions = entries.map((entry) => entry.region);
    const period = state.month ? state.meta.months[state.month - 1] : "summer";
    const rows = [
      h(
        "div",
        { class: "compare__row compare__row--head", role: "row" },
        h("div", { class: "compare__label", role: "columnheader" }),
        regions.map((region) =>
          h(
            "div",
            { class: "compare__cell", role: "columnheader" },
            h("small", {}, region.country_name),
            h("strong", { class: "compare__name" }, region.name),
            h(
              "span",
              { class: "compare__links" },
              h("button", { type: "button", class: "text-button", onclick: () => { closeCompare(); ET.selectRegion(region.id); } }, "Open"),
              h("button", { type: "button", class: "text-button", onclick: () => toggleCompare(region.id) }, "Remove")
            )
          )
        )
      ),
    ];
    if (ET.hasFilters()) rows.push(row("Fit for your filters", null, regions.map(fitCell)));
    const seasonalChosen = state.meta.filters.some((filter) => filter.seasonal && state.filters[filter.name]);
    if (seasonalChosen) rows.push(row("Best months", "for your filters", entries.map((entry) => monthsCell(entry.year))));
    state.meta.filters.forEach((filter) => {
      const wanted = state.filters[filter.name];
      const notes = [];
      if (filter.seasonal) notes.push("in " + period);
      if (wanted) notes.push("you want " + filter.levels[wanted].toLowerCase());
      rows.push(row(filter.label, notes.join(", ") || null, regions.map((region) => levelCell(region, filter))));
    });
    rows.push(row("In short", null, regions.map((region) => h("span", { class: "compare__text" }, region.summary))));
    rows.push(
      row(
        "What people come for",
        null,
        regions.map((region) =>
          region.highlights.length > 0
            ? h("ul", { class: "bullets" }, region.highlights.slice(0, 4).map((item) => h("li", {}, item)))
            : h("span", { class: "compare__unknown" }, "Nothing written yet")
        )
      )
    );
    rows.push(
      row(
        "Main cities",
        null,
        regions.map((region) =>
          region.cities.length > 0
            ? h("span", { class: "compare__text" }, region.cities.map((city) => city.name).join(", "))
            : h("span", { class: "compare__unknown" }, "None listed")
        )
      )
    );
    return h("div", { class: "compare__table", role: "table", style: "--columns:" + regions.length }, rows);
  }

  let request = 0;
  async function renderCompare() {
    const mine = ++request;
    const ids = state.compare.slice();
    const seasonalChosen = state.meta.filters.some((filter) => filter.seasonal && state.filters[filter.name]);
    if (!panelBody.firstChild) panelBody.replaceChildren(h("p", { class: "note" }, "Loading the regions…"));
    let entries;
    try {
      entries = await Promise.all(
        ids.map(async (id) => {
          const region = await api("/api/regions/" + id + (state.month ? "?month=" + state.month : ""));
          let year = null;
          if (seasonalChosen && region.climate) {
            year = await api("/api/regions/" + id + "/year", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ filters: state.filters }),
            });
          }
          return { region, year };
        })
      );
    } catch (error) {
      if (mine === request) panelBody.replaceChildren(h("p", { class: "note" }, "Couldn't load the comparison. " + error.message));
      return;
    }
    if (mine !== request || !state.compareOpen) return;
    panelBody.replaceChildren(
      table(entries),
      h(
        "p",
        { class: "fineprint" },
        "Change the filters, the month or the fit line on the right and this table follows. Some figures are estimates; see STATUS.md in the project."
      )
    );
  }

  function openCompare() {
    if (state.compare.length < 2) return;
    state.compareOpen = true;
    panel.hidden = false;
    panelBody.replaceChildren();
    renderTray();
    renderCompare();
    panelTitle.focus({ preventScroll: true });
    emit("compare:changed", { ids: state.compare });
  }

  function closeCompare() {
    if (!state.compareOpen) return;
    state.compareOpen = false;
    panel.hidden = true;
    renderTray();
    emit("compare:changed", { ids: state.compare });
  }

  document.getElementById("compare-close").addEventListener("click", closeCompare);
  // Escape closes the comparison first, before the card underneath it.
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Escape" && state.compareOpen) {
        event.stopPropagation();
        closeCompare();
      }
    },
    true
  );

  on("match:updated", () => {
    if (state.compareOpen) renderCompare();
  });

  ET.setCompare = setCompare;
  ET.openCompare = openCompare;
  ET.closeCompare = closeCompare;
})();
