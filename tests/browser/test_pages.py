"""What a visitor does on the page, checked in a real browser."""
import re

from playwright.sync_api import expect


def choose(page, *labels):
    """Press filter or month buttons by their text."""
    for label in labels:
        page.locator(".segments button, .months button").get_by_text(label, exact=True).click()


def state(page, expression):
    return page.evaluate("() => window.ET.state." + expression)


def open_page(context, base_url, query):
    page = context.new_page()
    page.goto(base_url + "/" + query, wait_until="domcontentloaded")
    page.wait_for_selector(".segments button")
    return page


# ---------- Filters and the map ----------

def test_the_page_starts_with_six_filters_and_nothing_lit(page):
    expect(page.locator(".filter")).to_have_count(6)
    expect(page.locator(".months button")).to_have_count(12)
    expect(page.locator("#results")).to_contain_text("Nothing chosen yet")
    assert page.locator(".leaflet-glow-pane path").count() == 0
    assert page.locator(".leaflet-overlay-pane path").count() > 300  # one outline per region or island


def test_choosing_filters_lights_regions_and_lists_them(page):
    choose(page, "Hot", "Seaside")
    expect(page.locator(".results__count")).to_contain_text(re.compile(r"\d+ regions fit"))
    assert page.locator(".leaflet-glow-pane path").count() > 0
    expect(page.locator(".results__list button").first).to_contain_text("100%")
    expect(page.locator("#clear-filters")).to_be_visible()


def test_pressing_a_filter_again_turns_it_off(page):
    choose(page, "Seaside")
    expect(page.locator(".results__count")).to_be_visible()
    choose(page, "Seaside")
    expect(page.locator("#results")).to_contain_text("Nothing chosen yet")
    assert state(page, "filters") == {}


def test_a_higher_fit_line_lights_fewer_regions(page):
    choose(page, "Mild", "Some coast", "Rich")
    expect(page.locator(".results__count")).to_be_visible()
    before = page.locator(".leaflet-glow-pane path").count()
    page.locator("#threshold").fill("95")
    expect(page.locator("#threshold-value")).to_have_text("95%")
    assert page.locator(".leaflet-glow-pane path").count() < before


def test_regions_without_data_are_counted_not_hidden(page):
    choose(page, "Hot")
    expect(page.locator("#results")).to_contain_text("regions have no data yet")


# ---------- Region, city and places ----------

def test_a_region_card_explains_the_fit_and_the_best_months(page):
    choose(page, "Hot", "Seaside")
    page.locator(".results__list button").first.click()
    expect(page.locator("#drawer")).to_be_visible()
    expect(page.locator(".fit__score")).to_contain_text("% fit")
    expect(page.locator(".fit__row")).to_have_count(2)
    expect(page.locator(".year__month")).to_have_count(12)
    expect(page.locator('[data-section="year"] .chart__caption')).to_contain_text("Fits")
    expect(page.locator(".chart svg")).to_be_visible()


def test_choosing_a_month_bar_switches_the_month(page):
    choose(page, "Hot")
    page.locator(".results__list button").first.click()
    page.locator(".year__month").nth(0).click()
    expect(page.locator("#month-note")).to_contain_text("January")
    expect(page.locator('.year__month[aria-pressed="true"]')).to_have_attribute("aria-label", re.compile("January"))
    assert state(page, "month") == 1


def test_best_months_are_left_out_when_no_filter_depends_on_the_month(page):
    choose(page, "Seaside")
    page.locator(".results__list button").first.click()
    expect(page.locator(".fit__score")).to_be_visible()
    expect(page.locator('[data-section="year"]')).to_have_count(0)


