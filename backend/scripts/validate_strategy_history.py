"""Read-only Binance history evidence for unchanged Nested and SFP detectors.

Run from the repository root with PYTHONPATH=backend/src. No application boot,
database, strategy approval, orders, or notification delivery is involved.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.market_contracts.adapters.binance_usdm import BinanceUsdmPerpetualSource
from app.market_contracts.catalog import catalog_for_symbols
from app.market_contracts.enums import VenueId
from app.market_contracts.first_slice import first_slice_identity
from app.market_contracts.ohlcv import ClosedOhlcvSeries
from app.schemas.common import Timeframe, TradeDirection
from app.schemas.nested_continuation import BrainSetupState, NestedContinuationSpec
from app.schemas.strategy_replay import SfpReplayEvidence
from app.services.sfp_replay_adapter import validate_replay_evidence
from app.strategy_brain.detector import detect_nested, detection_hash
from app.strategy_brain.sfp.contracts import SfpCondition, SfpSpec, available_at
from app.strategy_brain.sfp.detector import detect_sfp

SYMBOLS = ("BTCUSDT", "ETHUSDT", "TAOUSDT", "HYPEUSDT", "ZECUSDT")
TIMEFRAMES = ("5m", "15m", "1h", "4h", "1d", "1w")
SAFE_SETTINGS = {
    "ENABLE_REAL_TRADING": "false",
    "EXECUTION_MODE": "paper",
    "EXCHANGE_MODE": "paper_internal",
}
NESTED_ROLES = ("FORMING", "CONFIRMED", "N1", "N2", "N3", "N4_PLUS", "INVALIDATED", "EXPIRED")
SFP_ROLES = (
    "reference_level",
    "sweep",
    "reclaim",
    "confirmation",
    "failed_reclaim",
    "invalidation",
    "expiry",
)


def require_paper_settings() -> dict[str, str]:
    for key, expected in SAFE_SETTINGS.items():
        if os.environ.get(key, expected).lower() != expected:
            raise ValueError(f"Historical validation requires {key}={expected}.")
        os.environ.setdefault(key, expected)
    return dict(SAFE_SETTINGS)


def unavailable(reasons: list[str]) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "reason_codes": reasons,
        "counts": None,
        "representatives": {},
        "unique_setups": None,
        "detector_snapshots": None,
    }


def summarize(records: list[dict[str, Any]], roles: tuple[str, ...]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    representatives: dict[str, list[dict[str, Any]]] = {role: [] for role in roles}
    seen: set[tuple[str, str]] = set()
    for record in records:
        for role in record["roles"]:
            key = (record["setup_id"], role)
            if role not in representatives or key in seen:
                continue
            seen.add(key)
            counts[role] += 1
            if len(representatives[role]) < 2:
                representatives[role].append(record)
    return {
        "status": "evaluated",
        "reason_codes": [],
        "counts": {role: counts[role] for role in roles},
        "representatives": representatives,
        "unique_setups": len({r["setup_id"] for r in records}),
        "detector_snapshots": len(records),
    }


def evaluate_series(
    series: ClosedOhlcvSeries,
    *,
    sfp_spec: SfpSpec | None,
    sfp_evidence: SfpReplayEvidence,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    bars, symbol, timeframe = (
        tuple(series.bars),
        series.identity.instrument.provider_symbol,
        series.timeframe,
    )
    families: dict[str, Any] = {"nested_continuation": {}, "sfp": {}}
    records: list[dict[str, Any]] = []
    # Only explicitly supplied canonical receipts can establish historical SFP
    # availability. Today's REST download cannot be backdated to past closes.
    proofs = {
        p.bar.source_event_id: p
        for p in sfp_evidence.candles
        if p.observation.identity == series.identity
    }
    sfp_reasons = []
    if sfp_spec is None:
        sfp_reasons.append("authored_sfp_parameters_missing")
    if any(bar.source_event_id not in proofs for bar in bars):
        sfp_reasons.append("historical_candle_receipts_missing")
    if not sfp_reasons and any(
        proofs[b.source_event_id].bar.content_hash != b.content_hash for b in bars
    ):
        sfp_reasons.append("historical_candle_proof_differs_from_acquired_data")
    for direction in TradeDirection:
        scope = {"symbol": symbol, "timeframe": timeframe.value, "direction": direction.value}
        spec = NestedContinuationSpec(
            symbol=symbol, trigger_timeframe=timeframe, direction=direction
        )
        nested_records = []
        for event in detect_nested(bars, spec, evaluated_at=series.evaluated_at):
            bar = bars[event.event_index]
            roles = [event.state.value]
            if event.state is BrainSetupState.CONFIRMED:
                roles.append(event.stage)
            record = {
                **scope,
                "strategy_family": "nested_continuation",
                "setup_id": str(event.setup_id),
                "sequence_id": str(event.sequence_id),
                "state": event.state.value,
                "stage": event.stage,
                "roles": roles,
                "candle_open_utc": bar.interval_start.isoformat(),
                "candle_close_utc": bar.interval_end.isoformat(),
                "detected_at_utc": event.detected_at.isoformat(),
                "expires_at_utc": event.expires_at.isoformat(),
                "anchor_open_utc": bars[event.anchor_index].interval_start.isoformat(),
                "impulse_open_utc": bars[event.impulse_index].interval_start.isoformat(),
                "pullback_open_utc": (
                    bars[event.pullback_index].interval_start.isoformat()
                    if event.pullback_index is not None
                    else None
                ),
                "entry": str(event.entry),
                "stop": str(event.stop),
                "reason_codes": event.reason_codes,
                "evidence": event.evidence,
                "evidence_hash": detection_hash(event, bars),
            }
            nested_records.append(record)
        families["nested_continuation"][direction.value] = summarize(nested_records, NESTED_ROLES)
        records.extend(nested_records)
        if sfp_reasons:
            families["sfp"][direction.value] = unavailable(sfp_reasons)
            continue
        assert sfp_spec is not None
        bound_spec = sfp_spec.model_copy(
            update={"symbol": symbol, "trigger_timeframe": timeframe, "direction": direction}
        )
        observations = tuple(proofs[b.source_event_id].observation for b in bars)
        scan = detect_sfp(bars, observations, bound_spec, evaluated_at=series.evaluated_at)
        if scan.required_evidence.value != "AVAILABLE":
            families["sfp"][direction.value] = unavailable(list(scan.reason_codes))
            continue
        by_id = {str(o.observation_id): o for o in observations}
        sfp_records = []
        seen_setups = set()
        for event in scan.events:
            setup = str(event.setup_id)
            roles = []
            if setup not in seen_setups:
                roles.extend(("reference_level", "sweep"))
                seen_setups.add(setup)
            if event.reclaim_observation_id:
                roles.append("reclaim")
            if event.state is BrainSetupState.CONFIRMED:
                roles.append("confirmation")
            if event.condition is SfpCondition.FAILED_RECLAIM:
                roles.append("failed_reclaim")
            if event.state is BrainSetupState.INVALIDATED:
                roles.append("invalidation")
            if event.state is BrainSetupState.EXPIRED:
                roles.append("expiry")
            level = event.sweep.reference_level
            record = {
                **scope,
                "strategy_family": "sfp",
                "setup_id": setup,
                "event_id": str(event.event_id),
                "state": event.state.value,
                "condition": event.condition.value,
                "roles": roles,
                "candle_open_utc": event.evidence.interval_start.isoformat(),
                "candle_close_utc": event.evidence.interval_end.isoformat(),
                "event_time_utc": event.event_time.isoformat(),
                "observed_at_utc": event.observed_at.isoformat(),
                "expires_at_utc": event.expires_at.isoformat(),
                "reference_level": {
                    "id": str(level.level_id),
                    "kind": level.kind.value,
                    "price": str(level.price),
                    "anchor_event_ids": list(level.anchor_event_ids),
                    "established_at_utc": level.established_at.isoformat(),
                    "known_at_utc": level.known_at.isoformat(),
                },
                "sweep": {
                    "open_utc": event.sweep.event_time.isoformat(),
                    "close_utc": event.sweep.candle_end.isoformat(),
                    "extreme": str(event.sweep.extreme),
                    "depth_ratio": str(event.sweep.depth_ratio),
                },
                "reason_codes": list(event.reason_codes),
                "evidence_hash": event.evidence.payload_content_hash,
                "optional_evidence": {
                    key: getattr(event.quality, key).availability.value
                    for key in ("cvd", "order_flow", "open_interest")
                },
            }
            for role, observation_id in (
                ("reclaim", event.reclaim_observation_id),
                ("confirmation", event.confirmation_observation_id),
            ):
                proof = by_id.get(str(observation_id))
                record[role] = (
                    {
                        "open_utc": proof.interval_start.isoformat(),
                        "close_utc": proof.interval_end.isoformat(),
                        "available_at_utc": available_at(proof).isoformat(),
                    }
                    if proof
                    else None
                )
            sfp_records.append(record)
        families["sfp"][direction.value] = summarize(sfp_records, SFP_ROLES)
        records.extend(sfp_records)
    return families, records


def failure_detail(exc: Exception) -> list[dict[str, str]]:
    chain = []
    while exc is not None and len(chain) < 4:
        chain.append({"type": type(exc).__name__, "message": str(exc)[:300]})
        exc = exc.__cause__
    return chain


def run_validation(
    *,
    symbols: tuple[str, ...],
    timeframes: tuple[Timeframe, ...],
    bars: int,
    as_of: datetime,
    source: BinanceUsdmPerpetualSource,
    sfp_spec: SfpSpec | None = None,
    sfp_evidence: SfpReplayEvidence | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    settings = require_paper_settings()
    proof = sfp_evidence or SfpReplayEvidence()
    validate_replay_evidence(proof)
    report: dict[str, Any] = {
        "as_of_utc": as_of.isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "provider": "Binance USD-M perpetual public REST",
        "safe_settings": settings,
        "requested_bars_per_series": bars,
        "nested_parameters": NestedContinuationSpec(symbol=symbols[0]).parameters.model_dump(
            mode="json"
        ),
        "sfp_authored_spec": sfp_spec.model_dump(mode="json") if sfp_spec else None,
        "sfp_evidence_candles": len(proof.candles),
        "limitations": [
            "Bounded final-candle tail; shorter listing history is reported explicitly. "
            "No profitability estimate.",
            "SFP requires explicit authored parameters and matching canonical historical "
            "receipt proofs; REST candles do not establish past receipts.",
            "CVD, order flow, OI and funding are unavailable in this candle-only harness. "
            "Volume is used only as candle volume.",
            "Each symbol/timeframe/direction is isolated; no higher-timeframe context is injected.",
            "Timestamps are UTC. TradingView candle labels use candle open; decisions use "
            "close/receipt. Exact intrabar sweep time is unknown.",
            "Counts are unique setups reaching each lifecycle role. N stages count "
            "confirmations only; detector snapshots are retained separately.",
        ],
        "results": [],
    }
    history, events = [], []
    for symbol in symbols:
        instrument = catalog_for_symbols((symbol,), venue=VenueId.BINANCE).require(symbol)
        contract_failure = None
        try:
            source.verify_exchange_info(instrument)
        except Exception as exc:
            contract_failure = failure_detail(exc)
        for timeframe in timeframes:
            result: dict[str, Any] = {"symbol": symbol, "timeframe": timeframe.value}
            try:
                if contract_failure:
                    result["acquisition"] = {
                        "status": "unavailable",
                        "final_bars": None,
                        "reason_codes": ["provider_contract_verification_failed"],
                        "error_chain": contract_failure,
                    }
                else:
                    identity = first_slice_identity(
                        timeframe=timeframe, instrument=instrument, replay=False, is_live=True
                    )
                    series = source.fetch_closed_ohlcv_history(
                        identity=identity,
                        instrument=instrument,
                        timeframe=timeframe,
                        evaluated_at=as_of,
                        limit=bars,
                    )
                    received_at = datetime.now(UTC).isoformat()
                    result["acquisition"] = {
                        "status": "acquired" if len(series.bars) == bars else "acquired_partial",
                        "final_bars": len(series.bars),
                        "reason_codes": []
                        if len(series.bars) == bars
                        else ["shorter_provider_history"],
                        "first_open_utc": series.bars[0].interval_start.isoformat(),
                        "last_close_utc": series.bars[-1].interval_end.isoformat(),
                        "received_at_utc": received_at,
                        "series_hash": series.content_hash,
                    }
                    history.append(
                        {"received_at_utc": received_at, "series": series.model_dump(mode="json")}
                    )
                    result["families"], detected = evaluate_series(
                        series, sfp_spec=sfp_spec, sfp_evidence=proof
                    )
                    events.extend(detected)
            except Exception as exc:
                # Do not label a detector/evidence failure as an acquisition failure.
                if "acquisition" in result:
                    result["evaluation_error"] = failure_detail(exc)
                else:
                    result["acquisition"] = {
                        "status": "unavailable",
                        "final_bars": None,
                        "reason_codes": ["provider_history_acquisition_failed"],
                        "error_chain": failure_detail(exc),
                    }
            if "families" not in result:
                reason = (
                    "detector_or_evidence_validation_failed"
                    if "evaluation_error" in result
                    else "provider_data_unavailable"
                )
                result["families"] = {
                    family: {d.value: unavailable([reason]) for d in TradeDirection}
                    for family in ("nested_continuation", "sfp")
                }
                for summary in result["families"]["sfp"].values():
                    if sfp_spec is None:
                        summary["reason_codes"].append("authored_sfp_parameters_missing")
                    if not proof.candles:
                        summary["reason_codes"].append("historical_candle_receipts_missing")
            report["results"].append(result)
            print(f"{symbol} {timeframe.value}: {result['acquisition']['status']}", flush=True)
    report["live_acquisition"] = {
        "acquired_series": len(history),
        "requested_series": len(symbols) * len(timeframes),
        "final_candles": sum(len(item["series"]["bars"]) for item in history),
    }
    return report, history, events


def markdown_report(report: dict[str, Any]) -> str:
    live = report["live_acquisition"]
    lines = [
        "# Nested / SFP historical validation evidence",
        "",
        f"Cutoff: `{report['as_of_utc']}`. Provider: Binance USD-M perpetual public adapter.",
        f"Live acquisition: **{live['acquired_series']}/{live['requested_series']} series**, "
        f"**{live['final_candles']} final candles**.",
        "Safety: `ENABLE_REAL_TRADING=false`, `EXECUTION_MODE=paper`, "
        "`EXCHANGE_MODE=paper_internal`. No orders, Telegram sends or strategy approval mutations.",
        f"SFP authored spec supplied: **{'yes' if report['sfp_authored_spec'] else 'no'}**. "
        f"Canonical historical receipt proofs supplied: "
        f"**{report['sfp_evidence_candles']} candles**.",
        "",
    ]
    for symbol in dict.fromkeys(r["symbol"] for r in report["results"]):
        lines.extend(
            (
                f"## {symbol}",
                "",
                "| Timeframe | Acquisition / final bars | Nested long / short confirmations "
                "| SFP long / short confirmations |",
                "|---|---|---|---|",
            )
        )
        for row in (r for r in report["results"] if r["symbol"] == symbol):

            def count(family: str, role: str, row: dict[str, Any] = row) -> str:
                values = [row["families"][family][d.value] for d in TradeDirection]
                return " / ".join(
                    str(v["counts"][role]) if v["counts"] is not None else "unavailable"
                    for v in values
                )

            acquisition = row["acquisition"]
            final_bars = acquisition["final_bars"]
            final_bars = final_bars if final_bars is not None else "unavailable"
            lines.append(
                f"| {row['timeframe']} | {acquisition['status']} / {final_bars} "
                f"| {count('nested_continuation', 'CONFIRMED')} | {count('sfp', 'confirmation')} |"
            )
        lines.append("")
    lines.extend(("## Representative chart evidence", ""))
    for row in report["results"]:
        for family, directions in row["families"].items():
            for direction, summary in directions.items():
                representatives = summary["representatives"]
                if not any(representatives.values()):
                    continue
                lines.extend(
                    (
                        f"### {row['symbol']} · {row['timeframe']} · {family} · {direction}",
                        "",
                        f"Unique lifecycle counts: `{json.dumps(summary['counts'])}`.",
                        "",
                    )
                )
                for role, examples in representatives.items():
                    if examples:
                        event = examples[0]
                        level = event.get("reference_level")
                        detail = (
                            f"; reference {level['kind']} at {level['price']}"
                            if level
                            else f"; stage {event['stage']}"
                        )
                        lines.append(
                            f"- **{role}**: open `{event['candle_open_utc']}`, "
                            f"close `{event['candle_close_utc']}`{detail}; "
                            f"reasons `{', '.join(event['reason_codes'])}`; "
                            f"setup `{event['setup_id']}`."
                        )
                    else:
                        lines.append(f"- **{role}**: not observed in this window.")
                lines.append("")
    if not any(
        s["representatives"] and any(s["representatives"].values())
        for r in report["results"]
        for f in r["families"].values()
        for s in f.values()
    ):
        lines.extend(
            (
                "No representative detections are available. Unavailable evidence is not a "
                "zero-signal result; no timestamps or signals were invented.",
                "",
            )
        )
    errors = {
        json.dumps(r["acquisition"].get("error_chain", []))
        for r in report["results"]
        if r["acquisition"].get("error_chain")
    }
    lines.extend(("## Provider limitations and evidence gaps", ""))
    lines.extend(f"- `{error}`" for error in sorted(errors))
    acquisition_reasons = sorted(
        {reason for row in report["results"] for reason in row["acquisition"]["reason_codes"]}
    )
    lines.append(f"- Acquisition reason codes: `{', '.join(acquisition_reasons) or 'none'}`.")
    gaps = sorted(
        {
            reason
            for r in report["results"]
            for f in r["families"].values()
            for s in f.values()
            for reason in s["reason_codes"]
        }
    )
    lines.append(f"- Evaluation reason codes: `{', '.join(gaps) or 'none'}`.")
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    lines.extend(
        (
            "",
            "## Exact rerun command",
            "",
            "```sh",
            report["rerun_command"],
            "```",
            "",
            "Full counts, representative proofs and reason codes: `report.json`. "
            "Acquired canonical candles: `candles.jsonl`. Detector snapshots: `events.jsonl`.",
            "",
        )
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="+", choices=SYMBOLS, default=list(SYMBOLS))
    parser.add_argument("--timeframes", nargs="+", choices=TIMEFRAMES, default=list(TIMEFRAMES))
    parser.add_argument("--bars", type=int, default=1000)
    parser.add_argument("--as-of", type=datetime.fromisoformat, default=datetime.now(UTC))
    parser.add_argument(
        "--sfp-spec", type=Path, help="Existing explicit SfpSpec JSON; parameters are never tuned."
    )
    parser.add_argument(
        "--sfp-evidence",
        type=Path,
        help="Existing SfpReplayEvidence JSON with actual canonical historical receipts.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("var/strategy-history-validation"))
    args = parser.parse_args()
    if args.as_of.tzinfo is None or args.as_of > datetime.now(UTC) or not 1 <= args.bars <= 1498:
        parser.error("Use an aware non-future --as-of and --bars between 1 and 1498.")
    require_paper_settings()
    spec = SfpSpec.model_validate_json(args.sfp_spec.read_text()) if args.sfp_spec else None
    evidence = (
        SfpReplayEvidence.model_validate_json(args.sfp_evidence.read_text())
        if args.sfp_evidence
        else None
    )
    catalog = catalog_for_symbols(tuple(args.symbols), venue=VenueId.BINANCE)
    source = BinanceUsdmPerpetualSource(catalog=catalog, max_retries=0)
    try:
        report, history, events = run_validation(
            symbols=tuple(dict.fromkeys(args.symbols)),
            timeframes=tuple(Timeframe(t) for t in dict.fromkeys(args.timeframes)),
            bars=args.bars,
            as_of=args.as_of.astimezone(UTC),
            source=source,
            sfp_spec=spec,
            sfp_evidence=evidence,
        )
    finally:
        source.close()
    command = [
        "env",
        *(f"{key}={value}" for key, value in SAFE_SETTINGS.items()),
        f"PYTHONPATH={os.environ.get('PYTHONPATH', 'backend/src')}",
        "python",
        "backend/scripts/validate_strategy_history.py",
        "--symbols",
        *args.symbols,
        "--timeframes",
        *args.timeframes,
        "--bars",
        str(args.bars),
        "--as-of",
        report["as_of_utc"],
        "--output-dir",
        str(args.output_dir),
    ]
    for flag, path in (("--sfp-spec", args.sfp_spec), ("--sfp-evidence", args.sfp_evidence)):
        if path:
            command.extend((flag, str(path)))
    report["rerun_command"] = shlex.join(command)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output_dir / "report.md").write_text(markdown_report(report))
    for name, items in (("candles", history), ("events", events)):
        (args.output_dir / f"{name}.jsonl").write_text(
            "".join(json.dumps(item) + "\n" for item in items)
        )
    # Missing SFP inputs or a blocked series must not masquerade as a successful validation.
    return (
        0
        if all(
            r["acquisition"]["status"].startswith("acquired")
            and all(s["status"] == "evaluated" for f in r["families"].values() for s in f.values())
            for r in report["results"]
        )
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
