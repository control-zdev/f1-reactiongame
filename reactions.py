"""
Precompute F1 race-start times (2021 to date) into static JSON for the React app.

How the time is estimated
    Telemetry is only ~4 samples/second, so a "first sample above X km/h"
    rule is quantised and late. Instead we fit a straight line through the
    first few speed samples of the launch ramp and extrapolate back to
    0 km/h. That gives the moment the car started moving ("launchMs",
    measured from lights out), using several samples instead of one.

    launchMs still contains the clutch-bite delay, so it is larger than a
    pure reaction. reactionMs = launchMs - offset. By default each race gets
    its own offset so that race's median driver lands on TARGET_MEDIAN_MS
    ("race" centring). Grip, track temperature and lights-out timing shift a
    whole grid together, and none of that is reaction time, so centring each
    race removes it and keeps the differences between drivers. Use
    --center global for one shared offset instead.
    Times are kept to 1 ms (3 decimals in seconds) so ties are very rare.
    This avoids ties; it does not mean the data is accurate to 1 ms.

    Realism floor: after centring, any driver faster than MIN_REACTION_MS is
    dropped (status "too_fast"), since no human reacts that quickly to a light.
    Cleaning (automatic, repeatable): races whose median launch is far from
    the rest (rain/rolling starts, bad lights-out timing) get usable=false and
    no reaction times; individual drivers far from their own race median get
    status "outlier" (stalls, pit-lane starts, bad data). Nothing is deleted:
    the original status is kept in rawStatus.

Setup:
    pip install -U fastf1 pandas numpy

Usage:
    python reactions.py                          # all races 2021 to date, clean + auto offset
    python reactions.py --years 2025             # one season
    python reactions.py --recalibrate            # redo offset only, instant, no downloads
    python reactions.py --recalibrate --target-median-ms 190
    python reactions.py --recalibrate --min-reaction-ms 150   # stricter realism floor
    python reactions.py --recalibrate --center global    # one shared offset for all races
    python reactions.py --recalibrate --offset-ms 350    # fixed offset

Output (in ./data, then copied to f1-reaction/public/data for the app):
    2025-abu-dhabi-grand-prix.json   one file per race, all drivers
    index.json                       list of every race, for the year/track picker
"""

import argparse
import datetime
import json
import re
import shutil
import statistics
import time
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd
import requests.models

# Speed fix: FastF1 reads every response body as text, and `requests` guesses the
# encoding by scanning the whole (huge) telemetry payload, which can take minutes.
# F1's feed is always UTF-8 (with a BOM), so tell requests directly and skip the guess.
requests.models.Response.apparent_encoding = property(lambda self: "utf-8-sig")

BASE = Path(__file__).resolve().parent  # paths below work from any folder
OUT_DIR = BASE / "data"
CACHE_DIR = BASE / "cache"
# The React app serves race files from here; every run copies them across.
PUBLIC_DIR = BASE / "f1-reaction" / "public" / "data"

# ---- config -----------------------------------------------------------------
START_YEAR = 2021
END_YEAR = datetime.date.today().year
RAMP_MIN_KMH = 2.0  # first sample at/above this = the car has started moving
RAMP_MAX_KMH = 60.0  # fit the launch ramp up to this speed
MIN_RAMP_POINTS = 3  # need at least this many samples for the line fit
PRE_WINDOW_S = 1.0  # look this far before lights out (jump-start detection)
POST_WINDOW_S = 4.0  # give up if no launch within this long
ROUND_MS = 1  # 1 ms = 3 decimals in seconds
TARGET_MEDIAN_MS = 220  # each race's median driver is set to this
MIN_REACTION_MS = (
    120  # nobody reacts faster than this; quicker times are dropped ("too_fast")
)
BAND_MS = (150, 250)  # realistic F1 reaction band, used for the summary only
SUSPECT_RACE_MS = 100  # list races whose median is this far from the overall median
RACE_EXCLUDE_MS = 500  # race median this far off = not a clean standing start; excluded
DRIVER_OUTLIER_MS = (
    130  # driver this far from their own race median = stall/pit start/bad data
)
MIN_VALID_DRIVERS = 10  # races with fewer valid launches are excluded
# -----------------------------------------------------------------------------


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def round_step(ms: float) -> int:
    return int(round(ms / ROUND_MS)) * ROUND_MS


