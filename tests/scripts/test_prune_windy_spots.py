"""Tests for scripts/prune_windy_spots.py using a small synthetic dataset."""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from data_pipelines.config import DAYS_OF_YEAR, WIND_BINS
from scripts.prune_windy_spots import (
    CleanseReport,
    DataPaths,
    bin_midpoints,
    cleanse_spots,
    filter_daily_histograms,
    parse_args,
    rank_spots,
    run,
    score_histograms,
    select_top,
)

NUM_BINS = len(WIND_BINS) - 1
NUM_DAYS = len(DAYS_OF_YEAR)


def make_histogram(spot_ids, in_range_fraction):
    """1D histogram pickle where each spot has 100 hours/day split around 15 knots.

    ``in_range_fraction[i]`` of the hours land in the 15-17.5 bin (index 6), the
    rest in the 5-7.5 bin (index 2).
    """
    data = np.zeros((len(spot_ids), NUM_DAYS, NUM_BINS), dtype=np.float32)
    for i, frac in enumerate(in_range_fraction):
        data[i, :, 6] = 100 * frac
        data[i, :, 2] = 100 * (1 - frac)
    return {"spot_ids": list(spot_ids), "bins": WIND_BINS, "days": DAYS_OF_YEAR, "data": data}


def make_spots(spot_ids, countries=None):
    countries = countries or ["Testland"] * len(spot_ids)
    return pd.DataFrame(
        {
            "spot_id": spot_ids,
            "name": [f"Spot {sid}" for sid in spot_ids],
            "latitude": [10.0 + i for i in range(len(spot_ids))],
            "longitude": [20.0 + i for i in range(len(spot_ids))],
            "country": countries,
        }
    )


@pytest.fixture
def dataset(tmp_path: Path):
    """Five spots (windiest first: e, d, c, b, a) with all derived files present."""
    processed = tmp_path / "processed"
    processed.mkdir()
    ids = ["a", "b", "c", "d", "e"]
    fractions = [0.1, 0.3, 0.5, 0.7, 0.9]

    spots = make_spots(ids)
    # Exact duplicate row + one with string coordinates, as in the real data.
    dup = spots.iloc[[1]].copy()
    str_coords = spots.iloc[[2]].copy()
    str_coords["latitude"] = str_coords["latitude"].astype(str)
    spots = pd.concat([spots, dup, str_coords], ignore_index=True)

    hist = make_histogram(ids + ["orphan"], fractions + [1.0])
    paths = DataPaths(
        spots_file=processed / "spots.pkl",
        histograms_1d_file=processed / "histograms_1d.pkl",
        histograms_temperature_file=processed / "histograms_temperature.pkl",
        histograms_precipitation_file=processed / "histograms_precipitation.pkl",
        histograms_2d_dir=processed / "histograms_2d",
        timeseries_dir=tmp_path / "timeseries",
        backup_root=tmp_path / "backup",
        report_file=processed / "spot_windiness.csv",
    )
    with open(paths.spots_file, "wb") as f:
        pickle.dump(spots, f)
    for hist_file in paths.daily_histogram_files:
        with open(hist_file, "wb") as f:
            pickle.dump(hist, f)
    paths.histograms_2d_dir.mkdir()
    paths.timeseries_dir.mkdir()
    for sid in ids:
        (paths.histograms_2d_dir / f"{sid}.pkl").write_bytes(b"x")
        (paths.timeseries_dir / f"{sid}.npz").write_bytes(b"x")
    return paths


class TestScoring:
    def test_kiteable_percentage_matches_backend_rule(self):
        hist = make_histogram(["a", "b"], [0.25, 1.0])
        scores = score_histograms(hist, metric="kiteable", wind_min=15, wind_max=float("inf"))
        assert scores.loc["a", "score"] == pytest.approx(25.0)
        assert scores.loc["b", "score"] == pytest.approx(100.0)
        assert scores.loc["a", "hours"] == pytest.approx(100 * NUM_DAYS)

    def test_mean_uses_bin_midpoints(self):
        hist = make_histogram(["a"], [1.0])  # everything in the 15-17.5 bin
        scores = score_histograms(hist, metric="mean")
        assert scores.loc["a", "mean_knots"] == pytest.approx(16.25)

    def test_zero_hours_gives_nan(self):
        hist = make_histogram(["a"], [0.5])
        hist["data"][0] = 0
        scores = score_histograms(hist)
        assert np.isnan(scores.loc["a", "score"])

    def test_open_top_bin_midpoint(self):
        mids = bin_midpoints([0, 2.5, 5, float("inf")])
        assert mids.tolist() == [1.25, 3.75, 6.25]

    def test_unknown_metric_rejected(self):
        with pytest.raises(ValueError):
            score_histograms(make_histogram(["a"], [0.5]), metric="median")


class TestCleanse:
    def test_drops_duplicates_and_coerces_coordinates(self):
        spots = make_spots(["a", "b"])
        spots["latitude"] = spots["latitude"].astype(object)
        spots.loc[1, "latitude"] = "11.5"
        spots = pd.concat([spots, spots.iloc[[0]]], ignore_index=True)
        report = CleanseReport()

        cleaned = cleanse_spots(spots, report)

        assert cleaned["spot_id"].tolist() == ["a", "b"]
        assert cleaned["latitude"].dtype == float
        assert cleaned.loc[1, "latitude"] == 11.5
        assert report.duplicate_rows_dropped == 1
        assert report.coords_coerced == 1