def test_a_city_card_lists_places_and_pins_them(context, base_url):
    page = open_page(context, base_url, "?region=ES61")
    page.locator(".city-list button", has_text="Seville").click()
    expect(page.locator("#drawer-title")).to_have_text("Seville")
    expect(page.locator(".place-list li").first).to_be_visible()
    assert page.locator(".place-pin").count() == page.locator(".place-list li").count()
    page.locator(".place-list button").first.hover()
    expect(page.locator(".place-pin.is-active")).to_have_count(1)
    page.locator("#drawer-back").click()
    expect(page.locator("#drawer-title")).to_have_text("Andalusia")
    expect(page.locator(".place-pin")).to_have_count(0)


def test_escape_closes_the_card(context, base_url):
    page = open_page(context, base_url, "?region=ES61")
    expect(page.locator("#drawer")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator("#drawer")).to_be_hidden()
    assert state(page, "selected") is None


# ---------- Base map and theme ----------

def test_city_names_are_not_drawn_twice(context, base_url):
    # Every base map prints city names itself, so ours appear only on hover.
    page = open_page(context, base_url, "?region=ES61")
    expect(page.locator(".city-list button").first).to_be_visible()
    for name in ("dark", "terrain", "satellite"):
        page.locator(f'.basemaps button[data-basemap="{name}"]').click()
        expect(page.locator(".city-label")).to_have_count(0)


def test_the_warm_theme_is_remembered(page):
    expect(page.locator("html")).not_to_have_attribute("data-theme", "warm")
    page.locator('.themes button[data-theme-choice="warm"]').click()
    expect(page.locator("html")).to_have_attribute("data-theme", "warm")
    page.reload(wait_until="domcontentloaded")
    expect(page.locator("html")).to_have_attribute("data-theme", "warm")
    expect(page.locator('.themes button[data-theme-choice="warm"]')).to_have_attribute("aria-pressed", "true")
    page.locator('.themes button[data-theme-choice="night"]').click()
    expect(page.locator("html")).not_to_have_attribute("data-theme", "warm")


# ---------- Compare ----------

def pick_for_comparison(page, position):
    page.locator(".results__list button").nth(position).click()
    button = page.locator('#drawer-actions [data-action="compare"]')
    expect(button).to_have_attribute("aria-pressed", "false")
    button.click()
    expect(page.locator('#drawer-actions [data-action="compare"]')).to_have_attribute("aria-pressed", "true")


def test_comparing_regions_side_by_side(page):
    choose(page, "Hot", "Seaside", "Jul")
    pick_for_comparison(page, 0)
    expect(page.locator("#compare-tray")).to_contain_text("Add one more region")
    pick_for_comparison(page, 2)
    page.locator(".tray__go").click()
    expect(page.locator("#compare")).to_be_visible()
    expect(page.locator(".compare__name")).to_have_count(2)
    expect(page.locator(".compare__fit")).to_have_count(2)
    expect(page.locator(".compare__label", has_text="Best months")).to_be_visible()
    # The table follows the month chosen on the right.
    choose(page, "Jan")
    expect(page.locator(".compare__label", has_text="Temperature")).to_contain_text("January")
    page.keyboard.press("Escape")
    expect(page.locator("#compare")).to_be_hidden()
    expect(page.locator("#drawer")).to_be_visible()  # Escape closed the comparison only


def test_no_more_than_three_regions_can_be_compared(page):
    choose(page, "Seaside")
    for position in range(3):
        pick_for_comparison(page, position)
    page.locator(".results__list button").nth(3).click()
    button = page.locator('#drawer-actions [data-action="compare"]')
    expect(button).to_have_attribute("aria-pressed", "false")
    expect(button).to_be_disabled()
    page.locator(".tray__remove").first.click()
    expect(page.locator('#drawer-actions [data-action="compare"]')).to_be_enabled()
    assert len(state(page, "compare")) == 2


# ---------- Saved places ----------

