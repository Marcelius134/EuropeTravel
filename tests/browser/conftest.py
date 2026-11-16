"""Fixtures for the browser tests.

These tests drive a real Chromium through Playwright. They are skipped when
Playwright or its browser is not installed, so plain `pytest` always works:

    pip install -r requirements-browser.txt
    playwright install chromium
"""
import threading

import pytest

playwright_api = pytest.importorskip("playwright.sync_api", reason="Playwright is not installed")


@pytest.fixture(scope="session")
def base_url():
    """Run the real app on a free local port for the whole test session."""
    from werkzeug.serving import make_server

    from app import create_app

    server = make_server("127.0.0.1", 0, create_app(), threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    with playwright_api.sync_playwright() as playwright:
        try:
            chromium = playwright.chromium.launch()
        except Exception as error:  # the package is there but the browser was never downloaded
            pytest.skip(f"Chromium could not start ({error}). Run: playwright install chromium")
        yield chromium
        chromium.close()


def _only_local(route):
    """Let requests to our own server through and drop the rest (map tiles, fonts).

    The tests then need no internet and never wait on someone else's server.
    """
    if route.request.url.startswith("http://127.0.0.1"):
        route.continue_()
    else:
        route.abort()


@pytest.fixture
def context(browser):
    """A clean browser profile per test: nothing saved, default theme."""
    context = browser.new_context(viewport={"width": 1366, "height": 800})
    context.route("**/*", _only_local)
    yield context
    context.close()


@pytest.fixture
def page(context, base_url):
    """An open page on the app that fails the test if the page's own scripts throw."""
    page = context.new_page()
    problems = []
    page.on("pageerror", lambda error: problems.append(str(error)))
    page.goto(base_url + "/", wait_until="domcontentloaded")
    page.wait_for_selector(".segments button")
    yield page
    assert problems == [], "the page's scripts threw errors"
