"""Analyze spot windiness and prune the dataset down to the windiest spots.

Two phases:

1. **Analysis** - every spot in ``data/processed/spots.pkl`` gets a windiness
   score computed from its 1D wind histogram (``histograms_1d.pkl``), and the
   full ranking is written to a CSV report. Cleansing issues are reported too:
   duplicate spot IDs, spots without wind data, orphan histogram rows.
2. **Cleansing** - unless ``--dry-run`` is given, everything derived from the
   spot list is pruned to the selected spots, consistently:

   - ``spots.pkl`` (duplicates dropped, lat/lon coerced to float)
   - ``histograms_1d.pkl``, ``histograms_temperature.pkl``,
     ``histograms_precipitation.pkl`` (rows for removed spots dropped)
   - ``histograms_2d/<spot_id>.pkl`` and ``data/timeseries/<spot_id>.npz``
     (files for removed spots moved to the backup directory)

   The original pickles are copied to ``data/backup/prune_<timestamp>/``
   before anything is overwritten; removed per-spot files are *moved* there
   (cheap, same filesystem) so the run is reversible.

Windiness metrics (``--metric``):

- ``kiteable`` (default): share of daylight hours with wind in
  ``[--wind-min, --wind-max)`` knots, over the whole year. Defaults match the
  app's default filter (15 knots and up).
- ``mean``: mean wind speed in knots estimated from bin midpoints.

Usage:
    python -m scripts.prune_windy_spots --dry-run         # report only
    python -m scripts.prune_windy_spots                   # keep top 3000
    python -m scripts.prune_windy_spots --top 2500 --metric mean
    python -m scripts.prune_windy_spots --wind-min 12 --wind-max 30
"""
from __future__ import annotations

import argparse
import math
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from data_pipelines.config import (
    DATA_DIR,
    ENRICHED_SPOTS_FILE,
    HISTOGRAMS_1D_FILE,
    HISTOGRAMS_2D_DIR,
    HISTOGRAMS_PRECIPITATION_FILE,
    HISTOGRAMS_TEMPERATURE_FILE,
    TIMESERIES_DIR,
)
from data_pipelines.utils.file_utils import load_pickle, save_pickle

DEFAULT_TOP = 3000
DEFAULT_WIND_MIN = 15.0  # knots; matches the frontend's default filter
DEFAULT_WIND_MAX = float("inf")
METRICS = ("kiteable", "mean")


@dataclass
class DataPaths:
    """All files touched by the script, so tests can point at a temp dir."""

    spots_file: Path = ENRICHED_SPOTS_FILE
    histograms_1d_file: Path = HISTOGRAMS_1D_FILE
    histograms_temperature_file: Path = HISTOGRAMS_TEMPERATURE_FILE
    histograms_precipitation_file: Path = HISTOGRAMS_PRECIPITATION_FILE
    histograms_2d_dir: Path = HISTOGRAMS_2D_DIR
    timeseries_dir: Path = TIMESERIES_DIR
    backup_root: Path = DATA_DIR / "backup"
    report_file: Path = DATA_DIR / "processed" / "spot_windiness.csv"

    @property
    def daily_histogram_files(self) -> List[Path]:
        return [
            self.histograms_1d_file,
            self.histograms_temperature_file,
            self.histograms_precipitation_file,
        ]


@dataclass
class CleanseReport:
    """What the cleansing step found and did."""

    spots_before: int = 0
    duplicate_rows_dropped: int = 0
    coords_coerced: int = 0
    spots_without_wind_data: int = 0
    orphan_histogram_rows: int = 0
    spots_after_cleanse: int = 0
    spots_kept: int = 0
    spots_removed: int = 0
    score_threshold: float = float("nan")
    files_moved: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cleansing
# ---------------------------------------------------------------------------


def cleanse_spots(spots: pd.DataFrame, report: CleanseReport) -> pd.DataFrame:
    """Drop duplicate spot IDs and coerce coordinates to floats.

    Duplicate ``spot_id`` values are almost always exact duplicate rows; when
    the rows differ (e.g. a coordinate stored as string vs float) the first
    occurrence wins, which is also what the backend's ``get_spot_by_id`` does.
    """
    report.spots_before = len(spots)
    df = spots.copy()

    for col in ("latitude", "longitude"):
        before = df[col]
        coerced = pd.to_numeric(before, errors="coerce")
        report.coords_coerced += int((before.map(type) != float).sum())
        df[col] = coerced.astype(float)

    bad_coords = df["latitude"].isna() | df["longitude"].isna()
    if bad_coords.any():
        print(f"WARNING: dropping {int(bad_coords.sum())} spots with unparseable coordinates")
        df = df[~bad_coords]

    dup_mask = df["spot_id"].duplicated(keep="first")
    report.duplicate_rows_dropped = int(dup_mask.sum())
    df = df[~dup_mask].reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def bin_midpoints(bins: Sequence[float]) -> np.ndarray:
    """Midpoints of histogram bins; an open top bin uses half a bin width above its edge."""
    edges = np.asarray(bins, dtype=float)
    mids = (edges[:-1] + edges[1:]) / 2.0
    if math.isinf(edges[-1]):
        width = edges[-2] - edges[-3] if len(edges) > 2 else 2.5
        mids[-1] = edges[-2] + width / 2.0
    return mids


