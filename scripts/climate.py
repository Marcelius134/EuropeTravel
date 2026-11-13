"""Monthly climate for every region.

Primary source: NASA POWER climatology (30-year monthly means, one small
request per region). If that fails for a region, the script falls back to
the Open-Meteo historical archive and averages three recent years.

Both are free and need no API key.
  https://power.larc.nasa.gov/docs/services/api/temporal/climatology/
  https://open-meteo.com/en/docs/historical-weather-api
"""
import time

from .common import CACHE, COMPUTED, fetch, load_json, save_json

POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
MONTH_KEYS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DAYS_IN_MONTH = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
POWER_MISSING = -900  # POWER marks missing values with -999


def parse_power(payload):
    """Turn a NASA POWER climatology response into our climate object.

    Temperature is the mean daily maximum in degrees C. POWER reports
    precipitation in mm per day, so it is multiplied by the days in the month.
    """
    parameters = payload["properties"]["parameter"]
    temps = [parameters["T2M_MAX"][key] for key in MONTH_KEYS]
    rain_per_day = [parameters["PRECTOTCORR"][key] for key in MONTH_KEYS]
    if any(value is None or value < POWER_MISSING for value in temps + rain_per_day):
        raise ValueError("NASA POWER returned missing values")
    return {
        "temp_max_c": [round(value, 1) for value in temps],
        "precip_mm": [round(value * days) for value, days in zip(rain_per_day, DAYS_IN_MONTH)],
        "source": "nasa-power",
    }


def parse_open_meteo(payload):
    """Turn an Open-Meteo daily archive response into our climate object."""
    daily = payload["daily"]
    temp_sums = [0.0] * 12
    temp_counts = [0] * 12
    rain_sums = [0.0] * 12
    years = set()
    for date, temp, rain in zip(daily["time"], daily["temperature_2m_max"], daily["precipitation_sum"]):
        month = int(date[5:7]) - 1
        years.add(date[:4])
        if temp is not None:
            temp_sums[month] += temp
            temp_counts[month] += 1
        if rain is not None:
            rain_sums[month] += rain
    if not years or any(count == 0 for count in temp_counts):
        raise ValueError("Open-Meteo returned no usable days")
    return {
        "temp_max_c": [round(total / count, 1) for total, count in zip(temp_sums, temp_counts)],
        "precip_mm": [round(total / len(years)) for total in rain_sums],
        "source": "open-meteo",
    }


def fetch_region_climate(region_id, lat, lon):
    try:
        payload = fetch(
            POWER_URL,
            params={
                "parameters": "T2M_MAX,PRECTOTCORR", "community": "AG",
                "latitude": lat, "longitude": lon, "format": "JSON",
            },
            cache_file=CACHE / "climate" / f"{region_id}.power.json",
        )
        return parse_power(payload)
    except (RuntimeError, KeyError, ValueError, TypeError) as power_error:
        payload = fetch(
            OPEN_METEO_URL,
            params={
                "latitude": lat, "longitude": lon,
                "start_date": "2021-01-01", "end_date": "2023-12-31",
                "daily": "temperature_2m_max,precipitation_sum", "timezone": "UTC",
            },
            cache_file=CACHE / "climate" / f"{region_id}.openmeteo.json",
        )
        try:
            return parse_open_meteo(payload)
        except (KeyError, ValueError, TypeError) as meteo_error:
            raise RuntimeError(f"NASA POWER: {power_error}; Open-Meteo: {meteo_error}")


def build_climate(pause_seconds=0.4):
    geometry = load_json(COMPUTED / "geometry.json")
    if geometry is None:
        raise RuntimeError("data/computed/geometry.json is missing. Run the 'geometry' step first.")
    result = load_json(COMPUTED / "climate.json", {})
    failed = []
    total = len(geometry)
    for number, (region_id, info) in enumerate(sorted(geometry.items()), start=1):
        if region_id in result:
            continue
        lat, lon = info["centroid"]
        try:
            result[region_id] = fetch_region_climate(region_id, lat, lon)
            print(f"climate: {number}/{total} {region_id} ok ({result[region_id]['source']})")
        except RuntimeError as error:
            failed.append(region_id)
            print(f"climate: {number}/{total} {region_id} FAILED: {error}")
        save_json(COMPUTED / "climate.json", dict(sorted(result.items())))
        time.sleep(pause_seconds)
    print(f"climate: {len(result)} regions have data, {len(failed)} failed")
    if failed:
        print("climate: run the step again to retry: " + ", ".join(failed))
    return result
