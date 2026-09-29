"""The graph noun: judge consistency, and derive every edge's state (SEG-SREQ-076).

``graph check`` builds one record stream and reports what the builder
knows; ``graph status`` derives every edge's state from both the recorded
and the current streams.
"""

from __future__ import annotations

import argparse
from collections import Counter

from affirmatrix import drift, graph
from affirmatrix.case import AffirmationStore
from affirmatrix.cli import _judgement, _outcome
from affirmatrix.config import Config
from affirmatrix.records import EdgeReference, LinkState, RecordSource
from affirmatrix.sources.store import StoreError

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


def handle_check(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Report node and edge counts by kind, and the count of pending edges.

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
    except (graph.GraphError, StoreError) as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.NEGATIVE)
    node_counts = Counter(built.node(local_id).kind for local_id in built.node_ids())
    edge_counts = Counter(edge.kind for edge in built.edges)
    pending = sum(1 for edge in built.edges if edge.state is LinkState.PENDING)
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
    """Derive every edge's state from both the recorded and current streams.

    :implements: SEG-SREQ-080
    :implements: SEG-SREQ-081
    :implements: SEG-SREQ-082
    :implements: SEG-SREQ-083
    :implements: SEG-SREQ-137
    :implements: SEG-SREQ-138

    Every recorded edge the current stream no longer has is listed after the
    rest, with no state, and takes no part in the verdict, which reads the
    derived edges alone.
    """
    try:
        current = _judgement.resolve_current(args.current, config)
    except _judgement.JudgementError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    try:
        derivation = drift.derive(recorded=store, current=current)
        built = graph.build(derivation)
    except (graph.GraphError, drift.DriftError, StoreError) as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    rows = [_status_row(built, edge, store, verbose=args.verbose) for edge in built.edges]
    rows += [
        _vanished_row(edge)
        for edge in sorted(derivation.vanished, key=lambda e: (e.from_id, e.to_id, e.kind))
    ]
    if args.json:
        _outcome.render_json({"edges": rows})
    else:
        _print_status(rows)
    not_active = {edge.state for edge in built.edges if edge.state is not LinkState.ACTIVE}
    if not_active & _SUSPECT_OR_BROKEN:
        return _outcome.exit_for(_outcome.NEGATIVE)
    return _outcome.exit_for(_outcome.POSITIVE)


def _current_or_case(
    args: argparse.Namespace, config: Config, store: AffirmationStore
) -> RecordSource:
    if args.current is not None:
        return _judgement.resolve_current(args.current, config)
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
