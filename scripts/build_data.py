"""Rebuild the data sets the app reads.

Usage:
    python -m scripts.build_data all          # everything, in order
    python -m scripts.build_data climate      # one step

Steps that download from the internet keep what they fetched in data/cache/,
so a step can be stopped and started again without repeating finished work.
"""
import argparse
import sys

from . import cities, climate, geometry, heritage, merge

STEPS = {
    "boundaries": ("Download NUTS-2 region outlines", geometry.build_boundaries),
    "geometry": ("Area, coast and mountains from the outlines", geometry.build_geometry),
    "cities": ("Cities per region and how built-up each region is", cities.build_settlement_and_cities),
    "climate": ("Monthly temperature and rainfall (about 5 minutes)", climate.build_climate),
    "heritage": ("World Heritage sites and castles from Wikidata", heritage.build_heritage),
    "merge": ("Write data/regions.json and the other app files", merge.build_all_outputs),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild EuropeTravel data.")
    parser.add_argument("steps", nargs="+", choices=[*STEPS, "all"], help="steps to run, or 'all'")
    args = parser.parse_args(argv)
    chosen = list(STEPS) if "all" in args.steps else args.steps
    if "merge" not in chosen:
        chosen.append("merge")

    failures = []
    for name in chosen:
        description, run = STEPS[name]
        print(f"\n== {name}: {description}")
        try:
            run()
        except Exception as error:  # keep going so one broken source does not block the rest
            failures.append(name)
            print(f"{name}: FAILED: {error}")
    if failures:
        print("\nFinished with problems in: " + ", ".join(failures))
        print("The other steps still ran. Fix or retry the failed ones, then run 'merge'.")
        return 1
    print("\nAll steps finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
