"""The graph noun: judge consistency, and derive every strong edge's state (SEG-SREQ-076).

``graph check`` builds one record stream and reports what the builder
knows; it reads no run bundle. ``graph status`` derives every strong edge's
state from both the recorded and the current streams, and reports the test
evidence of the configured run bundles apart, with its own counts.
"""

from __future__ import annotations

import argparse
from collections import Counter

from affirmatrix import drift, graph, taxonomy
from affirmatrix.case import AffirmationStore
from affirmatrix.cli import _judgement, _outcome
from affirmatrix.config import Config
from affirmatrix.records import EdgeReference, LinkState, NodeRecord, RecordSource
from affirmatrix.sources import SourceError

_SUSPECT_OR_BROKEN = frozenset(
    {
        LinkState.DIRECTLY_OUTDATED,
        LinkState.TRANSITIVELY_SUSPECT,
        LinkState.DOUBLY_OUTDATED,
        LinkState.BROKEN,
    }
)


def add_check_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--current", help="the producer supplying the current stream")


def add_status_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--current", help="the producer supplying the current stream")
    parser.add_argument("--revision", help="the implementation repository's revision, given as is")


def handle_check(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Report node and edge counts by kind, and the count of pending strong edges.

    :implements: SEG-SREQ-077
    :implements: SEG-SREQ-078
    :implements: SEG-SREQ-079

    Over the one stream given: ``--current`` when given, the case itself
    otherwise. An unbuildable stream is the negative verdict, and its
    refusal renders the builder's own message with no count of anything.
    """
    source = _current_or_case(args, config, store)
    try:
        built = graph.build(source)
    except (graph.GraphError, SourceError) as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.NEGATIVE)
    node_counts = Counter(built.node(local_id).kind for local_id in built.node_ids())
    edge_counts = Counter(edge.kind for edge in built.edges)
    strong = taxonomy.propagating_edge_kinds()
    pending = sum(
        1 for edge in built.edges if edge.state is LinkState.PENDING and edge.kind in strong
    )
    report = {
        "nodesByKind": dict(sorted(node_counts.items())),
        "edgesByKind": dict(sorted(edge_counts.items())),
        "pending": pending,
    }
    if args.json:
        _outcome.render_json(report)
    else:
        print(f"nodes by kind: {_outcome.counts_display(report['nodesByKind'])}")
        print(f"edges by kind: {_outcome.counts_display(report['edgesByKind'])}")
        print(f"pending: {pending}")
    return _outcome.exit_for(_outcome.POSITIVE)


def handle_status(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Derive every strong edge's state from both streams, and report the evidence apart.

    :implements: SEG-SREQ-080
    :implements: SEG-SREQ-081
    :implements: SEG-SREQ-082
    :implements: SEG-SREQ-083
    :implements: SEG-SREQ-112
    :implements: SEG-SREQ-137
    :implements: SEG-SREQ-138
    :implements: SEG-SREQ-208
    :implements: SEG-SREQ-210
    :implements: SEG-SREQ-231

    The rows are the strong edges. Every recorded edge the current stream no
    longer has is listed after them, with no state, and takes no part in the
    verdict. The evidence section counts the test outcomes recorded at the
    current revision, those recorded at another revision, and the evidence
    edges that touch an absent node. The current revision is asked for only
    when the current stream holds a test outcome. The verdict is negative for
    a strong edge that is suspect or broken and for a dangling evidence edge,
    and never for an outcome at any revision.
    """
    try:
        current = _judgement.resolve_current(args.current, config, evidence=True)
    except _judgement.JudgementError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    try:
        derivation = drift.derive(recorded=store, current=current)
        built = graph.build(derivation)
    except (graph.GraphError, drift.DriftError, SourceError) as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    outcomes = _outcome_nodes(built)
    revision = None
    if outcomes:
        try:
            revision = _judgement.resolve_gate_revision(config, given=args.revision)
        except _judgement.JudgementError as error:
            _outcome.render_refusal(str(error), as_json=args.json)
            return _outcome.exit_for(_outcome.INDETERMINATE)
    strong = taxonomy.propagating_edge_kinds()
    strong_edges = [edge for edge in built.edges if edge.kind in strong]
    rows = [_status_row(built, edge, store, verbose=args.verbose) for edge in strong_edges]
    rows += [
        _vanished_row(edge)
        for edge in sorted(derivation.vanished, key=lambda e: (e.from_id, e.to_id, e.kind))
        if edge.kind in strong
    ]
    evidence = _evidence_counts(built, outcomes, revision)
    if args.json:
        _outcome.render_json({"edges": rows, "evidence": evidence})
    else:
        _print_status(rows)
        print(
            f"evidence: {evidence['current']} at the current revision, "
            f"{evidence['stale']} at another revision, {evidence['dangling']} dangling"
        )
    not_active = {edge.state for edge in strong_edges if edge.state is not LinkState.ACTIVE}
    if not_active & _SUSPECT_OR_BROKEN or evidence["dangling"]:
        return _outcome.exit_for(_outcome.NEGATIVE)
    return _outcome.exit_for(_outcome.POSITIVE)


def _outcome_nodes(built: graph.Graph) -> list[NodeRecord]:
    """Every test outcome node of the built graph."""
    return [node for kind in taxonomy.evidence_node_kinds() for node in built.nodes_of_kind(kind)]


def _evidence_counts(
    built: graph.Graph, outcomes: list[NodeRecord], revision: str | None
) -> dict[str, int]:
    """Outcomes at ``revision``, outcomes at another one, and evidence edges to an absent node.

    ``revision`` is ``None`` only when ``outcomes`` is empty, so both outcome
    counts are then zero.
    """
    present = built.node_ids()
    current = sum(1 for node in outcomes if node.revision == revision)
    dangling = sum(
        1
        for edge in built.edges
        if edge.kind in taxonomy.evidence_edge_kinds()
        and (edge.from_id not in present or edge.to_id not in present)
    )
    return {"current": current, "stale": len(outcomes) - current, "dangling": dangling}


def _current_or_case(
    args: argparse.Namespace, config: Config, store: AffirmationStore
) -> RecordSource:
    if args.current is not None:
        return _judgement.resolve_current(args.current, config, evidence=False)
    return store


def _vanished_row(edge) -> dict[str, object]:
    return {"from": edge.from_id, "to": edge.to_id, "kind": edge.kind}


def _status_row(built, edge, store: AffirmationStore, *, verbose: bool) -> dict[str, object]:
    row: dict[str, object] = {
        "from": edge.from_id,
        "to": edge.to_id,
        "kind": edge.kind,
        "state": edge.state.value,
    }
    affirmed = edge.edge_hash is not None and edge.state is not LinkState.BROKEN
    if verbose and affirmed:
        reference = EdgeReference(kind=edge.kind, from_id=edge.from_id, to_id=edge.to_id)
        latest = store.latest_review_event(reference)
        if latest is not None:
            comparison = drift.compare(
                reference,
                current_from=built.node(edge.from_id),
                current_to=built.node(edge.to_id),
                event=latest,
            )
            row["comparison"] = [
                {
                    "endpoint": side,
                    "name": item.name,
                    "status": item.status.value,
                    "recorded": _outcome.anchor_display(item.recorded, verbose=verbose),
                    "current": _outcome.anchor_display(item.current, verbose=verbose),
                }
                for side, hashes in (("from", comparison.from_hashes), ("to", comparison.to_hashes))
                for item in hashes
            ]
    return row


def _print_status(rows: list[dict[str, object]]) -> None:
    for row in rows:
        head = f"{row['from']} --[{row['kind']}]--> {row['to']}"
        if "state" not in row:
            print(f"{head}  vanished from the current stream")
            continue
        print(f"{head} ({row['state']})")
        for item in row.get("comparison", []) or []:
            recorded = item["recorded"] if item["recorded"] is not None else "—"
            current = item["current"] if item["current"] is not None else "—"
            print(
                f"  {item['endpoint']} {item['name']}: {recorded} → {current} "
                f"({item['status']})"
            )


__all__ = [
    "add_check_arguments",
    "add_status_arguments",
    "handle_check",
    "handle_status",
]