def bin_mask(bins: Sequence[float], wind_min: float, wind_max: float) -> np.ndarray:
    """Bins overlapping [wind_min, wind_max) - same rule the backend filter uses."""
    edges = np.asarray(bins, dtype=float)
    return (edges[:-1] < wind_max) & (edges[1:] > wind_min)


def score_histograms(
    hist: Dict,
    metric: str = "kiteable",
    wind_min: float = DEFAULT_WIND_MIN,
    wind_max: float = DEFAULT_WIND_MAX,
) -> pd.DataFrame:
    """Score every spot in a 1D histogram pickle.

    Returns a DataFrame indexed by spot_id with columns:
    ``score``, ``kiteable_pct``, ``mean_knots``, ``hours`` (total daylight
    hours of data behind the score).
    """
    if metric not in METRICS:
        raise ValueError(f"Unknown metric {metric!r}; choose from {METRICS}")

    data = np.asarray(hist["data"], dtype=np.float64)  # (spots, days, bins)
    totals_per_bin = data.sum(axis=1)  # (spots, bins)
    hours = totals_per_bin.sum(axis=1)  # (spots,)

    mask = bin_mask(hist["bins"], wind_min, wind_max)
    in_range = totals_per_bin[:, mask].sum(axis=1)
    mids = bin_midpoints(hist["bins"])

    with np.errstate(divide="ignore", invalid="ignore"):
        kiteable_pct = np.where(hours > 0, in_range / hours * 100.0, np.nan)
        mean_knots = np.where(hours > 0, totals_per_bin @ mids / hours, np.nan)

    score = kiteable_pct if metric == "kiteable" else mean_knots
    return pd.DataFrame(
        {
            "score": score,
            "kiteable_pct": kiteable_pct,
            "mean_knots": mean_knots,
            "hours": hours,
        },
        index=pd.Index(list(hist["spot_ids"]), name="spot_id"),
    )


def rank_spots(
    spots: pd.DataFrame,
    scores: pd.DataFrame,
    report: CleanseReport,
) -> pd.DataFrame:
    """Join spots with their scores and sort windiest first.

    Spots without a histogram row (or with zero hours of data) get NaN scores
    and sort last; histogram rows without a spot are counted as orphans.
    """
    spot_ids = set(spots["spot_id"])
    report.orphan_histogram_rows = int(sum(1 for sid in scores.index if sid not in spot_ids))

    ranked = spots.merge(scores, left_on="spot_id", right_index=True, how="left")
    ranked["has_wind_data"] = ranked["score"].notna()
    report.spots_without_wind_data = int((~ranked["has_wind_data"]).sum())

    # Windiest first; ties broken by data coverage, then a stable name order.
    ranked = ranked.sort_values(
        ["score", "hours", "name"],
        ascending=[False, False, True],
        na_position="last",
        kind="mergesort",
    ).reset_index(drop=True)
    ranked.insert(0, "rank", np.arange(1, len(ranked) + 1))
    return ranked


