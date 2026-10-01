"""The proof noun: ask the gate about a scope, and generate the package (SEG-SREQ-089).

``proof check`` reports the coverage the gate finds for a requested scope,
without generating anything; ``proof generate`` assembles and persists an
evidence package when the gate finds the scope ready, and refuses with the
gate's own report otherwise.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from affirmatrix import drift, graph, proof
from affirmatrix.case import AffirmationStore
from affirmatrix.cli import _judgement, _outcome
from affirmatrix.config import Config
from affirmatrix.sources import SourceError, composed


def add_check_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--current", help="the producer supplying the current stream")
    parser.add_argument(
        "--scope", action="append", default=[], help="a requested requirement; repeatable"
    )
    parser.add_argument("--evaluation-date", help="ISO date a waiver's expiry is judged against")
    parser.add_argument("--timestamp", help="ISO timestamp the snapshot identifier is minted from")
    parser.add_argument("--revision", help="the implementation repository's revision, given as is")


def add_generate_arguments(parser: argparse.ArgumentParser) -> None:
    add_check_arguments(parser)
    parser.add_argument("--output-dir", help="relocate the whole write root here, not the case")


def handle_check(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Report the gate's coverage verdict for a requested scope.

    :implements: SEG-SREQ-090
    :implements: SEG-SREQ-091
    :implements: SEG-SREQ-229
    :implements: SEG-SREQ-231
    """
    built, _, error_status = _build(args, config, store)
    if built is None:
        return error_status
    try:
        gate_revision = _judgement.resolve_gate_revision(config, given=args.revision)
    except _judgement.JudgementError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    try:
        _, report = proof.check_readiness(
            built,
            args.scope,
            snapshot_timestamp=_judgement.resolve_timestamp(args.timestamp),
            evaluation_date=_judgement.resolve_evaluation_date(args.evaluation_date),
            current_revision=gate_revision,
        )
    except proof.ScopeError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    document = proof.coverage_report_document(report)
    if args.json:
        _outcome.render_json(document)
    else:
        print(f"blocked: {report.blocked}")
        for diagnostic in report.diagnostics:
            print(f"  {diagnostic.severity.value}: {diagnostic.condition} ({diagnostic.subject})")
    return _outcome.exit_for(_outcome.NEGATIVE if report.blocked else _outcome.POSITIVE)


def handle_generate(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Assemble and persist an evidence package, or refuse with the gate's report.

    :implements: SEG-SREQ-092
    :implements: SEG-SREQ-093
    :implements: SEG-SREQ-094
    :implements: SEG-SREQ-226
    :implements: SEG-SREQ-229
    :implements: SEG-SREQ-231
    """
    built, current, error_status = _build(args, config, store)
    if built is None:
        return error_status
    try:
        gate_revision = _judgement.resolve_gate_revision(config, given=args.revision)
    except _judgement.JudgementError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    write_store = AffirmationStore(root=Path(args.output_dir)) if args.output_dir else store
    try:
        package = proof.assemble(
            built,
            args.scope,
            snapshot_timestamp=_judgement.resolve_timestamp(args.timestamp),
            evaluation_date=_judgement.resolve_evaluation_date(args.evaluation_date),
            current_revision=gate_revision,
            evidence_bundles=composed.evidence_bundles(current),
        )
    except proof.ScopeError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    except proof.GenerationRefused as refusal:
        document = proof.coverage_report_document(refusal.coverage_report)
        if args.json:
            _outcome.render_json(document)
        else:
            print(f"refused: {refusal}")
            for diagnostic in refusal.coverage_report.diagnostics:
                print(
                    f"  {diagnostic.severity.value}: {diagnostic.condition} "
                    f"({diagnostic.subject})"
                )
        return _outcome.exit_for(_outcome.NEGATIVE)
    written = proof.persist(package, write_store)
    report = {
        "snapshotId": package.scope.snapshot_id,
        "documents": {name: str(path) for name, path in written.items()},
    }
    if args.json:
        _outcome.render_json(report)
    else:
        print(f"snapshot: {package.scope.snapshot_id}")
        for name, path in sorted(written.items()):
            print(f"wrote {name}: {path}")
    return _outcome.exit_for(_outcome.POSITIVE)


def _build(args: argparse.Namespace, config: Config, store: AffirmationStore):
    """The built graph and the current stream, or ``(None, None, exit_status)`` on refusal.

    Both proof verbs judge test evidence, so the current stream includes the
    configured run bundles and a bundle that is refused ends the verb here.
    """
    try:
        current = _judgement.resolve_current(args.current, config, evidence=True)
    except _judgement.JudgementError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return None, None, _outcome.exit_for(_outcome.INDETERMINATE)
    try:
        derivation = drift.derive(recorded=store, current=current)
        built = graph.build(derivation)
    except (graph.GraphError, drift.DriftError, SourceError) as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return None, None, _outcome.exit_for(_outcome.INDETERMINATE)
    return built, current, None


__all__ = ["add_check_arguments", "add_generate_arguments", "handle_check", "handle_generate"]
