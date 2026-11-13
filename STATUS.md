# Status

Last updated: 14 November 2026

## Done and working

- Flask app with a JSON API, 70 passing tests
- Dark map of 328 NUTS-2 regions (EU, EFTA, the United Kingdom, Turkey and the western Balkans)
- Filter panel: temperature, rainfall, sea and coast, mountains and wild nature, historic feel, crowds
- Month choice; without one, temperature and rainfall use June to August
- Fit threshold slider (70% by default); regions at or above it glow, brighter for a closer fit
- Region card: fit breakdown per filter, summary, climate chart, cities
- 1,238 city dots; city card with notes and ideas
- Place pins with a matching list; hovering or clicking one highlights the other
- Dark, terrain and satellite base maps
- Layout for phones: the panels become sheets at the bottom
- Data build script with one step per source

## Works, but on estimates until the data build has been run

Run `python -m scripts.build_data all` (see `README.md`) to replace most of these.

| What | Now | After the data build |
|---|---|---|
| Climate | Hand-written monthly figures for 46 regions; the other 282 have none and can't be scored on temperature or rainfall | Measured climate for all regions |
| Historic feel | Hand-written score for the same 46 regions; none for the rest | Wikidata counts for the rest. The 46 keep their hand-written score |
| City notes | Hand-written for 14 cities | Wikivoyage text for every city that has an article |
| Places | 71 hand-written places in 14 cities, positions typed from memory | Wikivoyage listings for other cities. The 14 keep their hand-written places |

The 46 regions and 14 cities with hand-written content are listed in `data/curated/`.

## Not verified

- **The download steps have never run against the real services.** The environment this was built in could only reach GitHub, so `climate`, `heritage` and `places` were written from knowledge of the APIs and tested with made-up sample responses. Expect to fix small things on the first real run. `boundaries`, `geometry` and `cities` did run for real.
- **The page has not been seen with its base map.** Map tiles could not load in that environment either. Outlines, glow, panels and pins were checked in a browser on a blank background; how they look over the real dark, terrain and satellite tiles has not been checked.
- Only Chromium was tried. Firefox and Safari have not been.

## Known limits

- "Mountains and wild nature" is a proxy: the share of the region covered by Natural Earth mountain ranges, plus how thinly settled it is. Forests and lakes are not measured, so Finland or the Scottish Highlands score lower than they should unless hand-written.
- "Crowds" is the population living in towns over 15,000 per km². It ignores tourists, so a quiet region with a busy summer coast reads as quiet.
- The Wikidata heritage score counts World Heritage sites and castles. Larger regions have more of both.
- GeoNames sometimes lists a suburb or beach as a city (for example "Acilia-Castel Fusano-Ostia Antica" in Lazio).
- Region names are Eurostat's, in the local language, except for the 46 with hand-written English names.
- The Canary Islands and the French overseas regions are not in the outline file used.
- Region outlines are simplified, so a coastal pin can sit slightly outside its region.
- Git tags `v0.1-scaffold` to `v0.4-phase3` exist only in the build environment; see the commit list below to recreate them.

## Ideas for what to do next

- Run the data build and review what it produces
- An activity filter (beach, culture, hiking, skiing, food)
- Free-text search that fills in the filters
- Tourism nights from Eurostat for a better crowd score
- Forest cover for a better nature score
- English names for all regions
- A screenshot in the README

## Commits

| Commit | Contents |
|---|---|
| `8414f2e` | Skeleton, base map, docs |
| `885f174` | Phase 1: regions, filters, matching, glow |
| `f0b0ae3` | Phase 2: cities |
| `793ea21` | Phase 3: places |

To go back to any of them: `git checkout <commit>`. To tag them:

```bash
git tag v0.1-scaffold 8414f2e
git tag v0.2-phase1 885f174
git tag v0.3-phase2 f0b0ae3
git tag v0.4-phase3 793ea21
git push --tags
```
