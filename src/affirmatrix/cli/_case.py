"""The case noun: create, inspect, sync, refresh the schema copy of, and trim a case (SEG-SREQ-069).

Five verbs, one write root: ``init`` creates the layout and schema set
without altering an existing one; ``check`` reports five judgements about
what is there; ``sync`` writes the derived stream a producer and the case
together imply; ``refresh`` rewrites the case's schema copy from the packaged
schemas and names what differed; ``remove`` trims exactly what its selector
names.
"""

from __future__ import annotations

import argparse

from affirmatrix import drift, graph, taxonomy
from affirmatrix.case import AffirmationStore, AffirmationStoreError
from affirmatrix.cli import _judgement, _outcome, _selector
from affirmatrix.config import Config
from affirmatrix.records import EdgeRecord, NodeRecord
from affirmatrix.sources import SourceError


def add_check_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--current", help="the producer supplying the current stream")


def add_sync_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--current", help="the producer supplying the current stream")


def add_remove_arguments(parser: argparse.ArgumentParser) -> None:
    _selector.add_selector_arguments(parser)


def handle_init(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Create a case's layout and schema set, unaltered if already there.

    :implements: SEG-SREQ-070
    """
    store.initialize()
    print(f"case initialized at {store.root}")
    return _outcome.exit_for(_outcome.POSITIVE)


def handle_check(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Report the case's five judgements.

    :implements: SEG-SREQ-071
    :implements: SEG-SREQ-290

    Layout and schema set are read whether or not the case is otherwise
    readable; record counts default to zero for a case that is not yet
    self-describing rather than propagating that refusal, since a fresh
    root reporting zero of everything is itself the honest report. A producer
    that cannot be read is reported with the reason the library gave, as
    ``producerReason`` in the structured rendering (``null`` when the
    producer is readable) and as a line of its own in the text.
    """
    layout = sorted(store.layout())
    missing_schemas = sorted(store.missing_schemas())
    counts = _record_counts(store)
    config_found = (args.config_path is not None and args.config_path.is_file())
    producer_reason = _producer_unreadable_reason(args, config)
    producer_readable = producer_reason is None
    report = {
        "layout": layout,
        "missingSchemas": missing_schemas,
        "recordCounts": counts,
        "configurationFound": config_found,
        "producerReadable": producer_readable,
        "producerReason": producer_reason,
    }
    if args.json:
        _outcome.render_json(report)
    else:
        print(f"layout: {', '.join(layout) or '(none)'}")
        print(f"missing schemas: {', '.join(missing_schemas) or '(none)'}")
        shown = {
            "nodes": counts["nodes"],
            "edges": counts["edges"],
            "review events": counts["reviewEvents"],
        }
        print(f"record counts: {_outcome.counts_display(shown)}")
        print(f"configuration found: {config_found}")
        print(f"producer readable: {producer_readable}")
        if producer_reason is not None:
            print(f"producer reason: {producer_reason}")
    healthy = not missing_schemas and producer_readable
    return _outcome.exit_for(_outcome.POSITIVE if healthy else _outcome.NEGATIVE)


def handle_sync(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Write the derived stream case sync produces, then clear the test evidence the case holds.

    :implements: SEG-SREQ-072
    :implements: SEG-SREQ-073
    :implements: SEG-SREQ-074
    :implements: SEG-SREQ-136
    :implements: SEG-SREQ-212
    :implements: SEG-SREQ-228

    A current stream that cannot be built, and a record of it that the case
    refuses, stop the sync before any write, exit 2. The case stores no test
    evidence, so the stream's test outcomes and evidence edges are left out of
    what is written. After the write, every test outcome node and evidence
    edge the case still holds is removed, and each removal is named. A
    vanished evidence edge is not reported: the removal covers it.
    """
    try:
        current = _judgement.resolve_current(args.current, config)
    except _judgement.JudgementError as error:
        return _outcome.exit_for(_report_refusal(str(error), _outcome.INDETERMINATE))
    try:
        derivation = drift.derive(recorded=store, current=current)
    except (graph.GraphError, drift.DriftError, SourceError) as error:
        return _outcome.exit_for(_report_refusal(str(error), _outcome.INDETERMINATE))
    evidence_nodes = taxonomy.evidence_node_kinds()
    evidence_edges = taxonomy.evidence_edge_kinds()
    held_nodes = [node for node in store.nodes() if node.kind in evidence_nodes]
    held_edges = [edge for edge in store.edges() if edge.kind in evidence_edges]
    store.write_records(
        (node for node in derivation.nodes() if node.kind not in evidence_nodes),
        (edge for edge in derivation.edges() if edge.kind not in evidence_edges),
        demote=(),
    )
    print(f"synced {store.root}")
    for edge in derivation.vanished:
        if edge.kind not in evidence_edges:
            print(f"vanished: {edge.from_id} -> {edge.to_id} ({edge.kind})")
    _remove_held_evidence(store, held_nodes, held_edges)
    return _outcome.exit_for(_outcome.POSITIVE)


def _remove_held_evidence(
    store: AffirmationStore, nodes: list[NodeRecord], edges: list[EdgeRecord]
) -> None:
    """Remove the test evidence the case held before the sync, and name each record.

    What is removed was read, and so checked against the case's schemas,
    before the sync wrote anything. A kind with no held record is not touched,
    so a case that holds no evidence is left byte for byte as it is.
    """
    for kind in sorted({node.kind for node in nodes}):
        store.remove_nodes(kind, [node.local_id for node in nodes if node.kind == kind])
    for kind in sorted({edge.kind for edge in edges}):
        store.remove_edges(
            kind, [(edge.from_id, edge.to_id) for edge in edges if edge.kind == kind]
        )
    for node in nodes:
        print(f"removed: {node.local_id} ({node.kind})")
    for edge in edges:
        print(f"removed: {edge.from_id} -> {edge.to_id} ({edge.kind})")


def handle_refresh(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Rewrite the case's schema copy from the packaged schemas, and say what differed.

    :implements: SEG-SREQ-141

    A refresh that changed something is a store act done, not a negative
    verdict, so both outcomes exit 0; the working tree shows the operator what
    to commit. A root that is not a case is a request it could not judge.
    """
    try:
        refreshed = store.refresh_schemas()
    except AffirmationStoreError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    if args.json:
        _outcome.render_json({"refreshed": list(refreshed)})
    else:
        for name in refreshed:
            print(f"refreshed: {name}")
        if not refreshed:
            print("schema copy up to date")
    return _outcome.exit_for(_outcome.POSITIVE)


def handle_remove(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Remove only the edge records the selector names.

    :implements: SEG-SREQ-075
    :implements: SEG-SREQ-103

    The selector's grammar is edge-shaped (SEG-SREQ-099): this pass removes
    matched edges only. Addressing a node record by the same grammar is
    unspecified by the requirements — SEG-SREQ-075 names both node and edge
    records, but no selector field addresses a node on its own — so it is
    left out rather than inventing a form the requirements do not describe.
    """
    selector = _selector.selector_from_args(args)
    try:
        built = graph.build(store)
    except graph.GraphError as error:
        return _outcome.exit_for(_report_refusal(str(error), _outcome.INDETERMINATE))
    matched = _selector.select(store.edges(), selector, built)
    if not matched:
        return _outcome.exit_for(
            _report_refusal("the selector matched no edge", _outcome.INDETERMINATE)
        )
    for kind in {edge.kind for edge in matched}:
        store.remove_edges(
            kind, [(edge.from_id, edge.to_id) for edge in matched if edge.kind == kind]
        )
    for edge in matched:
        print(f"removed: {edge.from_id} -> {edge.to_id} ({edge.kind})")
    return _outcome.exit_for(_outcome.POSITIVE)


def _record_counts(store: AffirmationStore) -> dict[str, int]:
    try:
        return {
            "nodes": sum(1 for _ in store.nodes()),
            "edges": sum(1 for _ in store.edges()),
            "reviewEvents": sum(1 for _ in store.review_events()),
        }
    except AffirmationStoreError:
        return {"nodes": 0, "edges": 0, "reviewEvents": 0}


def _producer_unreadable_reason(args: argparse.Namespace, config: Config) -> str | None:
    """The reason the producer cannot be read, in the library's own words, or ``None``."""
    try:
        current = _judgement.resolve_current(args.current, config)
        list(current.nodes())
    except (_judgement.JudgementError, SourceError) as error:
        return str(error)
    return None


def _report_refusal(message: str, status: int) -> int:
    _outcome.render_refusal(message, as_json=False)
    return status


__all__ = [
    "add_check_arguments",
    "add_remove_arguments",
    "add_sync_arguments",
    "handle_check",
    "handle_init",
    "handle_refresh",
    "handle_remove",
    "handle_sync",
]
