# Tasks for the team

Each task below is written so it can be pasted into a GitHub issue as it is. They are independent unless "Needs" says otherwise, so four people can work at once. Pick by size: S is an afternoon, M is a few days, L is a week or more.

| # | Task | Size | Area |
|---|---|---|---|
| 1 | Run the data build and review the result | S, plus waiting | Data |
| 2 | Try the start script on Windows | S | Setup |
| 3 | Check the page in other browsers and screen sizes | S | Interface |
| 4 | Retake the README screenshots with the real map | S | Docs |
| 5 | English names for every region | M | Data |
| 6 | Write notes and places for more cities | S each | Content |
| 7 | Mark compared and saved regions on the map | M | Interface |
| 8 | Prepare the demo | S | Presentation |
| 9 | Tourist nights for a truer "Crowds" filter | M | Data |
| 10 | Forest and lake cover for a truer "nature" filter | M to L | Data |
| 11 | Activity filter | L | Data and interface |
| 12 | Turkish interface with a language switch | M | Interface |
| 13 | Decide what to do with the phone layout | S | Interface |
| 14 | Search by typing a sentence | L | Later |

Do task 1 first. Tasks 2 to 4 are good first commits.

---

## 1. Run the data build and review the result

**Why.** The repository ships with hand-written climate for 46 regions. The other 282 cannot be scored on temperature or rainfall, so most of the map stays dark when those filters are on. The download steps exist but have never run against the real services.

**What to do.**
1. `pip install -r requirements-data.txt`
2. `python -m scripts.build_data all`. Expect 20 to 30 minutes. It can be stopped and started again.
3. If a step prints `FAILED`, read the message. Fix the script if the service answered in a shape the parser did not expect, then run that step again, for example `python -m scripts.build_data climate`.
4. Run `pytest`, start the app and spot-check ten regions you know: is July in Seville hot, is Bergen rainy?
5. Commit the changed files under `data/` (not `data/cache/`), and update the table in `STATUS.md`.

**Where.** `scripts/climate.py`, `scripts/heritage.py`, `scripts/places.py`, `scripts/common.py`.

**Done when.** Every region has climate, `pytest` passes, and `STATUS.md` no longer says the downloads are unverified.

**Watch for.** Wikidata sometimes times out on the castle list; the step then ranks on World Heritage sites alone and says so. Run it again later.

---

## 2. Try the start script on Windows

**Why.** `run.bat` was written on Linux and has never run.

**What to do.** Delete the `venv` folder if there is one. Double-click `run.bat`. It should create `venv`, install the packages, start the app and open the browser. Try it a second time (it should start faster). Try it from a folder whose path contains a space. Fix what breaks.

**Where.** `run.bat`, the "Run it" section of `README.md`.

**Done when.** A teammate who has never run the project gets the page open by double-clicking, on their own computer.

---

## 3. Check the page in other browsers and screen sizes

**Why.** Only Chromium was used while building. The demo laptop may run something else.

**What to do.** Open the app in Firefox and Edge (and Safari if someone has a Mac). Go through: filters, region card, best months, city card with pins, compare, save, copy link, both themes, all three base maps. Repeat at a browser width of about 1280 pixels and with the browser zoomed to 125%. Use only the keyboard for one pass: Tab, Enter, Escape. Write each problem as its own issue with a screenshot; fix the small ones.

**Where.** `static/css/style.css`, `static/js/`.

**Done when.** `STATUS.md` lists which browsers were checked, and the problems found are fixed or filed.

---

## 4. Retake the README screenshots with the real map

**Why.** The pictures in `docs/screenshots/` were taken where map tiles could not load, so the background is empty.

**What to do.** Run the app with internet. At a window about 1366 pixels wide, open each address below, take a picture of the page and replace the file of that name in `docs/screenshots/`.

| File | Address after `http://127.0.0.1:5000/` |
|---|---|
| `1-filters.png` | `?temperature=high&coast=high&month=7` |
| `2-region.png` | `?temperature=high&coast=high&region=ES61` |
| `3-city.png` | `?city=seville-es` |
| `4-compare.png` | `?temperature=high&coast=high&month=7&compare=ES61,EL30,HR03&show=compare` |
| `5-warm-theme.png` | `?temperature=medium&nature=high&region=AT33`, with the sun button pressed |

**Done when.** The README shows the map behind the regions.

---

## 5. English names for every region

**Why.** Only the 46 hand-written regions have English names. The rest show Eurostat's local-language names, such as "Piemonte" for Piedmont or "Oberbayern" for Upper Bavaria.

**What to do.**
1. Write `scripts/names.py`. Wikidata has the NUTS code of each region as property P605. One SPARQL query can return the English label for every item that has a NUTS-2 code.
2. Save the answer as `data/computed/names.json`: `{"ITC1": "Piedmont", ...}`.
3. Register the step in `scripts/build_data.py`.
4. In `scripts/merge.py`, use the name in this order: hand-written, Wikidata, Eurostat.
5. Tests: a parsing test with a made-up answer, and a merge test for the order.

**Where.** `scripts/heritage.py` is the model: it already queries Wikidata and parses the answer.

**Done when.** No region in the results list has a name with non-English spelling where a common English name exists, and `pytest` passes.