def data_files():
    """Race JSON files from START_YEAR onwards (ignores index.json and older years)."""
    files = []
    for f in sorted(OUT_DIR.glob("20*-*.json")):
        try:
            if int(f.name[:4]) >= START_YEAR:
                files.append(f)
        except ValueError:
            pass
    return files


def get_lights_out(session):
    """Return (lights_out_seconds, started_count, had_aborted_start)."""
    status = session.session_status
    started = status[status["Status"] == "Started"]
    if started.empty:
        return None, 0, False
    aborted = bool((status["Status"] == "Aborted").any())
    # First "Started" = the grid start. Races with aborted starts / restarts
    # are flagged in the JSON so you can review them by hand.
    return started.iloc[0]["Time"].total_seconds(), len(started), aborted


def launch_time(car, lights_out):
    """Seconds from lights out until the car starts moving (ramp -> 0 km/h).

    Returns (seconds | None, status).
    """
    t = car["SessionTime"].dt.total_seconds().to_numpy()
    v = car["Speed"].to_numpy(dtype=float)

    mask = (t >= lights_out - PRE_WINDOW_S) & (t <= lights_out + POST_WINDOW_S)
    t, v = t[mask], v[mask]

    if len(t) < MIN_RAMP_POINTS + 1:
        return None, "no_data"
    if v[0] >= RAMP_MIN_KMH:
        return None, "already_moving"  # pit-lane start, rolling, or bad data

    above = np.nonzero(v >= RAMP_MIN_KMH)[0]
    if above.size == 0:
        return None, "no_launch"

    start = above[0]  # >= 1 because v[0] is below RAMP_MIN_KMH
    end = start
    while end + 1 < len(v) and v[end + 1] <= RAMP_MAX_KMH:
        end += 1
    end = min(max(end, start + MIN_RAMP_POINTS - 1), len(v) - 1)  # at least N points

    ramp_t, ramp_v = t[start : end + 1], v[start : end + 1]
    if len(ramp_t) < 2:
        return None, "no_launch"

    slope, intercept = np.polyfit(ramp_t, ramp_v, 1)  # v = slope * t + intercept
    if slope <= 0:
        return None, "bad_fit"

    t_zero = -intercept / slope  # time at which the fitted line crosses 0 km/h
    launch = float(t_zero - lights_out)
    return launch, ("jump_start" if launch < 0 else "ok")


def assign_reactions(drivers, offset_ms, usable=True, min_ms=MIN_REACTION_MS):
    """Fill reactionMs / reactionSec (unique per race) and sort fastest first.

    Order always follows the unrounded launchMs. If two drivers still end up
    equal after rounding, the slower one is pushed up by one step.
    Drivers below min_ms are marked "too_fast" and get no time.
    Unusable races get no reaction times at all.
    """
    for d in drivers:
        if d["status"] == "too_fast":
            d["status"] = "ok"  # undo an earlier pass; it is re-checked below
        d["reactionMs"] = None
        d["reactionSec"] = None

    ok = sorted(
        (d for d in drivers if d["status"] == "ok" and usable),
        key=lambda d: d["launchMs"],
    )
    last = None
    for d in ok:
        value = round_step(d["launchMs"] - offset_ms)
        if value < min_ms:
            d["status"] = "too_fast"
            continue
        if last is not None and value <= last:
            value = last + ROUND_MS
        d["reactionMs"] = value
        d["reactionSec"] = round(value / 1000, 3)
        last = value

    drivers.sort(key=lambda d: (d["reactionMs"] is None, d["reactionMs"] or 0))