def select_top(ranked: pd.DataFrame, top: int, report: CleanseReport) -> pd.DataFrame:
    """Mark the ``top`` windiest spots with data as kept."""
    eligible = ranked["has_wind_data"]
    keep = eligible & (ranked["rank"] <= top)
    # Spots without data never make the cut, even if fewer than `top` have data.
    ranked = ranked.copy()
    ranked["keep"] = keep

    report.spots_after_cleanse = len(ranked)
    report.spots_kept = int(keep.sum())
    report.spots_removed = int((~keep).sum())
    if report.spots_kept:
        report.score_threshold = float(ranked.loc[keep, "score"].min())
    return ranked


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def write_report(ranked: pd.DataFrame, path: Path) -> None:
    """Write the full ranking to CSV so the cut-off can be inspected/tuned."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["rank", "keep", "spot_id", "name", "country", "latitude", "longitude",
            "score", "kiteable_pct", "mean_knots", "hours"]
    ranked[cols].to_csv(path, index=False, float_format="%.3f")


def print_summary(ranked: pd.DataFrame, report: CleanseReport, metric: str, top: int) -> None:
    """Print the analysis: cleansing counts, score distribution, country impact."""
    print("\n=== Cleansing ===")
    print(f"Spots in spots.pkl:                {report.spots_before}")
    print(f"Duplicate spot_id rows dropped:    {report.duplicate_rows_dropped}")
    print(f"Coordinates coerced to float:      {report.coords_coerced}")
    print(f"Spots without wind data:           {report.spots_without_wind_data}")
    print(f"Orphan histogram rows (no spot):   {report.orphan_histogram_rows}")
    print(f"Unique spots after cleansing:      {report.spots_after_cleanse}")

    scored = ranked[ranked["has_wind_data"]]
    if scored.empty:
        print("\nNo spots have wind data; nothing to rank.")
        return

    label = "kiteable %" if metric == "kiteable" else "mean knots"
    print(f"\n=== Windiness ({label}) ===")
    q = scored["score"].quantile([0.1, 0.25, 0.5, 0.75, 0.9])
    print("Percentiles: " + "  ".join(f"p{int(p * 100)}={v:.1f}" for p, v in q.items()))
    print(f"Min={scored['score'].min():.1f}  Max={scored['score'].max():.1f}  "
          f"Mean={scored['score'].mean():.1f}")
    print(f"\nKeeping top {top}: {report.spots_kept} kept, {report.spots_removed} removed")
    print(f"Cut-off score for the last kept spot: {report.score_threshold:.2f}")

    print("\nTop 10 windiest:")
    for _, row in scored.head(10).iterrows():
        print(f"  {row['rank']:>5}  {row['score']:6.1f}  {row['name']}  ({row['country']})")

    print("\nLast 5 spots to make the cut:")
    kept = ranked[ranked["keep"]]
    for _, row in kept.tail(5).iterrows():
        print(f"  {row['rank']:>5}  {row['score']:6.1f}  {row['name']}  ({row['country']})")

    print("\nSpots per country (before -> after), top 15 by removals:")
    before = ranked.groupby("country").size().rename("before")
    after = ranked[ranked["keep"]].groupby("country").size().rename("after")
    by_country = pd.concat([before, after], axis=1).fillna(0).astype(int)
    by_country["removed"] = by_country["before"] - by_country["after"]
    by_country = by_country.sort_values("removed", ascending=False)
    for country, row in by_country.head(15).iterrows():
        print(f"  {country:<25} {row['before']:>5} -> {row['after']:>5}")
    lost = by_country[by_country["after"] == 0]
    if not lost.empty:
        print(f"\nCountries losing all spots ({len(lost)}): {', '.join(map(str, lost.index))}")


# ---------------------------------------------------------------------------
# Applying the pruning
# ---------------------------------------------------------------------------


def filter_daily_histograms(hist: Dict, keep_ids: Iterable[str]) -> Dict:
    """Return a copy of a {spot_ids, bins, days, data} pickle restricted to keep_ids."""
    keep = set(keep_ids)
    idx = [i for i, sid in enumerate(hist["spot_ids"]) if sid in keep]
    return {
        **hist,
        "spot_ids": [hist["spot_ids"][i] for i in idx],
        "data": hist["data"][idx],
    }


def prune_spot_files(
    directory: Path,
    suffix: str,
    keep_ids: Iterable[str],
    backup_dir: Optional[Path],
) -> int:
    """Move (or delete when no backup) per-spot files whose stem is not in keep_ids."""
    if not directory.exists():
        return 0
    keep = set(keep_ids)
    moved = 0
    if backup_dir is not None:
        backup_dir.mkdir(parents=True, exist_ok=True)
    for path in directory.glob(f"*{suffix}"):
        if path.stem in keep:
            continue
        if backup_dir is not None:
            shutil.move(str(path), str(backup_dir / path.name))
        else:
            path.unlink()
        moved += 1
    return moved


def apply_pruning(
    ranked: pd.DataFrame,
    spot_columns: Sequence[str],
    paths: DataPaths,
    report: CleanseReport,
    backup: bool = True,
    prune_timeseries: bool = True,
) -> Optional[Path]:
    """Write the pruned spots/histograms and move removed per-spot files aside."""
    keep_ids = ranked.loc[ranked["keep"], "spot_id"].tolist()
    # Write back only the original spot columns; the ranking columns stay in the CSV report.
    kept_spots = ranked.loc[ranked["keep"], list(spot_columns)].reset_index(drop=True)

    backup_dir: Optional[Path] = None
    if backup:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = paths.backup_root / f"prune_{stamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        for src in [paths.spots_file, *paths.daily_histogram_files]:
            if src.exists():
                shutil.copy2(src, backup_dir / src.name)
        print(f"\nBacked up pickles to {backup_dir}")

    save_pickle(kept_spots, paths.spots_file)
    print(f"Wrote {len(kept_spots)} spots to {paths.spots_file}")

    for hist_file in paths.daily_histogram_files:
        if not hist_file.exists():
            continue
        hist = load_pickle(hist_file)
        pruned = filter_daily_histograms(hist, keep_ids)
        save_pickle(pruned, hist_file)
        print(f"Wrote {len(pruned['spot_ids'])} spots to {hist_file.name} "
              f"(was {len(hist['spot_ids'])})")

    n2d = prune_spot_files(
        paths.histograms_2d_dir, ".pkl", keep_ids,
        backup_dir / paths.histograms_2d_dir.name if backup_dir else None,
    )
    report.files_moved["histograms_2d"] = n2d
    verb = "Moved" if backup_dir else "Deleted"
    print(f"{verb} {n2d} 2D histogram files")

    if prune_timeseries:
        nts = prune_spot_files(
            paths.timeseries_dir, ".npz", keep_ids,
            backup_dir / paths.timeseries_dir.name if backup_dir else None,
        )
        report.files_moved["timeseries"] = nts
        print(f"{verb} {nts} time series files")

    return backup_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run(
    paths: DataPaths,
    top: int = DEFAULT_TOP,
    metric: str = "kiteable",
    wind_min: float = DEFAULT_WIND_MIN,
    wind_max: float = DEFAULT_WIND_MAX,
    dry_run: bool = False,
    backup: bool = True,
    prune_timeseries: bool = True,
    quiet: bool = False,
) -> pd.DataFrame:
    """Full analysis (+ cleansing unless dry_run). Returns the ranked DataFrame."""
    report = CleanseReport()

    spots = load_pickle(paths.spots_file)
    if not isinstance(spots, pd.DataFrame):
        raise SystemExit(f"Expected a DataFrame in {paths.spots_file}, got {type(spots)}")
    if not paths.histograms_1d_file.exists():
        raise SystemExit(
            f"{paths.histograms_1d_file} not found; run the data pipeline first "
            "(scores are computed from the 1D wind histograms)."
        )
    hist = load_pickle(paths.histograms_1d_file)

    spot_columns = list(spots.columns)
    spots = cleanse_spots(spots, report)
    scores = score_histograms(hist, metric=metric, wind_min=wind_min, wind_max=wind_max)
    ranked = rank_spots(spots, scores, report)
    ranked = select_top(ranked, top, report)

    write_report(ranked, paths.report_file)
    if not quiet:
        print_summary(ranked, report, metric, top)
        print(f"\nFull ranking written to {paths.report_file}")

    if dry_run:
        if not quiet:
            print("\nDry run: no files were modified.")
        return ranked

    apply_pruning(ranked, spot_columns, paths, report, backup=backup, prune_timeseries=prune_timeseries)
    return ranked


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                        help=f"Number of windiest spots to keep (default {DEFAULT_TOP})")
    parser.add_argument("--metric", choices=METRICS, default="kiteable",
                        help="Ranking metric (default: kiteable)")
    parser.add_argument("--wind-min", type=float, default=DEFAULT_WIND_MIN,
                        help=f"Lower bound in knots for the kiteable metric (default {DEFAULT_WIND_MIN})")
    parser.add_argument("--wind-max", type=float, default=DEFAULT_WIND_MAX,
                        help="Upper bound in knots for the kiteable metric (default: no limit)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Analyze and write the report only; modify nothing")
    parser.add_argument("--no-backup", action="store_true",
                        help="Overwrite/delete in place instead of backing up to data/backup/")
    parser.add_argument("--keep-timeseries", action="store_true",
                        help="Leave data/timeseries/*.npz of removed spots in place")
    parser.add_argument("--report", type=Path, default=None,
                        help="Where to write the ranking CSV (default data/processed/spot_windiness.csv)")
    args = parser.parse_args(argv)
    if args.top <= 0:
        parser.error("--top must be positive")
    if args.wind_min >= args.wind_max:
        parser.error("--wind-min must be smaller than --wind-max")
    return args


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    paths = DataPaths()
    if args.report is not None:
        paths.report_file = args.report
    run(
        paths,
        top=args.top,
        metric=args.metric,
        wind_min=args.wind_min,
        wind_max=args.wind_max,
        dry_run=args.dry_run,
        backup=not args.no_backup,
        prune_timeseries=not args.keep_timeseries,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