**Watch for.** NUTS codes changed between the 2016, 2021 and 2024 versions. The project uses 2021. Some regions will have no match; leave their Eurostat name and print how many.

---

## 6. Write notes and places for more cities

**Why.** 14 cities have hand-written notes and 71 places between them. Wikivoyage will fill in many others after task 1, but the best-known cities deserve checked text and pins in the right spot.

**What to do.** Pick five cities you know or can research. For each, add to `data/curated/cities.json` a two-sentence summary and three or four "things to do", and to `data/curated/places.json` five to eight places with a category, a one-sentence description and coordinates. Take the coordinates from a map, not from memory. Then run `python -m scripts.build_data merge` and `pytest`.

**Where.** `data/curated/`. `SCHEMA.md` lists the fields and the allowed categories.

**Done when.** The five cities open with notes and pins that sit on the right buildings at street zoom.

**Watch for.** The existing 71 places had their coordinates typed from memory. Correcting those is part of this task.

---

## 7. Mark compared and saved regions on the map

**Why.** Regions in the comparison tray and saved regions look like any other region on the map.

**What to do.** Give regions in `ET.state.compare` a distinct outline, and saved regions a small marker or outline. Update when `compare:changed` or `saved:changed` fires. Keep the gold glow meaning "fits your filters" and nothing else.

**Where.** `regionStyle` in `static/js/app.js`; `compare.js`; `saved.js`.

**Done when.** A visitor can find their compared and saved regions on the map without opening a list, in both themes and on all three base maps, and a browser test covers it.

---

## 8. Prepare the demo

**Why.** The project is shown running on a laptop.

**What to do.** Write a five-minute path through the app in `docs/demo.md`: which filters, which region, which city, the comparison, the link. Use regions that have real data. Rehearse it on the laptop that will be used, on the network that will be used. Have a phone hotspot ready: without internet the base map is empty.

**Done when.** Two team members can each give the demo without notes.

---

## 9. Tourist nights for a truer "Crowds" filter

**Why.** "Crowds" is the share of people living in towns. A quiet region with a packed summer coast reads as quiet.

**What to do.** Eurostat publishes nights spent at tourist accommodation by NUTS-2 region (dataset `tour_occ_nin2`), free and without a key. Download it, divide by area or by residents, rank the regions and blend the rank into `crowd`. Turkey and the United Kingdom may be missing; keep the current measure for those and record the source per region.

**Where.** New `scripts/tourism.py`; `scripts/merge.py`; the "Crowds" row in `SCHEMA.md`.

**Done when.** The Algarve, the Balearic Islands and South Aegean come out "Busy", and `sources.crowd` says where each region's value came from.

---

## 10. Forest and lake cover for a truer "nature" filter

**Why.** "Mountains and wild nature" measures mountains and thin settlement. Flat forests and lake districts, such as Finland, score too low.

**What to do.** Find a free land-cover source that can be summarised per region. Eurostat's LUCAS survey has land cover by NUTS-2 as a table, which avoids processing large map files; CORINE Land Cover is the detailed alternative. Add forest and water share to the measure in `scripts/merge.py` (`nature_proxy`) and choose the weights by checking twenty regions you can judge.

**Done when.** Finnish and Swedish lake regions and the Scottish Highlands come out "Wild", the Po plain and the Netherlands do not, and the rule is described in `SCHEMA.md`.

---

## 11. Activity filter

**Why.** Travellers think in activities: beach, hiking, skiing, culture, food.

**What to do.** Decide as a team first: how many activities, and whether a region either has an activity or has it to a degree. Then find a source for each. Beaches can come from the coast measure plus summer temperature; skiing from mountains plus winter temperature; culture from the heritage score. Hiking and food need a new source or hand-written tags. Add the filter to `matcher.py` and design how it sits in the panel, which is already long.

**Needs.** Task 1, because several activities depend on climate.

**Done when.** A visitor can choose an activity and the lit regions make sense to all four of you.

---

## 12. Turkish interface with a language switch

**Why.** The team and the audience are in Turkey; the interface is English only.

**What to do.** Move every visible string into one dictionary per language. Strings live in three places: `matcher.py` (filter and level names, month names, generated summaries), `templates/index.html`, and the `static/js/` files. Add a switch next to the theme buttons and remember the choice the way the theme is remembered. Region summaries and place descriptions are data, not interface; leave them in English and say so.

**Done when.** Every label, button and message changes with the switch, and the browser tests pass in English.

---

## 13. Decide what to do with the phone layout

**Why.** An early phone layout is still in the stylesheet, but compare, saved places and the tray were built for a laptop only.

**What to do.** Either remove the `@media (max-width: 820px)` block and the `isNarrow()` branches and say "desktop only" in the README, or bring the newer features up to it. Removing is the small option.

**Done when.** The code and the README agree about phones.

---

## 14. Search by typing a sentence

**Why.** "Somewhere warm and quiet by the sea in May" is how people ask.

**What to do.** Start without any AI: match words to filters ("warm", "hot" to temperature high; "quiet" to crowds low; month names to the month) and fill the panel from the sentence. Show what was understood so the visitor can correct it. Only if that proves too weak, consider a language model, which brings an API key, a cost and a network dependency to the demo.

**Needs.** Nothing, but do it last.

**Done when.** Ten example sentences written by someone outside the team set the filters the way that person meant.