def process_race(year, event):
    rnd = int(event["RoundNumber"])
    session = fastf1.get_session(year, rnd, "R")
    session.load(laps=True, telemetry=True, weather=False, messages=False)

    lights_out, started_count, aborted = get_lights_out(session)
    if lights_out is None:
        raise RuntimeError("no 'Started' status found")

    drivers = []
    for _, d in session.results.iterrows():
        num = str(d["DriverNumber"])
        car = session.car_data.get(num)
        launch, status = (
            (None, "no_data") if car is None else launch_time(car, lights_out)
        )
        drivers.append(
            {
                "number": num,
                "code": d["Abbreviation"],
                "name": d["FullName"],
                "team": d["TeamName"],
                "grid": None if pd.isna(d["GridPosition"]) else int(d["GridPosition"]),
                "launchMs": None if launch is None else round(launch * 1000),
                "reactionMs": None,
                "reactionSec": None,
                "status": status,
            }
        )

    assign_reactions(drivers, 0)  # offset is applied afterwards by finalize()

    return {
        "year": year,
        "round": rnd,
        "eventName": event["EventName"],
        "location": event["Location"],
        "country": event["Country"],
        "startsDetected": started_count,
        "abortedStartFlag": aborted,
        "method": method_info(0),
        "drivers": drivers,
    }


def method_info(offset_ms, centering="fixed"):
    return {
        "source": "FastF1 car_data",
        "metric": "motion start (launch ramp extrapolated to 0 km/h), from lights out",
        "rampKmh": [RAMP_MIN_KMH, RAMP_MAX_KMH],
        "offsetMs": offset_ms,
        "centering": centering,
        "roundMs": ROUND_MS,
    }


def rebuild_index():
    entries = []
    for f in data_files():
        data = json.loads(f.read_text())
        valid = sum(d["reactionMs"] is not None for d in data["drivers"])
        entries.append(
            {
                "year": data["year"],
                "round": data["round"],
                "eventName": data["eventName"],
                "location": data["location"],
                "country": data["country"],
                "file": f.name,
                "usable": bool(data.get("usable", True)) and valid >= MIN_VALID_DRIVERS,
                "validDrivers": valid,
                "flagged": data["abortedStartFlag"] or data["startsDetected"] > 1,
            }
        )
    (OUT_DIR / "index.json").write_text(json.dumps(entries, indent=2))
    usable = sum(e["usable"] for e in entries)
    print(f"index.json: {len(entries)} races ({usable} usable)")


def overall_median_launch():
    """Median launch over clean drivers in usable races."""
    launches = []
    for f in data_files():
        data = json.loads(f.read_text())
        if not data.get("usable", True):
            continue
        for d in data["drivers"]:
            if d["status"] == "ok" and d.get("launchMs") is not None:
                launches.append(d["launchMs"])
    return statistics.median(launches) if launches else None


def clean_all(race_exclude_ms, outlier_ms):
    """Mark non-standing-start races unusable and outlier drivers. Safe to re-run."""
    races = []
    for f in data_files():
        data = json.loads(f.read_text())
        if any("launchMs" not in d for d in data["drivers"]):
            print(f"{f.name}: old format, delete it and re-run")
            continue
        for d in data["drivers"]:
            d.setdefault("rawStatus", d["status"])
        raw = [d["launchMs"] for d in data["drivers"] if d["rawStatus"] == "ok"]
        races.append((f, data, raw))

    all_raw = [ms for _, _, raw in races for ms in raw]
    if not all_raw:
        return
    overall = statistics.median(all_raw)

    for f, data, raw in races:
        race_med = statistics.median(raw) if raw else None
        usable = (
            race_med is not None
            and len(raw) >= MIN_VALID_DRIVERS
            and abs(race_med - overall) <= race_exclude_ms
        )
        data["usable"] = usable
        data["raceMedianLaunchMs"] = None if race_med is None else round(race_med)
        for d in data["drivers"]:
            d["status"] = d["rawStatus"]
            if (
                usable
                and d["rawStatus"] == "ok"
                and abs(d["launchMs"] - race_med) > outlier_ms
            ):
                d["status"] = "outlier"
        f.write_text(json.dumps(data, indent=2))


