// EuropeTravel: keep the page address in step with what is on screen, so a
// copied link opens the same filters, month, region or city for someone else.
//
// Example: /?temperature=high&coast=high&month=7&fit=80&region=ES61
(function () {
  "use strict";

  const ET = window.ET;
  const { state, on } = ET;

  const BASEMAPS = ["dark", "terrain", "satellite"];
  let restoring = true; // don't rewrite the address until it has been read

  function currentParams() {
    const params = new URLSearchParams();
    state.meta.filters.forEach((filter) => {
      if (state.filters[filter.name]) params.set(filter.name, state.filters[filter.name]);
    });
    if (state.month) params.set("month", state.month);
    if (state.threshold !== state.meta.default_threshold) params.set("fit", state.threshold);
    if (state.view === "city" && state.cityId) params.set("city", state.cityId);
    else if (state.view === "region" && state.selected) params.set("region", state.selected);
    if (state.basemap !== "dark") params.set("map", state.basemap);
    if (state.compare && state.compare.length > 0) params.set("compare", state.compare.join(","));
    if (state.compareOpen) params.set("show", "compare");
    return params;
  }

  function syncAddress() {
    if (restoring || !state.meta) return;
    const query = currentParams().toString();
    const address = window.location.pathname + (query ? "?" + query : "");
    if (address !== window.location.pathname + window.location.search) {
      window.history.replaceState(null, "", address);
    }
  }

  ["match:updated", "region:opened", "drawer:closed", "city:opened", "city:closed", "basemap:changed", "compare:changed"].forEach(
    (name) => on(name, syncAddress)
  );

  // Read the address once the map data is in. Anything unknown is skipped, so
  // an old or mistyped link still opens the page.
  async function restore() {
    const params = new URLSearchParams(window.location.search);
    const filters = {};
    state.meta.filters.forEach((filter) => {
      if (params.has(filter.name)) filters[filter.name] = params.get(filter.name);
    });
    const month = Number(params.get("month"));
    const threshold = Number(params.get("fit"));
    try {
      if (Object.keys(filters).length > 0 || params.has("month") || params.has("fit")) {
        await ET.applyState({
          filters,
          month: Number.isInteger(month) ? month : null,
          threshold: params.has("fit") ? threshold : NaN,
        });
      }
      if (BASEMAPS.includes(params.get("map"))) ET.setBasemap(params.get("map"));
      if (params.has("compare")) ET.setCompare(params.get("compare").toUpperCase().split(","));
      const city = params.get("city");
      const region = (params.get("region") || "").toUpperCase();
      if (city) await ET.openCity(city.toLowerCase());
      else if (state.names[region]) await ET.selectRegion(region);
      if (params.get("show") === "compare") ET.openCompare();
    } finally {
      restoring = false;
      syncAddress();
    }
  }

  on("ready", restore);

  // ---------- Copy link ----------

  const copyButton = document.getElementById("copy-link");
  const copyLabel = copyButton.textContent;
  let labelTimer = null;

  function flash(text) {
    copyButton.textContent = text;
    clearTimeout(labelTimer);
    labelTimer = setTimeout(() => {
      copyButton.textContent = copyLabel;
    }, 2500);
  }

  copyButton.addEventListener("click", async () => {
    syncAddress();
    try {
      await navigator.clipboard.writeText(window.location.href);
      flash("Link copied");
    } catch (error) {
      // Some browsers only allow copying on https or localhost.
      flash("Copy the address from the bar at the top");
    }
  });
})();
