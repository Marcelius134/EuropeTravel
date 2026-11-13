"""Loads the JSON data files once and answers lookups for the app."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


class Store:
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = Path(data_dir)
        self.regions = self._read("regions.json")
        self.regions_by_id = {region["id"]: region for region in self.regions}
        self.cities = self._read("cities.json")
        self.cities_by_id = {city["id"]: city for city in self.cities}
        self.cities_by_region = {}
        for city in self.cities:
            self.cities_by_region.setdefault(city["region_id"], []).append(city)

    def _read(self, name):
        path = self.data_dir / name
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def region(self, region_id):
        return self.regions_by_id.get(region_id)

    def city(self, city_id):
        return self.cities_by_id.get(city_id)

    def cities_in(self, region_id):
        return self.cities_by_region.get(region_id, [])