def recalibrate_all(offset_ms=None, target_ms=TARGET_MEDIAN_MS, min_ms=MIN_REACTION_MS):
    """Recompute reactionMs / reactionSec from stored launchMs. No downloads.

    offset_ms=None centres every race on target_ms with its own offset;
    otherwise the same offset is used for every race.
    """
    count = 0
    for f in data_files():
        data = json.loads(f.read_text())
        if any("launchMs" not in d for d in data["drivers"]):
            continue
        if offset_ms is None:
            clean = [
                d["launchMs"]
                for d in data["drivers"]
                if d["status"] in ("ok", "too_fast")
            ]
            offset = round(statistics.median(clean) - target_ms) if clean else 0
            centering = "race"
        else:
            offset, centering = offset_ms, "fixed"
        assign_reactions(data["drivers"], offset, data.get("usable", True), min_ms)
        data["method"] = method_info(offset, centering)
        f.write_text(json.dumps(data, indent=2))
        count += 1
    print(f"recalibrated {count} races")


def sync_to_public(public_dir):
    """Copy the race files and index.json into the React app's public/data folder."""
    if public_dir is None:
        return
    public_dir = Path(public_dir)
    if not public_dir.parent.exists():
        print(f"app folder not found ({public_dir.parent}); skipped copying to the app")
        return
    public_dir.mkdir(parents=True, exist_ok=True)
    files = data_files() + [OUT_DIR / "index.json"]
    for f in files:
        shutil.copy2(f, public_dir / f.name)
    print(f"copied {len(files)} files to {public_dir}")


def finalize(args):
    """Clean the data, apply the offset, summarise, write the index, copy to the app."""
    clean_all(args.race_exclude_ms, args.outlier_ms)
    floor = args.min_reaction_ms
    if args.offset_ms is not None:
        print(f"fixed offset: {args.offset_ms} ms for every race")
        recalibrate_all(args.offset_ms, min_ms=floor)
    elif args.center == "global":
        med = overall_median_launch()
        if med is None:
            print("No valid launches found yet.")
            return
        offset = round(med - args.target_median_ms)
        print(
            f"global offset: median launch {round(med)} ms - target "
            f"{args.target_median_ms} ms = {offset} ms"
        )
        recalibrate_all(offset, min_ms=floor)
    else:
        if overall_median_launch() is None:
            print("No valid launches found yet.")
            return
        print(
            f"per-race centring: each race's median driver set to {args.target_median_ms} ms"
        )
        recalibrate_all(None, args.target_median_ms, floor)
    print_summary()
    rebuild_index()
    sync_to_public(None if args.no_sync else args.public_dir)