def test_saved_places_survive_a_reload(context, base_url):
    page = open_page(context, base_url, "?region=ES61")
    expect(page.locator("#saved")).to_be_hidden()
    page.locator('#drawer-actions [data-action="save"]').click()
    expect(page.locator('#drawer-actions [data-action="save"]')).to_have_text("Saved")
    page.locator(".city-list button", has_text="Seville").click()
    expect(page.locator("#drawer-title")).to_have_text("Seville")
    page.locator('#drawer-actions [data-action="save"]').click()
    expect(page.locator("#saved-list li")).to_have_count(2)

    page.goto(base_url + "/", wait_until="domcontentloaded")
    expect(page.locator("#saved-list li")).to_have_count(2)
    page.locator(".saved__open", has_text="Seville").click()
    expect(page.locator("#drawer-title")).to_have_text("Seville")
    expect(page.locator('#drawer-actions [data-action="save"]')).to_have_text("Saved")
    # Removing it from the list also resets the button on the open card.
    page.locator('.saved__remove[aria-label*="Seville"]').click()
    expect(page.locator("#saved-list li")).to_have_count(1)
    expect(page.locator('#drawer-actions [data-action="save"]')).to_have_text("Save")


# ---------- Links ----------

def test_the_address_follows_the_view(page):
    choose(page, "Hot", "Seaside", "Jul")
    expect(page.locator(".results__count")).to_be_visible()
    page.locator("#threshold").fill("80")
    page.locator(".results__list button").first.click()
    expect(page.locator("#drawer")).to_be_visible()
    expect(page).to_have_url(re.compile(r"\?temperature=high&coast=high&month=7&fit=80&region=[A-Z0-9]+$"))
    page.locator("#drawer-close").click()
    expect(page).to_have_url(re.compile(r"\?temperature=high&coast=high&month=7&fit=80$"))
    page.locator("#clear-filters").click()
    expect(page).to_have_url(re.compile(r"\?month=7&fit=80$"))


def test_a_link_opens_the_same_view(context, base_url):
    page = open_page(context, base_url, "?temperature=high&coast=high&month=7&fit=80&region=ES61&map=terrain")
    expect(page.locator("#drawer-title")).to_have_text("Andalusia")
    expect(page.locator(".fit__score")).to_contain_text("% fit")
    assert state(page, "filters") == {"temperature": "high", "coast": "high"}
    assert state(page, "month") == 7
    assert state(page, "threshold") == 80
    assert state(page, "basemap") == "terrain"
    expect(page.locator('.segments button[data-filter="temperature"][data-level="high"]')).to_have_attribute("aria-pressed", "true")


def test_a_link_to_a_city_and_a_comparison(context, base_url):
    page = open_page(context, base_url, "?city=seville-es&compare=ES61,EL30")
    expect(page.locator("#drawer-title")).to_have_text("Seville")
    expect(page.locator(".tray__chip")).to_have_count(2)
    page = open_page(context, base_url, "?compare=ES61,EL30&show=compare")
    expect(page.locator(".compare__name")).to_have_count(2)


def test_a_broken_link_still_opens_the_page(context, base_url):
    page = open_page(context, base_url, "?region=ZZ99&month=13&fit=abc&coast=sideways&compare=ES61,NOPE,ES61&temperature=high")
    expect(page.locator(".results__count")).to_be_visible()
    assert state(page, "filters") == {"temperature": "high"}
    assert state(page, "month") is None
    assert state(page, "threshold") == 70
    assert state(page, "compare") == ["ES61"]
    expect(page.locator("#drawer")).to_be_hidden()
    expect(page).to_have_url(re.compile(r"\?temperature=high&compare=ES61$"))


# ---------- When things go wrong ----------

def test_a_server_that_stops_answering_is_explained(page):
    page.route("**/api/match", lambda route: route.abort())
    choose(page, "Hot")
    expect(page.locator("#status")).to_contain_text("The server didn't answer")
    page.unroute("**/api/match")
    choose(page, "Seaside")
    expect(page.locator(".results__count")).to_be_visible()
    expect(page.locator("#status")).to_be_hidden()
