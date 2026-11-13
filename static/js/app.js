// EuropeTravel: map setup. Filters, regions and cities are added in later phases.
const map = L.map("map", { minZoom: 3, maxZoom: 16 }).setView([52, 12], 4);

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png", {
  subdomains: "abcd",
  maxZoom: 20,
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors ' +
    '&copy; <a href="https://carto.com/attributions">CARTO</a>',
}).addTo(map);
