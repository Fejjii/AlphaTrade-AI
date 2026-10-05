"""Research-only Nested replay of checksum-verified Binance public archives.

No API credentials, database, orders, notifications or historical receipt fabrication.
Archive publication proves OHLCV provenance, not point-in-time delivery availability.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from validate_strategy_history import evaluate_series, require_paper_settings

from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.catalog import catalog_for_symbols
from app.market_contracts.enums import VenueId
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.identity import interval_timedelta
from app.market_contracts.ohlcv import require_closed_series
from app.schemas.common import Timeframe
from app.schemas.strategy_replay import SfpReplayEvidence


def archive_rows(payload: bytes, checksum: str, filename: str) -> list[list[str]]:
    expected, listed_name = checksum.strip().split()
    if listed_name.lstrip("*") != filename or hashlib.sha256(payload).hexdigest() != expected:
        raise ValueError("Archive checksum or filename mismatch")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        csv_name = filename.removesuffix(".zip") + ".csv"
        if archive.namelist() != [csv_name]:
            raise ValueError("Unexpected archive contents")
        if archive.getinfo(csv_name).file_size > 20_000_000:
            raise ValueError("Archive exceeds research size bound")
        rows = list(csv.reader(io.StringIO(archive.read(csv_name).decode())))
    if rows and rows[0][0] == "open_time":
        rows.pop(0)
    if not rows or any(len(row) != 12 for row in rows):
        raise ValueError("Malformed or empty archive")
    return rows


def run_one(scope: tuple[str, str], month: str, out: Path, bars: int) -> dict:
    symbol, interval = scope
    filename = f"{symbol}-{interval}-{month}.zip"
    url = (
        f"https://data.binance.vision/data/futures/um/monthly/klines/{symbol}/{interval}/{filename}"
    )
    result = {"symbol": symbol, "timeframe": interval, "archive_url": url}
    try:
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            response = client.get(url)
            response.raise_for_status()
            checksum = client.get(url + ".CHECKSUM")
            checksum.raise_for_status()
        received = datetime.now(UTC)
        rows = archive_rows(response.content, checksum.text, filename)
        (out / filename).write_bytes(response.content)
        (out / (filename + ".CHECKSUM")).write_text(checksum.text)
        timeframe = Timeframe(interval)
        instrument = catalog_for_symbols((symbol,), venue=VenueId.BINANCE).require(symbol)
        identity = first_slice_identity(timeframe=timeframe, instrument=instrument, replay=False)
        identity = identity.model_copy(
            update={
                "provenance": identity.provenance.model_copy(
                    update={"detail": "Binance monthly USD-M archive; historical research only."}
                )
            }
        )
        source = BinanceUsdmPerpetualSource()
        canonical = []
        for row in rows:
            if int(row[6]) + 1 - int(row[0]) != int(
                interval_timedelta(timeframe).total_seconds() * 1000
            ):
                raise ValueError("Archive close clock differs from requested timeframe")
            start = datetime.fromtimestamp(int(row[0]) / 1000, UTC)
            if start.strftime("%Y-%m") != month:
                raise ValueError("Candle outside requested archive month")
            canonical.append(
                source._parse_kline(
                    row,
                    instrument=instrument,
                    timeframe=timeframe,
                    evaluated_at=received,
                    grace=timedelta(seconds=5),
                )
            )
        # Validate the complete archive before selecting a bounded tail.
        full = require_closed_series(
            canonical,
            identity=identity,
            timeframe=timeframe,
            evaluated_at=received,
            min_bars=len(canonical),
        )
        series = require_closed_series(
            full.bars[-bars:],
            identity=identity,
            timeframe=timeframe,
            evaluated_at=received,
            min_bars=min(bars, len(full.bars)),
        )
        families, events = evaluate_series(series, sfp_spec=None, sfp_evidence=SfpReplayEvidence())
        stem = f"{symbol}-{interval}"
        (out / (stem + ".series.json")).write_text(series.model_dump_json())
        (out / (stem + ".events.json")).write_text(json.dumps(events, indent=2, default=str))
        result.update(
            status="evaluated",
            received_at_utc=received.isoformat(),
            archive_sha256=hashlib.sha256(response.content).hexdigest(),
            archive_bars=len(full.bars),
            evaluated_bars=len(series.bars),
            first_open_utc=series.bars[0].interval_start.isoformat(),
            last_close_utc=series.bars[-1].interval_end.isoformat(),
            series_hash=series.content_hash,
            families=families,
        )
    except Exception as exc:
        result.update(status="unavailable", reason=f"{type(exc).__name__}: {str(exc)[:240]}")
    print(f"{symbol} {interval}: {result['status']}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--month", required=True)
    parser.add_argument(
        "--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "TAOUSDT", "HYPEUSDT", "ZECUSDT"]
    )
    parser.add_argument(
        "--timeframes",
        nargs="+",
        choices=["5m", "15m", "1h", "4h"],
        default=["5m", "15m", "1h", "4h"],
    )
    parser.add_argument("--bars", type=int, default=1000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}", args.month) or not 100 <= args.bars <= 2000:
        parser.error("Use YYYY-MM and 100..2000 bars")
    if args.month >= datetime.now(UTC).strftime("%Y-%m"):
        parser.error("Only a completed historical month is allowed")
    for symbol in args.symbols:
        catalog_for_symbols((symbol,), venue=VenueId.BINANCE).require(symbol)
    settings = require_paper_settings()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scopes = [(symbol, tf) for symbol in args.symbols for tf in args.timeframes]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda scope: run_one(scope, args.month, args.output_dir, args.bars), scopes)
        )
    report = {
        "source": "Binance official monthly USD-M public archive",
        "month": args.month,
        "safe_settings": settings,
        "results": results,
        "limitations": [
            "Retrospective structure only; profitability, execution and latency are unvalidated.",
            "Current archive receipts cannot prove historical delivery. SFP is unavailable.",
            "No CVD, order flow, open interest or higher timeframe context.",
            "Isolated symbol/timeframe/direction; provisional detector rules unchanged.",
            "Native 1d and 1w need a longer archive window and are outside this bounded run.",
            "Counts describe unique setup lifecycle transitions, not trades.",
        ],
    }
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    return 0 if all(row["status"] == "evaluated" for row in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
