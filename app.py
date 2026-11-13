"""EuropeTravel web application.

Run locally with:  flask run   (or: python app.py)
"""
from flask import Flask, jsonify, render_template, request

import matcher
from store import Store


def city_brief(city):
    """The few fields the map and the city lists need."""
    return {
        "id": city["id"],
        "name": city["name"],
        "region_id": city["region_id"],
        "lat": city["lat"],
        "lon": city["lon"],
        "population": city["population"],
        "has_notes": bool(city["summary"]),
    }


def region_payload(region, month=None, cities=()):
    """Everything the region card shows."""
    values = {name: matcher.feature_value(region, name, month) for name in matcher.FILTERS}
    return {
        "id": region["id"],
        "name": region["name"],
        "country_name": region["country_name"],
        "centroid": region["centroid"],
        "summary": region["summary"] or matcher.describe(region),
        "summary_is_generated": region["summary"] is None,
        "highlights": region["highlights"],
        "climate": region["climate"],
        "levels": {
            name: {
                "label": matcher.FILTERS[name]["label"],
                "value": None if value is None else round(value, 2),
                "level": matcher.level_of(value),
                "level_label": matcher.FILTERS[name]["levels"].get(matcher.level_of(value)),
            }
            for name, value in values.items()
        },
        "sources": region["sources"],
        "cities": [city_brief(city) for city in cities],
    }


def create_app(store=None):
    app = Flask(__name__)
    app.json.sort_keys = False
    store = store or Store()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "regions": len(store.regions)})

    @app.get("/api/meta")
    def meta():
        """What the filter panel needs to draw itself."""
        return jsonify({
            "filters": [
                {"name": name, "label": spec["label"], "levels": spec["levels"], "seasonal": spec["seasonal"]}
                for name, spec in matcher.FILTERS.items()
            ],
            "months": matcher.MONTH_NAMES,
            "default_threshold": matcher.DEFAULT_THRESHOLD,
            "region_count": len(store.regions),
        })

    @app.post("/api/match")
    def match():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "Send a JSON object with 'filters' and an optional 'month'."}), 400
        try:
            results = matcher.score_all(store.regions, body.get("filters", {}), body.get("month"))
        except matcher.FilterError as error:
            return jsonify({"error": str(error)}), 400
        return jsonify({"results": results})

    @app.get("/api/regions")
    def region_list():
        """Names for tooltips and the results list."""
        return jsonify({
            "regions": [
                {"id": region["id"], "name": region["name"], "country_name": region["country_name"]}
                for region in store.regions
            ]
        })

    @app.get("/api/regions/<region_id>")
    def region_detail(region_id):
        region = store.region(region_id.upper())
        if region is None:
            return jsonify({"error": f"No region with id '{region_id}'."}), 404
        month = request.args.get("month", type=int)
        if month is not None and not 1 <= month <= 12:
            return jsonify({"error": "'month' must be a number from 1 to 12."}), 400
        return jsonify(region_payload(region, month, store.cities_in(region["id"])))

    @app.get("/api/cities")
    def city_list():
        """Every city, briefly, for the dots on the map."""
        return jsonify({"cities": [city_brief(city) for city in store.cities]})

    @app.get("/api/cities/<city_id>")
    def city_detail(city_id):
        city = store.city(city_id.lower())
        if city is None:
            return jsonify({"error": f"No city with id '{city_id}'."}), 404
        region = store.region(city["region_id"])
        return jsonify({
            **city,
            "region_name": region["name"],
            "country_name": region["country_name"],
            "places": store.places_in(city["id"]),
        })

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
