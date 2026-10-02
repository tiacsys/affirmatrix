"""The proof noun: ask the gate, generate a package, show it, verify it (SEG-SREQ-089).

``proof check`` reports the coverage the gate finds for a requested scope,
without generating anything; ``proof generate`` assembles and persists an
evidence package when the gate finds the scope ready, and refuses with the
gate's own report otherwise. ``proof show`` states what a package records and
judges nothing. ``proof verify`` runs the checks of the proof verifier and
reports each one. Neither of the last two writes anything, and neither asks for
an implementation revision.
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
    _judgement.add_bundle_argument(parser)


def add_generate_arguments(parser: argparse.ArgumentParser) -> None:
    add_check_arguments(parser)
    parser.add_argument("--output-dir", help="relocate the whole write root here, not the case")


def add_show_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "package", help="a package: its snapshot identifier, a unique prefix, or its directory"
    )


def add_verify_arguments(parser: argparse.ArgumentParser) -> None:
    add_show_arguments(parser)
    _judgement.add_bundle_argument(parser)
    parser.add_argument(
        "--affirmations",
        action="store_true",
        help="check that the case holds a review event for every design edge",
    )


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


def handle_show(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Report what an evidence package records, and judge nothing.

    :implements: SEG-SREQ-247
    :implements: SEG-SREQ-252
    :implements: SEG-SREQ-253
    :implements: SEG-SREQ-263

    Reads the four documents of the package and nothing else: no run bundle,
    no current stream, and no configuration beyond the case root that names the
    package by identifier. Exits with status 0 whatever the package records.
    """
    directory = resolve_package(args.package, store)
    summary = proof.summarize(proof.read_package(directory))
    if args.json:
        _outcome.render_json(summary.as_document())
    else:
        _print_summary(summary)
    return _outcome.exit_for(_outcome.POSITIVE)


def handle_verify(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Verify an evidence package, report every check, and exit by what the checks found.

    :implements: SEG-SREQ-255
    :implements: SEG-SREQ-256
    :implements: SEG-SREQ-257
    :implements: SEG-SREQ-258
    :implements: SEG-SREQ-259
    :implements: SEG-SREQ-260
    :implements: SEG-SREQ-261
    :implements: SEG-SREQ-262
    :implements: SEG-SREQ-263

    Gives the verifier exactly the run bundles the invocation names, and the
    case of the invocation when the affirmations are asked for. It resolves no
    revision: the verifier judges at the revision the package records. A check
    that failed gives status 1, whatever else was not judged; a check that was
    asked for and not judged gives status 2; otherwise status 0.
    """
    directory = resolve_package(args.package, store)
    try:
        report = proof.verify(
            directory,
            config=config,
            bundles=args.bundle,
            case=store if args.affirmations else None,
        )
    except (SourceError, graph.GraphError) as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    if args.json:
        _outcome.render_json(report.as_document())
    else:
        print(f"snapshot: {report.snapshot_id}")
        for check in report.checks:
            print(f"  {check.name:<17} {check.status:<11} {check.detail}".rstrip())
    if report.failed:
        return _outcome.exit_for(_outcome.NEGATIVE)
    if report.unjudged:
        return _outcome.exit_for(_outcome.INDETERMINATE)
    return _outcome.exit_for(_outcome.POSITIVE)


def resolve_package(name: str, store: AffirmationStore) -> Path:
    """The directory of the package that ``name`` gives: a path, an identifier or a prefix.

    :implements: SEG-SREQ-248
    :implements: SEG-SREQ-249
    :implements: SEG-SREQ-270

    A name that is a directory is a path, and reading it needs no case and no
    configuration. Any other name is an identifier or a prefix of one, looked
    up among the packages of the case. A prefix that names two packages, and a
    name that names none, are refused with status 2.
    """
    if not name:
        raise _judgement.JudgementError("a package needs a name: an identifier, a prefix or a path")
    if Path(name).is_dir():
        return Path(name)
    matches = [found for found in store.snapshot_ids() if found.startswith(name)]
    if len(matches) == 1:
        return store.proof_directory(matches[0])
    if not matches:
        raise _judgement.JudgementError(
            f"{name!r} is no directory, and the case at {store.root} holds no package "
            "with that identifier or prefix"
        )
    raise _judgement.JudgementError(
        f"{name!r} names {len(matches)} packages, so it names none: {', '.join(matches)}"
    )


def _print_summary(summary: proof.Summary) -> None:
    """The human-readable report of ``proof show``."""
    print(f"snapshot: {summary.snapshot_id}")
    print(f"revision: {summary.revision}")
    print(f"design root: {summary.design_root}")
    print(f"requested scope: {', '.join(summary.requested_scope)}")
    print(f"member scope: {len(summary.member_scope)} names")
    print(f"total: {'yes' if summary.total else 'no'}")
    bundles = ", ".join(summary.run_bundles) if summary.run_bundles else "not recorded"
    print(f"run bundles: {bundles}")
    print(f"findings: {len(summary.findings)}")
    for finding in summary.findings:
        print(f"  {finding['severity']}: {finding['condition']} ({finding['subject']})")
    print("requirements:")
    for entry in summary.requirements:
        print(f"  {entry.identifier}")
        print(f"    refined by: {', '.join(entry.refined_by) or 'none'}")
        print(f"    specifications: {', '.join(entry.specifications) or 'none'}")
        print(f"    implementations: {', '.join(entry.implementations) or 'none'}")
        outcomes = ", ".join(f"{name} {result}" for name, result in entry.outcomes)
        print(f"    outcomes: {outcomes or 'none'}")


def _build(args: argparse.Namespace, config: Config, store: AffirmationStore):
    """The built graph and the current stream, or ``(None, None, exit_status)`` on refusal.

    Both proof verbs judge test evidence, so the current stream includes the
    run bundles named with ``--bundle`` and a bundle that is refused ends the verb here.
    """
    try:
        current = _judgement.resolve_current(args.current, config, bundles=args.bundle)
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


__all__ = [
    "add_check_arguments",
    "add_generate_arguments",
    "add_show_arguments",
    "add_verify_arguments",
    "handle_check",
    "handle_generate",
    "handle_show",
    "handle_verify",
    "resolve_package",
]