def print_summary():
    launches, reactions, nudges, race_medians = [], [], [], {}
    excluded, outliers, too_fast = [], 0, 0
    for f in data_files():
        data = json.loads(f.read_text())
        offset = data["method"].get("offsetMs", 0)
        if not data.get("usable", True):
            excluded.append((f.name, data.get("raceMedianLaunchMs")))
            continue
        race = []
        for d in data["drivers"]:
            if d["status"] == "outlier":
                outliers += 1
            if d["status"] == "too_fast":
                too_fast += 1
            if d["status"] == "ok" and d.get("launchMs") is not None:
                launches.append(d["launchMs"])
                reactions.append(d["reactionMs"])
                nudges.append(d["reactionMs"] - round_step(d["launchMs"] - offset))
                race.append(d["launchMs"])
        if race:
            race_medians[f.name] = statistics.median(race)

    sec = lambda ms: f"{ms / 1000:.3f}s"
    if excluded:
        print(
            f"\nExcluded {len(excluded)} races (not clean standing starts or too little data):"
        )
        for name, m in excluded:
            print(f"  {name}: median launch {sec(m) if m is not None else 'n/a'}")
    if not launches:
        return

    med = statistics.median(launches)
    lo, hi = BAND_MS
    in_band = sum(lo <= r <= hi for r in reactions) / len(reactions) * 100
    qs = statistics.quantiles(reactions, n=10)

    print(
        f"\n{len(launches)} valid launches across {len(race_medians)} usable races "
        f"({outliers} outliers and {too_fast} too-fast drivers removed)"
    )
    print(
        f"raw launch     min {sec(min(launches))} / median {sec(med)} / max {sec(max(launches))}"
    )
    print(
        f"reaction       min {sec(min(reactions))} / median "
        f"{sec(statistics.median(reactions))} / max {sec(max(reactions))}"
    )
    print(f"reaction spread  10th pct {sec(qs[0])} / 90th pct {sec(qs[-1])}")
    print(f"inside {lo / 1000:.2f}-{hi / 1000:.2f}s band: {in_band:.0f}% of drivers")
    print(
        f"tie-break shift: mean {statistics.mean(nudges):.2f} ms / max {max(nudges)} ms"
    )

    marginal = sorted(
        (abs(m - med), name, m)
        for name, m in race_medians.items()
        if abs(m - med) > SUSPECT_RACE_MS
    )
    if marginal:
        print(
            f"\nKept, raw median is >{SUSPECT_RACE_MS} ms from the overall median (grip, weather or timing; per-race centring removes it):"
        )
        for diff, name, m in reversed(marginal):
            print(
                f"  {name}: median launch {sec(m)} ({'+' if m > med else '-'}{diff:.0f} ms)"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--years", nargs="+", type=int, default=list(range(START_YEAR, END_YEAR + 1))
    )
    parser.add_argument("--force", action="store_true", help="recompute existing files")
    parser.add_argument(
        "--offset-ms", type=int, default=None, help="fixed offset instead of automatic"
    )
    parser.add_argument("--target-median-ms", type=int, default=TARGET_MEDIAN_MS)
    parser.add_argument(
        "--center",
        choices=["race", "global"],
        default="race",
        help="race: own offset per race (default); global: one shared offset",
    )
    parser.add_argument(
        "--min-reaction-ms",
        type=int,
        default=MIN_REACTION_MS,
        help="drop drivers whose reaction is faster than this (not humanly possible)",
    )
    parser.add_argument(
        "--public-dir",
        default=str(PUBLIC_DIR),
        help="the React app's public/data folder; files are copied here after every run",
    )
    parser.add_argument(
        "--no-sync", action="store_true", help="do not copy files to the app"
    )
    parser.add_argument("--race-exclude-ms", type=int, default=RACE_EXCLUDE_MS)
    parser.add_argument("--outlier-ms", type=int, default=DRIVER_OUTLIER_MS)
    parser.add_argument(
        "--recalibrate",
        action="store_true",
        help="only redo the offset on existing files (no downloads)",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)

    if args.recalibrate:
        finalize(args)
        return

    CACHE_DIR.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    now = pd.Timestamp.utcnow().tz_localize(None)
    failures = []

    try:
        for year in args.years:
            schedule = fastf1.get_event_schedule(year, include_testing=False)
            for _, event in schedule.iterrows():
                if pd.Timestamp(event["EventDate"]) > now - pd.Timedelta(days=1):
                    continue  # race hasn't happened yet

                out = OUT_DIR / f"{year}-{slugify(event['EventName'])}.json"
                if out.exists() and not args.force:
                    continue

                print(
                    f"{year} R{int(event['RoundNumber']):02d} {event['EventName']}: loading...",
                    flush=True,
                )
                started = time.time()
                try:
                    result = process_race(year, event)
                    out.write_text(json.dumps(result, indent=2))
                    ok = sum(d["status"] == "ok" for d in result["drivers"])
                    print(
                        f"    done in {time.time() - started:.0f}s: "
                        f"{ok}/{len(result['drivers'])} valid launches",
                        flush=True,
                    )
                except Exception as exc:  # keep going; report at the end
                    failures.append((year, event["EventName"], str(exc)))
                    print(f"    FAILED ({exc})", flush=True)
    except KeyboardInterrupt:
        print("\nStopped. Finished races are saved; run the same command to resume.")

    finalize(args)
    if failures:
        print("\nFailed races (re-run to retry):")
        for y, name, err in failures:
            print(f"  {y} {name}: {err}")


if __name__ == "__main__":
    main()
