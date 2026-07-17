import csv
from pathlib import Path


def log_basket_positions(report, path, timestamp: str, account: str) -> None:
    """Append one row per symbol in report.positions to CSV at path.

    Columns: timestamp, account, symbol, shares, weight, allocation, applied, complete
    Creates parent dir + header if needed.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    file_exists = path.exists()
    fieldnames = ["timestamp", "account", "symbol", "shares", "weight", "allocation", "applied", "complete"]

    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        for symbol in sorted(report.positions.keys()):
            shares = report.positions[symbol]
            weight = report.weights.get(symbol, "")
            row = {
                "timestamp": timestamp,
                "account": account,
                "symbol": symbol,
                "shares": shares,
                "weight": weight,
                "allocation": report.allocation,
                "applied": report.applied,
                "complete": report.complete,
            }
            writer.writerow(row)
