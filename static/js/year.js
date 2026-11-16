// EuropeTravel: "best months" in the region card.
// Shows how well the open region fits the chosen filters in each month of the year.
(function () {
  "use strict";

  const ET = window.ET;
  const { state, on, h, api } = ET;

  // Turn month numbers into words: [6, 7, 8, 10] -> "June to August and October".
  function describeMonths(months, names) {
    if (months.length === 12) return "all year";
    const runs = [];
    months.forEach((month) => {
      const last = runs[runs.length - 1];
      if (last && last[1] === month - 1) last[1] = month;
      else runs.push([month, month]);
    });
    // December and January are neighbours, so join a run that ends the year to one that starts it.
    if (runs.length > 1 && runs[0][0] === 1 && runs[runs.length - 1][1] === 12) {
      runs[0][0] = runs.pop()[0];
      runs.push(runs.shift());
    }
    const parts = runs.map(([from, to]) => (from === to ? names[from - 1] : names[from - 1] + " to " + names[to - 1]));
    if (parts.length === 1) return parts[0];
    return parts.slice(0, -1).join(", ") + " and " + parts[parts.length - 1];
  }

  function caption(scores) {
    const names = state.meta.months;
    const fitting = scores.map((score, index) => (score >= state.threshold ? index + 1 : null)).filter(Boolean);
    if (fitting.length === 12) return "Fits all year round.";
    if (fitting.length > 0) return "Fits in " + describeMonths(fitting, names) + ".";
    const best = Math.max(...scores);
    const bestMonth = names[scores.indexOf(best)];
    return "No month reaches your " + state.threshold + "% line. The closest is " + bestMonth + ", at " + best + "%.";
  }

  function chart(scores) {
    const names = state.meta.months;
    return h(
      "div",
      { class: "year", role: "group", "aria-label": "Fit in each month" },
      scores.map((score, index) => {
        const month = index + 1;
        const chosen = state.month === month;
        return h(
          "button",
          {
            type: "button",
            class: "year__month" + (score >= state.threshold ? " is-fit" : ""),
            "aria-pressed": String(chosen),
            "aria-label": names[index] + ": " + score + "% fit",
            title: names[index] + ": " + score + "% fit",
            onclick: () => ET.toggleMonth(month),
          },
          h("span", { class: "year__bar" }, h("i", { style: "height:" + Math.max(4, score) + "%" })),
          h("span", { class: "year__letter" }, names[index].slice(0, 1))
        );
      })
    );
  }

  let request = 0;
  async function fill(section, regionId) {
    const mine = ++request;
    let data;
    try {
      data = await api("/api/regions/" + regionId + "/year", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filters: state.filters }),
      });
    } catch (error) {
      section.replaceChildren(h("h3", {}, "Best months"), h("p", { class: "fineprint" }, "Couldn't work out the best months. " + error.message));
      return;
    }
    if (mine !== request || !section.isConnected) return; // the card moved on while we waited
    if (data.scores.some((score) => score === null)) {
      section.remove(); // the fit box above already says which data is missing
      return;
    }
    section.replaceChildren(
      h("h3", {}, "Best months"),
      chart(data.scores),
      h("p", { class: "chart__caption" }, caption(data.scores)),
      h("p", { class: "fineprint" }, state.month ? "Choose the month again to go back to summer." : "Choose a month to see the region then.")
    );
  }

  on("region:render", ({ region, body }) => {
    if (!ET.hasFilters() || !region.climate) return;
    const seasonal = state.meta.filters.some((filter) => filter.seasonal && state.filters[filter.name]);
    if (!seasonal) return; // the other filters are the same in every month
    const section = h(
      "section",
      { "data-section": "year" },
      h("h3", {}, "Best months"),
      h("p", { class: "fineprint" }, "Working out the best months…")
    );
    const fitIndex = body.findIndex((node) => node.classList && node.classList.contains("fit"));
    body.splice(fitIndex + 1, 0, section);
    // The section joins the page when the drawer opens, just after this event.
    setTimeout(() => fill(section, region.id), 0);
  });

  ET.describeMonths = describeMonths;
})();
