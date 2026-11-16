// EuropeTravel, phase 2: city dots on the map and the city card.
(function () {
  "use strict";

  const ET = window.ET;
  const { map, state, on, emit, h, api } = ET;

  const CITY = "#4dd0e1";
  const SEA = "#0b1420";
  const TEXT = "#eef2f6";
  // Below this zoom only the open region's cities are drawn, to keep Europe uncluttered.
  const SHOW_ALL_FROM_ZOOM = 6.5;
  const CITY_ZOOM = 11;

  const entries = {}; // city id -> { city, marker }
  state.cityId = null;

  function formatPopulation(count) {
    if (!count) return null;
    if (count >= 1e6) return (count / 1e6).toFixed(1).replace(/\.0$/, "") + " million people";
    if (count >= 10000) return (Math.round(count / 1000) * 1000).toLocaleString("en") + " people";
    return count.toLocaleString("en") + " people";
  }

  function markerStyle(city) {
    const open = city.id === state.cityId;
    const inOpenRegion = city.region_id === state.selected;
    return {
      radius: open ? 7 : inOpenRegion ? 5 : 3.5,
      color: open ? TEXT : SEA,
      weight: open ? 2 : 1,
      fillColor: CITY,
      fillOpacity: 1,
    };
  }

  function refreshMarkers() {
    const showAll = map.getZoom() >= SHOW_ALL_FROM_ZOOM;
    Object.values(entries).forEach(({ city, marker }) => {
      const inOpenRegion = city.region_id === state.selected;
      const visible = showAll || inOpenRegion;
      if (visible && !map.hasLayer(marker)) marker.addTo(map);
      if (!visible && map.hasLayer(marker)) map.removeLayer(marker);
      if (!visible) return;
      marker.setStyle(markerStyle(city));
      // Names stay on screen for the open region; elsewhere they appear on hover.
      // Not on a base map that prints city names itself, or each would show twice.
      const wantPermanent = inOpenRegion && !state.basemapNamesCities;
      if (marker.labelIsPermanent !== wantPermanent) {
        marker.unbindTooltip();
        marker.bindTooltip(city.name, {
          permanent: wantPermanent,
          direction: "right",
          offset: [8, 0],
          className: wantPermanent ? "city-label" : "map-tip",
          pane: wantPermanent ? "cities" : "tooltipPane",
        });
        marker.labelIsPermanent = wantPermanent;
      }
      if (city.id === state.cityId) marker.bringToFront();
    });
  }

  function addCities(cities) {
    cities.forEach((city) => {
      const marker = L.circleMarker([city.lat, city.lon], Object.assign({ pane: "cities" }, markerStyle(city)));
      marker.on("click", (event) => {
        L.DomEvent.stopPropagation(event);
        openCity(city.id);
      });
      entries[city.id] = { city, marker };
    });
    refreshMarkers();
  }

  // ---------- Cities inside the region card ----------

  on("region:render", ({ region, body }) => {
    if (!region.cities || region.cities.length === 0) return;
    const section = h(
      "section",
      { "data-section": "cities" },
      h("h3", {}, "Cities"),
      h(
        "ul",
        { class: "city-list" },
        region.cities.map((city) =>
          h(
            "li",
            {},
            h(
              "button",
              { type: "button", onclick: () => openCity(city.id) },
              h("span", { class: "city-list__dot", "aria-hidden": "true" }),
              h("span", { class: "city-list__name" }, city.name),
              h("span", { class: "city-list__meta" }, formatPopulation(city.population) || "")
            )
          )
        )
      )
    );
    const climateIndex = body.findIndex((node) => node.dataset && node.dataset.section === "climate");
    body.splice(climateIndex === -1 ? body.length : climateIndex, 0, section);
  });

  // ---------- City card ----------

  let cityRequest = 0;
  async function openCity(id) {
    const request = ++cityRequest;
    let city;
    try {
      city = await api("/api/cities/" + id);
    } catch (error) {
      ET.showStatus("Couldn't load this city. " + error.message);
      return;
    }
    if (request !== cityRequest) return;
    ET.showStatus("");
    state.selected = city.region_id;
    state.view = "city";
    state.cityId = city.id;
    ET.restyleRegions();
    refreshMarkers();
    ET.focusOn([city.lat, city.lon], Math.max(map.getZoom(), CITY_ZOOM));

    const body = cityBody(city);
    const actions = [];
    emit("city:render", { city, body, actions });
    ET.openDrawer({
      kicker: city.region_name + ", " + city.country_name,
      title: city.name,
      body,
      actions,
      focus: true,
      back: { label: city.region_name, action: () => ET.selectRegion(city.region_id) },
    });
    emit("city:opened", { city });
  }

  function cityBody(city) {
    const body = [];
    const population = formatPopulation(city.population);
    if (city.summary) {
      body.push(h("section", { "data-section": "summary" }, h("p", {}, city.summary)));
    } else {
      body.push(
        h(
          "section",
          { "data-section": "summary" },
          h("p", {}, "There are no travel notes for " + city.name + " yet."),
          h("p", { class: "fineprint" }, "Notes are added by the data build. See README.md in the project.")
        )
      );
    }
    if (population) body.push(h("p", { class: "fact" }, "Home to about " + population + "."));
    if (city.things_to_do.length > 0) {
      body.push(
        h(
          "section",
          { "data-section": "things" },
          h("h3", {}, "Ideas for a visit"),
          h("ul", { class: "bullets" }, city.things_to_do.map((item) => h("li", {}, item)))
        )
      );
    }
    if (city.sources.text === "wikivoyage") {
      body.push(
        h(
          "p",
          { class: "fineprint", "data-section": "credit" },
          "Text adapted from ",
          h("a", { href: "https://en.wikivoyage.org/wiki/" + encodeURIComponent(city.name), target: "_blank", rel: "noopener" }, "Wikivoyage"),
          ", CC BY-SA."
        )
      );
    }
    return body;
  }

  function leaveCity() {
    if (!state.cityId) return;
    const previous = state.cityId;
    state.cityId = null;
    emit("city:closed", { cityId: previous });
  }

  on("region:opened", () => {
    leaveCity();
    refreshMarkers();
  });
  on("drawer:closed", () => {
    leaveCity();
    refreshMarkers();
  });
  map.on("zoomend", refreshMarkers);
  on("basemap:changed", refreshMarkers);

  on("ready", async () => {
    try {
      const data = await api("/api/cities");
      addCities(data.cities);
    } catch (error) {
      ET.showStatus("Couldn't load the cities. " + error.message);
    }
  });

  ET.openCity = openCity;
  ET.formatPopulation = formatPopulation;
})();
