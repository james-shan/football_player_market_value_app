#!/usr/bin/env python3
"""Export modeling + prediction CSVs without pandas.

This mirrors the notebook step in `notebooks/regression_data_prep.ipynb`:

- Reads `data/merged/player_season_regression_dataset_all3.csv`
- Writes:
  - `data/merged/player_value_modeling_2015_16_to_2024_25.csv`
  - `data/merged/player_stats_2025_26_null_market_value.csv`
"""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALL3 = ROOT / "data" / "merged" / "player_season_regression_dataset_all3.csv"
OUT_HIST = ROOT / "data" / "merged" / "player_value_modeling_2015_16_to_2024_25.csv"
OUT_2025 = ROOT / "data" / "merged" / "player_stats_2025_26_null_market_value.csv"

CURRENT_SEASON = 2025


def is_numberish(v: str | None) -> bool:
    if v is None:
        return False
    t = str(v).strip()
    if not t:
        return False
    try:
        float(t)
        return True
    except ValueError:
        return False


def main() -> None:
    if not ALL3.exists():
        raise SystemExit(f"Missing file: {ALL3}")

    OUT_HIST.parent.mkdir(parents=True, exist_ok=True)

    with open(ALL3, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames:
            raise SystemExit("Input has no header columns.")

        # Ensure these columns exist; if they don't, we still write the file.
        target_cols = ["target_market_value_eur", "target_market_value_log", "market_value_date"]

        with open(OUT_HIST, "w", encoding="utf-8", newline="") as f_hist, open(
            OUT_2025, "w", encoding="utf-8", newline=""
        ) as f_2025:
            w_hist = csv.DictWriter(f_hist, fieldnames=fieldnames)
            w_2025 = csv.DictWriter(f_2025, fieldnames=fieldnames)
            w_hist.writeheader()
            w_2025.writeheader()

            n_hist = 0
            n_2025 = 0
            for row in reader:
                season_raw = (row.get("season") or "").strip()
                if not season_raw:
                    continue
                try:
                    season = int(float(season_raw))
                except ValueError:
                    continue

                if season == CURRENT_SEASON:
                    out = dict(row)
                    for c in target_cols:
                        if c in out:
                            out[c] = ""
                    w_2025.writerow(out)
                    n_2025 += 1
                    continue

                if 2015 <= season <= 2024:
                    # Historical modeling table requires a target market value.
                    if not is_numberish(row.get("target_market_value_eur")):
                        continue
                    w_hist.writerow(row)
                    n_hist += 1

    print(f"Wrote {OUT_HIST} rows={n_hist:,}")
    print(f"Wrote {OUT_2025} rows={n_2025:,}")


if __name__ == "__main__":
    main()

