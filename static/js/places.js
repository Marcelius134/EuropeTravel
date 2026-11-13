// EuropeTravel, phase 3: place pins on the map and the place list in the city card.
(function () {
  "use strict";

  const ET = window.ET;
  const { map, on, h } = ET;

  const KINDS = {
    historic: "Historic site",
    museum: "Museum",
    beach: "Beach",
    nature: "Nature",
    viewpoint: "Viewpoint",
    food: "Food and drink",
    other: "Place",
  };

  // 16 x 16 glyphs, drawn with the current text colour.
  const GLYPHS = {
    historic: '<path fill="currentColor" d="M2.5 6 8 2.5 13.5 6v1h-11zM4 8h1.6v4H4zm3.2 0h1.6v4H7.2zm3.2 0H12v4h-1.6zM2.5 13h11v1.2h-11z"/>',
    museum: '<path fill="none" stroke="currentColor" stroke-width="1.4" d="M2.7 2.7h10.6v10.6H2.7z"/><path fill="currentColor" d="m4.5 11 2.2-3 1.6 1.8 1.2-1.3 2 2.5z"/>',
    beach: '<path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" d="M2 6.2c1.5-1.4 2.5-1.4 4 0s2.5 1.4 4 0 2.5-1.4 4 0M2 10.4c1.5-1.4 2.5-1.4 4 0s2.5 1.4 4 0 2.5-1.4 4 0"/>',
    nature: '<path fill="currentColor" d="m1.5 13 4.6-8 2.4 4 1.5-2.2L14.5 13z"/>',
    viewpoint: '<path fill="none" stroke="currentColor" stroke-width="1.4" d="M1.6 8s2.4-4 6.4-4 6.4 4 6.4 4-2.4 4-6.4 4-6.4-4-6.4-4z"/><circle cx="8" cy="8" r="1.9" fill="currentColor"/>',
    food: '<path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" d="M5 2v12M3.3 2v3a1.7 1.7 0 0 0 3.4 0V2M10.6 14V2c2.2 1.2 2.6 4.2 2 7h-2"/>',
    other: '<circle cx="8" cy="8" r="3" fill="currentColor"/>',
  };

  function glyph(category) {
    return '<svg viewBox="0 0 16 16" aria-hidden="true">' + (GLYPHS[category] || GLYPHS.other) + "</svg>";
  }

  let pins = {}; // place id -> { marker, item }
  let activeId = null;

  function setActive(id, options) {
    if (activeId && pins[activeId]) {
      pins[activeId].item.classList.remove("is-active");
      const oldPin = pins[activeId].marker.getElement();
      if (oldPin) oldPin.firstElementChild.classList.remove("is-active");
      pins[activeId].marker.setZIndexOffset(0);
    }
    activeId = id;
    if (!id || !pins[id]) return;
    const { marker, item } = pins[id];
    item.classList.add("is-active");
    const pin = marker.getElement();
    if (pin) pin.firstElementChild.classList.add("is-active");
    marker.setZIndexOffset(1000);
    if (options && options.scrollList) item.scrollIntoView({ block: "nearest", behavior: "smooth" });
    if (options && options.panMap && !map.getBounds().pad(-0.15).contains(marker.getLatLng())) {
      ET.focusOn(marker.getLatLng(), map.getZoom());
    }
  }

  function clearPins() {
    Object.values(pins).forEach(({ marker }) => map.removeLayer(marker));
    pins = {};
    activeId = null;
  }

  // The list goes into the city card as it is built...
  on("city:render", ({ city, body }) => {
    clearPins();
    if (!city.places || city.places.length === 0) return;
    const items = city.places.map((place) => {
      const item = h(
        "li",
        {},
        h(
          "button",
          {
            type: "button",
            onclick: () => setActive(place.id, { panMap: true }),
            onmouseenter: () => setActive(place.id),
            onfocus: () => setActive(place.id),
          },
          h("span", { class: "place-list__icon" }),
          h(
            "span",
            {},
            h("span", { class: "place-list__name" }, place.name),
            h("span", { class: "place-list__kind" }, KINDS[place.category] || KINDS.other),
            place.description && h("span", { class: "place-list__text" }, place.description)
          )
        )
      );
      item.querySelector(".place-list__icon").innerHTML = glyph(place.category);
      pins[place.id] = { item, marker: null };
      return item;
    });
    const section = h(
      "section",
      { "data-section": "places" },
      h("h3", {}, "Places to see and things to do"),
      h("ul", { class: "place-list" }, items)
    );
    const creditIndex = body.findIndex((node) => node.dataset && node.dataset.section === "credit");
    body.splice(creditIndex === -1 ? body.length : creditIndex, 0, section);

    if (city.places.some((place) => place.source === "curated-estimate")) {
      body.push(h("p", { class: "fineprint" }, "Pin positions here were placed by hand and can be a street or two off."));
    } else if (creditIndex === -1) {
      body.push(
        h(
          "p",
          { class: "fineprint" },
          "Places from ",
          h("a", { href: "https://en.wikivoyage.org/wiki/" + encodeURIComponent(city.name), target: "_blank", rel: "noopener" }, "Wikivoyage"),
          ", CC BY-SA."
        )
      );
    }
  });

  // ...and the pins go on the map once the card is open.
  on("city:opened", ({ city }) => {
    if (!city.places || city.places.length === 0) return;
    const points = [];
    city.places.forEach((place) => {
      const marker = L.marker([place.lat, place.lon], {
        pane: "places",
        title: place.name,
        alt: place.name + ", " + (KINDS[place.category] || KINDS.other),
        keyboard: true,
        icon: L.divIcon({
          className: "place-marker",
          html: '<div class="place-pin">' + glyph(place.category) + "</div>",
          iconSize: [30, 30],
          iconAnchor: [15, 15],
        }),
      });
      marker.bindTooltip(place.name, { className: "map-tip", direction: "top", offset: [0, -14] });
      marker.on("click", () => setActive(place.id, { scrollList: true }));
      marker.on("mouseover", () => setActive(place.id));
      marker.addTo(map);
      pins[place.id].marker = marker;
      points.push([place.lat, place.lon]);
    });
    points.push([city.lat, city.lon]);
    // Frame the city and all of its pins in the part of the map the card leaves free.
    map.stop();
    map.flyToBounds(L.latLngBounds(points), {
      paddingTopLeft: ET.isNarrow() ? [30, 30] : [440, 60],
      paddingBottomRight: ET.isNarrow() ? [30, window.innerHeight * 0.72 + 20] : [60, 60],
      maxZoom: 15,
      duration: 0.8,
    });
  });

  on("city:closed", clearPins);
})();
