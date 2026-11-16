// EuropeTravel, phase 1: the map, the filter panel, matching and the region card.
// Later phases (cities.js, places.js) plug in through ET.on(...) events.
(function () {
  "use strict";

  const GLOW = "#f5b942";
  const LINE = "#7f93a8";
  const TEXT = "#eef2f6";
  const MONTH_LETTERS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
  const RESULTS_SHOWN = 8;
  // Leave room for the drawer when the map frames a region.
  const DRAWER_PADDING = 400;

  const state = {
    meta: null,
    filters: {},
    month: null,
    threshold: 70,
    scores: {},
    ranked: [],
    selected: null,
    view: null, // what the drawer shows: "region", "city" or null
    basemap: "dark",
    basemapNamesCities: false, // true when the base map prints city names itself
    names: {},
  };

  // ---------- Small helpers ----------

  const listeners = {};
  function on(name, handler) {
    (listeners[name] = listeners[name] || []).push(handler);
  }
  function emit(name, payload) {
    (listeners[name] || []).forEach((handler) => handler(payload));
  }

  // Build a DOM element: h("p", {class: "note"}, "text", childNode)
  function h(tag, attrs, ...children) {
    const element = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (value === null || value === undefined || value === false) return;
      if (key === "class") element.className = value;
      else if (key.startsWith("on")) element.addEventListener(key.slice(2), value);
      else element.setAttribute(key, value === true ? "" : value);
    });
    children.flat().forEach((child) => {
      if (child === null || child === undefined || child === false) return;
      element.append(child.nodeType ? child : document.createTextNode(String(child)));
    });
    return element;
  }

  function svg(tag, attrs) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs || {}).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  }

  async function api(path, options) {
    let response;
    try {
      response = await fetch(path, options);
    } catch (error) {
      // fetch only throws when there was no answer at all.
      throw new Error("The server didn't answer. Check that Flask is still running.");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "The server returned an error (" + response.status + ").");
    return data;
  }

  const statusBox = document.getElementById("status");
  function showStatus(message) {
    statusBox.textContent = message;
    statusBox.hidden = !message;
  }

  function isNarrow() {
    return window.matchMedia("(max-width: 820px)").matches;
  }

  function hasFilters() {
    return Object.keys(state.filters).length > 0;
  }

  function monthLabel() {
    return state.month ? state.meta.months[state.month - 1] : "summer";
  }

  // ---------- Map ----------

  const map = L.map("map", {
    minZoom: 3,
    maxZoom: 17,
    zoomSnap: 0.5,
    zoomControl: false,
    maxBounds: [[12, -70], [80, 85]],
    maxBoundsViscosity: 0.6,
  }).setView([53, 12], 4);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');

  // Panes stack bottom to top: tiles, glow, region outlines, labels, cities, places.
  [["glow", 390], ["labels", 450], ["cities", 460], ["places", 470]].forEach(([name, zIndex]) => {
    const pane = map.createPane(name);
    pane.style.zIndex = zIndex;
    if (name === "glow" || name === "labels") pane.style.pointerEvents = "none";
  });

  const ESRI = "Tiles &copy; Esri and its data providers";
  const BOUNDARIES = "Regions &copy; EuroGeographics, Eurostat GISCO";

  // Esri's base maps need no key. (CARTO now watermarks tiles without one.)
  function esriLayer(service, options) {
    return L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/" + service + "/MapServer/tile/{z}/{y}/{x}",
      Object.assign({ maxZoom: 16, attribution: ESRI + " | " + BOUNDARIES }, options)
    );
  }

  const labelLayer = esriLayer("Canvas/World_Dark_Gray_Reference", { pane: "labels" });
  const basemaps = {
    dark: { layer: esriLayer("Canvas/World_Dark_Gray_Base"), labels: true },
    // The terrain map already has city names printed on it, so ours would show twice.
    terrain: { layer: esriLayer("World_Topo_Map", { maxZoom: 18 }), labels: false, namesCities: true },
    satellite: { layer: esriLayer("World_Imagery", { maxZoom: 18 }), labels: true },
  };
  let currentBasemap = null;

  function setBasemap(name) {
    if (currentBasemap) map.removeLayer(basemaps[currentBasemap].layer);
    currentBasemap = name;
    basemaps[name].layer.addTo(map);
    if (basemaps[name].labels) labelLayer.addTo(map);
    else map.removeLayer(labelLayer);
    document.querySelectorAll(".basemaps button").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.basemap === name));
    });
    restyleRegions();
    state.basemap = name;
    state.basemapNamesCities = Boolean(basemaps[name].namesCities);
    emit("basemap:changed", { name });
  }

  document.querySelectorAll(".basemaps button").forEach((button) => {
    button.addEventListener("click", () => setBasemap(button.dataset.basemap));
  });

  // ---------- Colour theme ----------

  // "night" is the default; "warm" is set as data-theme on <html> and remembered.
  function setTheme(name) {
    const warm = name === "warm";
    if (warm) document.documentElement.dataset.theme = "warm";
    else delete document.documentElement.dataset.theme;
    document.querySelectorAll(".themes button").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === (warm ? "warm" : "night")));
    });
    try {
      localStorage.setItem("et-theme", warm ? "warm" : "night");
    } catch (error) {
      // Private windows can refuse storage; the theme still applies for this visit.
    }
  }

  document.querySelectorAll(".themes button").forEach((button) => {
    button.addEventListener("click", () => setTheme(button.dataset.themeChoice));
  });
  setTheme(document.documentElement.dataset.theme === "warm" ? "warm" : "night");

  // ---------- Regions on the map ----------

  let regionLayer = null;
  let glowLayer = null;
  const layersById = {};
  const featuresById = {};

  function outlineColor() {
    // Soft grey-blue reads on the dark map; the light terrain map needs a darker line.
    return currentBasemap === "terrain" ? "#31465c" : LINE;
  }

  function regionStyle(feature) {
    const id = feature.properties.id;
    const active = hasFilters();
    const result = state.scores[id];
    const style = {
      color: outlineColor(),
      weight: 0.8,
      opacity: active ? 0.38 : 0.6,
      dashArray: null,
      fillColor: LINE,
      fillOpacity: active ? 0.01 : 0.05,
    };
    if (active && result && result.score === null) {
      style.dashArray = "3 4";
    }
    if (id === state.selected) {
      style.color = currentBasemap === "terrain" ? "#0b1420" : TEXT;
      style.weight = 2;
      style.opacity = 1;
    }
    return style;
  }

  function isMatch(id) {
    const result = state.scores[id];
    return Boolean(result) && result.score !== null && result.score >= state.threshold;
  }

  function glowStyle(feature) {
    const score = state.scores[feature.properties.id].score;
    const span = Math.max(1, 100 - state.threshold);
    const strength = Math.min(1, Math.max(0, (score - state.threshold) / span));
    return {
      color: GLOW,
      weight: 1,
      opacity: 0.9,
      fillColor: GLOW,
      fillOpacity: 0.24 + 0.5 * strength,
    };
  }

  function restyleRegions(announce) {
    if (!regionLayer) return;
    regionLayer.setStyle(regionStyle);
    glowLayer.clearLayers();
    if (hasFilters()) {
      Object.keys(featuresById).filter(isMatch).forEach((id) => glowLayer.addData(featuresById[id]));
    }
    if (state.selected && layersById[state.selected]) layersById[state.selected].bringToFront();
    if (announce) {
      const pane = map.getPane("glow");
      pane.classList.remove("is-arriving");
      void pane.offsetWidth; // restart the fade-in
      pane.classList.add("is-arriving");
    }
  }

  function tipContent(id) {
    const box = h("div", {}, h("strong", {}, state.names[id] ? state.names[id].name : id));
    if (state.names[id]) box.append(h("span", {}, state.names[id].country_name));
    const result = state.scores[id];
    if (hasFilters() && result) {
      if (result.score === null) {
        box.append(h("span", {}, "No data yet for " + missingLabels(result.missing)));
      } else {
        box.append(h("span", { class: "map-tip__score" }, result.score + "% fit"));
      }
    }
    return box;
  }

  function missingLabels(missing) {
    const labels = state.meta.filters
      .filter((filter) => missing.includes(filter.name))
      .map((filter) => filter.label.toLowerCase());
    return labels.join(" and ");
  }

  function addRegions(geojson) {
    geojson.features.forEach((feature) => {
      featuresById[feature.properties.id] = feature;
    });
    glowLayer = L.geoJSON(null, { pane: "glow", interactive: false, style: glowStyle }).addTo(map);
    regionLayer = L.geoJSON(geojson, {
      style: regionStyle,
      onEachFeature(feature, layer) {
        const id = feature.properties.id;
        layersById[id] = layer;
        layer.bindTooltip(() => tipContent(id), { sticky: true, className: "map-tip", direction: "top", offset: [0, -6] });
        layer.on("mouseover", () => {
          if (id !== state.selected) layer.setStyle({ weight: 1.6, opacity: 0.95 });
        });
        layer.on("mouseout", () => layer.setStyle(regionStyle(feature)));
        layer.on("click", () => selectRegion(id));
      },
    }).addTo(map);
  }

  // The glow should not hide streets and coast once the traveller zooms in.
  map.on("zoomend", () => {
    const zoom = map.getZoom();
    map.getPane("glow").style.opacity = zoom >= 10 ? 0.25 : zoom >= 8 ? 0.55 : 1;
  });

  // ---------- Filter panel ----------

  const filterList = document.getElementById("filter-list");
  const monthList = document.getElementById("month-list");
  const monthNote = document.getElementById("month-note");
  const thresholdInput = document.getElementById("threshold");
  const thresholdValue = document.getElementById("threshold-value");
  const resultsBox = document.getElementById("results");
  const clearButton = document.getElementById("clear-filters");

  function renderFilters() {
    filterList.replaceChildren(
      ...state.meta.filters.map((filter) => {
        const labelId = "filter-" + filter.name;
        return h(
          "div",
          { class: "filter" },
          h("div", { class: "filter__label", id: labelId }, filter.label),
          h(
            "div",
            { class: "segments", role: "group", "aria-labelledby": labelId },
            ["low", "medium", "high"].map((level) =>
              h(
                "button",
                {
                  type: "button",
                  "data-filter": filter.name,
                  "data-level": level,
                  "aria-pressed": String(state.filters[filter.name] === level),
                  onclick: () => toggleFilter(filter.name, level),
                },
                filter.levels[level]
              )
            )
          )
        );
      })
    );
  }

  function renderMonths() {
    monthList.replaceChildren(
      ...state.meta.months.map((name, index) =>
        h(
          "button",
          {
            type: "button",
            "aria-pressed": String(state.month === index + 1),
            "aria-label": name,
            title: name,
            onclick: () => toggleMonth(index + 1),
          },
          name.slice(0, 3)
        )
      )
    );
    monthNote.textContent = state.month
      ? "Temperature and rainfall are for " + state.meta.months[state.month - 1] + "."
      : "No month chosen, so temperature and rainfall are for summer (June to August).";
  }

  function toggleFilter(name, level) {
    if (state.filters[name] === level) delete state.filters[name];
    else state.filters[name] = level;
    renderFilters();
    runMatch();
  }

  function toggleMonth(month) {
    state.month = state.month === month ? null : month;
    renderMonths();
    runMatch();
  }

  // Set several choices at once, for example from a shared link. Unknown names are ignored.
  function applyState(choices) {
    const known = {};
    state.meta.filters.forEach((filter) => {
      const level = choices.filters && choices.filters[filter.name];
      if (["low", "medium", "high"].includes(level)) known[filter.name] = level;
    });
    state.filters = known;
    state.month = Number.isInteger(choices.month) && choices.month >= 1 && choices.month <= 12 ? choices.month : null;
    const min = Number(thresholdInput.min);
    const max = Number(thresholdInput.max);
    if (Number.isFinite(choices.threshold) && choices.threshold >= min && choices.threshold <= max) {
      state.threshold = Math.round(choices.threshold / 5) * 5;
      thresholdInput.value = state.threshold;
      thresholdValue.textContent = state.threshold + "%";
    }
    renderFilters();
    renderMonths();
    return runMatch();
  }

  thresholdInput.addEventListener("input", () => {
    state.threshold = Number(thresholdInput.value);
    thresholdValue.textContent = state.threshold + "%";
    restyleRegions();
    renderResults();
    emit("match:updated", state);
  });
  // When the slider is let go, bring an open region card in line with the new threshold.
  thresholdInput.addEventListener("change", () => {
    if (state.selected && state.view === "region") selectRegion(state.selected, { keepView: true });
  });

  clearButton.addEventListener("click", () => {
    state.filters = {};
    renderFilters();
    runMatch();
  });

  let matchRequest = 0;
  async function runMatch() {
    const request = ++matchRequest;
    if (!hasFilters()) {
      state.scores = {};
      state.ranked = [];
    } else {
      try {
        const data = await api("/api/match", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filters: state.filters, month: state.month }),
        });
        if (request !== matchRequest) return; // a newer choice replaced this one
        state.ranked = data.results;
        state.scores = {};
        data.results.forEach((result) => {
          state.scores[result.id] = result;
        });
        showStatus("");
      } catch (error) {
        showStatus("Couldn't score the regions. " + error.message);
        return;
      }
    }
    restyleRegions(true);
    renderResults();
    emit("match:updated", state);
    // Keep an open region card in step with the new filters or month.
    if (state.selected && state.view === "region") selectRegion(state.selected, { keepView: true });
  }

  function renderResults() {
    clearButton.hidden = !hasFilters();
    updateToggleLabel();
    if (!hasFilters()) {
      resultsBox.replaceChildren(
        h("p", { class: "results__hint" }, "Nothing chosen yet. Pick a filter above to light up the map.")
      );
      return;
    }
    const matched = state.ranked.filter((result) => isMatch(result.id));
    const unknown = state.ranked.filter((result) => result.score === null);
    const nodes = [
      h(
        "p",
        { class: "results__count" },
        matched.length === 0
          ? "No region fits yet"
          : matched.length + (matched.length === 1 ? " region fits" : " regions fit")
      ),
    ];
    if (matched.length === 0) {
      nodes.push(h("p", { class: "results__hint" }, "Lower the fit, or drop a filter."));
    } else {
      nodes.push(
        h(
          "ul",
          { class: "results__list" },
          matched.slice(0, RESULTS_SHOWN).map((result) =>
            h(
              "li",
              {},
              h(
                "button",
                { type: "button", onclick: () => selectRegion(result.id) },
                h(
                  "span",
                  { class: "results__name" },
                  state.names[result.id].name,
                  h("small", {}, state.names[result.id].country_name)
                ),
                h("span", { class: "results__score" }, result.score + "%")
              )
            )
          )
        )
      );
      if (matched.length > RESULTS_SHOWN) {
        nodes.push(h("p", { class: "note" }, "Showing the closest " + RESULTS_SHOWN + ". The rest are lit on the map."));
      }
    }
    if (unknown.length > 0) {
      nodes.push(
        h(
          "p",
          { class: "note" },
          unknown.length + " regions have no data yet for these filters. They are drawn with a dashed outline."
        )
      );
    }
    resultsBox.replaceChildren(...nodes);
  }

  // ---------- Sidebar as a sheet on small screens ----------

  const sidebar = document.getElementById("sidebar");
  const sidebarToggle = document.getElementById("sidebar-toggle");
  const sidebarToggleLabel = document.getElementById("sidebar-toggle-label");

  function setSidebarOpen(open) {
    sidebar.classList.toggle("is-open", open);
    sidebarToggle.setAttribute("aria-expanded", String(open));
  }
  sidebarToggle.addEventListener("click", () => setSidebarOpen(!sidebar.classList.contains("is-open")));

  function updateToggleLabel() {
    const count = Object.keys(state.filters).length;
    if (count === 0) {
      sidebarToggleLabel.textContent = "Filters";
      return;
    }
    const matched = state.ranked.filter((result) => isMatch(result.id)).length;
    sidebarToggleLabel.textContent =
      count + (count === 1 ? " filter, " : " filters, ") + matched + (matched === 1 ? " region fits" : " regions fit");
  }

  // ---------- Drawer ----------

  const drawer = document.getElementById("drawer");
  const drawerKicker = document.getElementById("drawer-kicker");
  const drawerTitle = document.getElementById("drawer-title");
  const drawerBody = document.getElementById("drawer-body");
  const drawerBack = document.getElementById("drawer-back");
  const drawerActions = document.getElementById("drawer-actions");
  let drawerBackHandler = null;

  function openDrawer(view) {
    const wasHidden = drawer.hidden;
    drawerKicker.textContent = view.kicker || "";
    drawerTitle.textContent = view.title;
    drawerBody.replaceChildren(...view.body);
    drawerActions.replaceChildren(...(view.actions || []));
    drawerActions.hidden = !view.actions || view.actions.length === 0;
    drawerBackHandler = view.back ? view.back.action : null;
    drawerBack.hidden = !view.back;
    drawerBack.textContent = view.back ? "Back to " + view.back.label : "";
    drawer.hidden = false;
    drawerBody.scrollTop = 0;
    if (isNarrow()) setSidebarOpen(false);
    if (wasHidden || view.focus) drawerTitle.focus({ preventScroll: true });
  }

  function closeDrawer() {
    drawer.hidden = true;
    const previous = state.selected;
    state.selected = null;
    state.view = null;
    restyleRegions();
    emit("drawer:closed", { regionId: previous });
  }

  drawerBack.addEventListener("click", () => drawerBackHandler && drawerBackHandler());
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !drawer.hidden) closeDrawer();
  });

  // ---------- Region card ----------

  let regionRequest = 0;
  async function selectRegion(id, options) {
    const keepView = options && options.keepView;
    const request = ++regionRequest;
    const changed = state.selected !== id || state.view !== "region";
    state.selected = id;
    state.view = "region";
    restyleRegions();
    if (!keepView && layersById[id]) {
      map.fitBounds(layersById[id].getBounds(), {
        paddingTopLeft: isNarrow() ? [20, 20] : [DRAWER_PADDING, 40],
        paddingBottomRight: isNarrow() ? [20, window.innerHeight * 0.6] : [40, 40],
        maxZoom: 8,
      });
    }
    let region;
    try {
      region = await api("/api/regions/" + id + (state.month ? "?month=" + state.month : ""));
    } catch (error) {
      showStatus("Couldn't load this region. " + error.message);
      return;
    }
    if (request !== regionRequest) return;
    showStatus("");
    const body = regionBody(region);
    const actions = []; // buttons under the title; later scripts add theirs
    emit("region:render", { region, body, changed, actions });
    openDrawer({ kicker: region.country_name, title: region.name, body, actions, focus: changed });
    emit("region:opened", { region, changed });
  }

  function regionBody(region) {
    const body = [];
    const fit = fitBlock(region);
    if (fit) body.push(fit);

    body.push(h("section", { "data-section": "summary" }, h("p", {}, region.summary)));

    if (region.highlights.length > 0) {
      body.push(
        h(
          "section",
          { "data-section": "highlights" },
          h("h3", {}, "What people come for"),
          h("ul", { class: "bullets" }, region.highlights.map((item) => h("li", {}, item)))
        )
      );
    }

    body.push(
      h(
        "section",
        { "data-section": "climate" },
        h("h3", {}, "Through the year"),
        region.climate
          ? climateChart(region.climate)
          : h("p", { class: "fineprint" }, "Climate data for this region hasn't been downloaded yet.")
      )
    );

    body.push(
      h(
        "section",
        { "data-section": "glance" },
        h("h3", {}, "At a glance"),
        h(
          "div",
          { class: "glance" },
          ["coast", "nature", "historic", "crowd"].map((name) => glanceRow(region.levels[name]))
        )
      )
    );

    const estimated = Object.values(region.sources).some((source) => source === "curated-estimate" || source === "proxy");
    if (estimated) {
      body.push(
        h(
          "p",
          { class: "fineprint" },
          "Some figures for this region are estimates, not measurements. See STATUS.md in the project for which ones."
        )
      );
    }
    return body;
  }

  function fitBlock(region) {
    if (!hasFilters()) return null;
    const result = state.scores[region.id];
    if (!result) return null;
    const filtersByName = {};
    state.meta.filters.forEach((filter) => {
      filtersByName[filter.name] = filter;
    });
    if (result.score === null) {
      return h(
        "section",
        { class: "fit fit--quiet" },
        h("p", { class: "fit__score" }, "Can't score this region yet"),
        h("p", { class: "note" }, "There is no data for " + missingLabels(result.missing) + " here.")
      );
    }
    const lit = result.score >= state.threshold;
    return h(
      "section",
      { class: "fit" + (lit ? "" : " fit--quiet") },
      h("p", { class: "fit__score" }, result.score + "% fit"),
      !lit && h("p", { class: "note" }, "Below your " + state.threshold + "% line, so it isn't lit."),
      h(
        "div",
        { class: "fit__rows" },
        Object.keys(result.matches).map((name) => {
          const filter = filtersByName[name];
          const wanted = filter.levels[state.filters[name]].toLowerCase();
          const actual = region.levels[name].level_label.toLowerCase();
          const season = filter.seasonal ? " in " + monthLabel() : "";
          return h(
            "div",
            { class: "fit__row" },
            h("span", {}, filter.label + ": you want " + wanted + ", it is " + actual + season),
            h("span", {}, result.matches[name] + "%")
          );
        })
      )
    );
  }

  function glanceRow(level) {
    const steps = { low: 1, medium: 2, high: 3 }[level.level] || 0;
    return h(
      "div",
      { class: "glance__row" },
      h("span", {}, level.label),
      h(
        "span",
        { class: "glance__value" },
        level.level_label || "Not known yet",
        h(
          "span",
          { class: "meter", "aria-hidden": "true" },
          [1, 2, 3].map((step) => h("i", { class: step <= steps ? "is-on" : "" }))
        )
      )
    );
  }

  // Twelve rain bars with the temperature line drawn over them.
  function climateChart(climate) {
    const width = 332;
    const height = 132;
    const top = 16;
    const bottom = 20;
    const column = width / 12;
    const plot = height - top - bottom;
    const temps = climate.temp_max_c;
    const rain = climate.precip_mm;
    const rainMax = Math.max(120, ...rain);
    const tempMin = Math.min(0, ...temps);
    const tempMax = Math.max(35, ...temps);
    const yTemp = (value) => top + plot * (1 - (value - tempMin) / (tempMax - tempMin));
    const focus = state.month ? [state.month] : [6, 7, 8];

    const chart = svg("svg", { viewBox: "0 0 " + width + " " + height, role: "img" });
    const title = svg("title");
    title.textContent = "Monthly high temperature and rainfall";
    chart.append(title);

    rain.forEach((value, index) => {
      const barHeight = (plot * value) / rainMax;
      chart.append(
        svg("rect", {
          x: (index * column + 5).toFixed(1),
          y: (top + plot - barHeight).toFixed(1),
          width: (column - 10).toFixed(1),
          height: Math.max(1, barHeight).toFixed(1),
          rx: 2,
          class: focus.includes(index + 1) ? "chart-rain is-focus" : "chart-rain",
        })
      );
      const label = svg("text", {
        x: (index * column + column / 2).toFixed(1),
        y: height - 5,
        "text-anchor": "middle",
        "font-size": 11,
        class: focus.includes(index + 1) ? "chart-month is-focus" : "chart-month",
      });
      label.textContent = MONTH_LETTERS[index];
      chart.append(label);
    });

    chart.append(
      svg("polyline", {
        points: temps.map((value, index) => (index * column + column / 2).toFixed(1) + "," + yTemp(value).toFixed(1)).join(" "),
        class: "chart-temp",
        "stroke-width": 2,
        "stroke-linejoin": "round",
        "stroke-linecap": "round",
      })
    );
    temps.forEach((value, index) => {
      if (!focus.includes(index + 1)) return;
      chart.append(
        svg("circle", { cx: (index * column + column / 2).toFixed(1), cy: yTemp(value).toFixed(1), r: 3.5, class: "chart-temp-dot" })
      );
    });

    const average = (series) => focus.reduce((sum, month) => sum + series[month - 1], 0) / focus.length;
    const period = state.month ? state.meta.months[state.month - 1] : "June to August";
    return h(
      "div",
      { class: "chart" },
      chart,
      h(
        "div",
        { class: "chart__key" },
        h("span", {}, h("i", { class: "key-temp" }), "Daily high"),
        h("span", {}, h("i", { class: "key-rain" }), "Rain per month")
      ),
      h(
        "p",
        { class: "chart__caption" },
        period + ": highs around " + Math.round(average(temps)) + " °C, about " + Math.round(average(rain)) + " mm of rain a month."
      )
    );
  }

  // Centre a point in the part of the map that the drawer does not cover.
  function focusOn(latlng, zoom) {
    const shift = isNarrow() ? [0, window.innerHeight * 0.3] : [-DRAWER_PADDING / 2, 0];
    const target = map.project(latlng, zoom).add(shift);
    map.flyTo(map.unproject(target, zoom), zoom, { duration: 0.8 });
  }

  // ---------- Start ----------

  window.ET = {
    map, state, on, emit, h, svg, api, showStatus, openDrawer, closeDrawer, selectRegion, restyleRegions, focusOn, isNarrow,
    layersById, hasFilters, isMatch, toggleMonth, applyState, setBasemap, monthLabel, missingLabels, glanceRow,
  };

  async function start() {
    setBasemap("dark");
    try {
      const [meta, geojson, names] = await Promise.all([
        api("/api/meta"),
        api("/static/geo/nuts2.geojson"),
        api("/api/regions"),
      ]);
      state.meta = meta;
      if (meta.region_count === 0 || geojson.features.length === 0) {
        showStatus("The region data is missing. Run 'python -m scripts.build_data merge' in the project folder, then reload.");
      }
      state.threshold = meta.default_threshold;
      thresholdInput.value = state.threshold;
      thresholdValue.textContent = state.threshold + "%";
      names.regions.forEach((region) => {
        state.names[region.id] = region;
      });
      addRegions(geojson);
      renderFilters();
      renderMonths();
      renderResults();
      emit("ready", state);
    } catch (error) {
      showStatus("Couldn't load the map data. Check that the server is running, then reload. " + error.message);
    }
  }

  start();
})();
