import csv
from pathlib import Path
from types import SimpleNamespace

from forex.run.basket_track import log_basket_positions


def test_log_basket_positions_creates_header(tmp_path):
    """First call creates header row."""
    csv_file = tmp_path / "basket.csv"
    report = SimpleNamespace(
        positions={"SPY": 100},
        weights={"SPY": 0.5},
        allocation=1000.0,
        applied=True,
    )
    log_basket_positions(report, str(csv_file), "2026-01-01T12:00:00Z", "DU123456")

    with open(csv_file) as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 1
    assert rows[0]["timestamp"] == "2026-01-01T12:00:00Z"
    assert rows[0]["account"] == "DU123456"
    assert rows[0]["symbol"] == "SPY"
    assert rows[0]["shares"] == "100"
    assert rows[0]["weight"] == "0.5"
    assert rows[0]["allocation"] == "1000.0"
    assert rows[0]["applied"] == "True"


def test_log_basket_positions_appends(tmp_path):
    """Second call appends without duplicating header."""
    csv_file = tmp_path / "basket.csv"
    report1 = SimpleNamespace(
        positions={"SPY": 100},
        weights={"SPY": 0.5},
        allocation=1000.0,
        applied=True,
    )
    report2 = SimpleNamespace(
        positions={"SPY": 110, "TLT": 50},
        weights={"SPY": 0.6, "TLT": 0.4},
        allocation=1500.0,
        applied=True,
    )

    log_basket_positions(report1, str(csv_file), "2026-01-01T12:00:00Z", "DU123456")
    log_basket_positions(report2, str(csv_file), "2026-01-02T12:00:00Z", "DU123456")

    with open(csv_file) as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 3
    assert rows[0]["symbol"] == "SPY"
    assert rows[1]["symbol"] == "SPY"
    assert rows[2]["symbol"] == "TLT"
    assert rows[1]["timestamp"] == "2026-01-02T12:00:00Z"
    assert rows[2]["timestamp"] == "2026-01-02T12:00:00Z"


def test_log_basket_positions_missing_weight(tmp_path):
    """Weight missing from report.weights still logs the row."""
    csv_file = tmp_path / "basket.csv"
    report = SimpleNamespace(
        positions={"SPY": 100, "TLT": 50},
        weights={"SPY": 0.5},  # TLT missing
        allocation=1000.0,
        applied=True,
    )
    log_basket_positions(report, str(csv_file), "2026-01-01T12:00:00Z", "DU123456")

    with open(csv_file) as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 2
    assert rows[0]["symbol"] == "SPY"
    assert rows[0]["weight"] == "0.5"
    assert rows[1]["symbol"] == "TLT"
    assert rows[1]["weight"] == ""


def test_log_basket_positions_creates_parent_dir(tmp_path):
    """Parent directory is created if it doesn't exist."""
    csv_file = tmp_path / "subdir" / "basket.csv"
    report = SimpleNamespace(
        positions={"SPY": 100},
        weights={"SPY": 0.5},
        allocation=1000.0,
        applied=True,
    )
    log_basket_positions(report, str(csv_file), "2026-01-01T12:00:00Z", "DU123456")

    assert csv_file.exists()
    with open(csv_file) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