class TestRanking:
    def test_ranks_windiest_first_and_counts_orphans(self):
        spots = make_spots(["a", "b", "nodata"])
        hist = make_histogram(["a", "b", "orphan"], [0.2, 0.8, 0.5])
        report = CleanseReport()

        ranked = rank_spots(spots, score_histograms(hist), report)
        ranked = select_top(ranked, top=1, report=report)

        assert ranked["spot_id"].tolist() == ["b", "a", "nodata"]
        assert ranked["keep"].tolist() == [True, False, False]
        assert report.orphan_histogram_rows == 1
        assert report.spots_without_wind_data == 1
        assert report.spots_kept == 1
        assert report.score_threshold == pytest.approx(80.0)

    def test_spots_without_data_never_kept_even_if_top_is_large(self):
        spots = make_spots(["a", "nodata"])
        hist = make_histogram(["a"], [0.5])
        report = CleanseReport()
        ranked = select_top(rank_spots(spots, score_histograms(hist), report), 10, report)
        assert ranked.set_index("spot_id")["keep"].to_dict() == {"a": True, "nodata": False}


def test_filter_daily_histograms_preserves_order_and_layout():
    hist = make_histogram(["a", "b", "c"], [0.1, 0.2, 0.3])
    pruned = filter_daily_histograms(hist, {"c", "a"})
    assert pruned["spot_ids"] == ["a", "c"]
    assert pruned["data"].shape == (2, NUM_DAYS, NUM_BINS)
    np.testing.assert_array_equal(pruned["data"][1], hist["data"][2])
    assert pruned["bins"] == hist["bins"]
    assert pruned["days"] == hist["days"]


class TestRun:
    def test_dry_run_modifies_nothing_but_writes_report(self, dataset: DataPaths):
        before = {p: p.read_bytes() for p in [dataset.spots_file, *dataset.daily_histogram_files]}

        ranked = run(dataset, top=3, dry_run=True, quiet=True)

        for p, content in before.items():
            assert p.read_bytes() == content
        assert len(list(dataset.histograms_2d_dir.glob("*.pkl"))) == 5
        assert not dataset.backup_root.exists()
        report = pd.read_csv(dataset.report_file)
        assert report["spot_id"].tolist() == ["e", "d", "c", "b", "a"]
        assert report["keep"].tolist() == [True, True, True, False, False]
        assert ranked["keep"].sum() == 3

    def test_prune_rewrites_all_derived_files_consistently(self, dataset: DataPaths):
        run(dataset, top=3, quiet=True)

        with open(dataset.spots_file, "rb") as f:
            spots = pickle.load(f)
        assert spots["spot_id"].tolist() == ["e", "d", "c"]
        assert list(spots.columns) == ["spot_id", "name", "latitude", "longitude", "country"]
        assert spots["latitude"].dtype == float
        assert spots.index.tolist() == [0, 1, 2]

        for hist_file in dataset.daily_histogram_files:
            with open(hist_file, "rb") as f:
                hist = pickle.load(f)
            # Keeps the file's own order, drops removed spots and the orphan row.
            assert hist["spot_ids"] == ["c", "d", "e"]
            assert hist["data"].shape == (3, NUM_DAYS, NUM_BINS)

        assert sorted(p.stem for p in dataset.histograms_2d_dir.glob("*.pkl")) == ["c", "d", "e"]
        assert sorted(p.stem for p in dataset.timeseries_dir.glob("*.npz")) == ["c", "d", "e"]

        backups = list(dataset.backup_root.glob("prune_*"))
        assert len(backups) == 1
        backup = backups[0]
        assert (backup / "spots.pkl").exists()
        assert (backup / "histograms_1d.pkl").exists()
        assert sorted(p.stem for p in (backup / "histograms_2d").glob("*.pkl")) == ["a", "b"]
        assert sorted(p.stem for p in (backup / "timeseries").glob("*.npz")) == ["a", "b"]

    def test_no_backup_deletes_and_keep_timeseries_leaves_npz(self, dataset: DataPaths):
        run(dataset, top=2, backup=False, prune_timeseries=False, quiet=True)

        assert not dataset.backup_root.exists()
        assert sorted(p.stem for p in dataset.histograms_2d_dir.glob("*.pkl")) == ["d", "e"]
        assert len(list(dataset.timeseries_dir.glob("*.npz"))) == 5

    def test_missing_histograms_is_a_clear_error(self, dataset: DataPaths):
        dataset.histograms_1d_file.unlink()
        with pytest.raises(SystemExit, match="histograms_1d.pkl"):
            run(dataset, dry_run=True, quiet=True)


class TestCli:
    def test_defaults(self):
        args = parse_args([])
        assert args.top == 3000
        assert args.metric == "kiteable"
        assert args.wind_min == 15.0
        assert args.wind_max == float("inf")

    def test_rejects_bad_ranges(self):
        with pytest.raises(SystemExit):
            parse_args(["--top", "0"])
        with pytest.raises(SystemExit):
            parse_args(["--wind-min", "20", "--wind-max", "10"])
