"""The edge noun: inspect a selection, and affirm it (SEG-SREQ-084).

``edge show`` renders the per-hash comparison and, for an affirmed edge,
recovered before-content; ``edge affirm`` records an affirmation over every
affirmable member of a selection.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping

from affirmatrix import affirmation, drift, graph, taxonomy
from affirmatrix.case import AffirmationStore
from affirmatrix.cli import _extraction, _judgement, _outcome, _selector
from affirmatrix.config import Config
from affirmatrix.records import EdgeReference, LinkState
from affirmatrix.sources import SourceError

_RE_AFFIRMATION_TAGS = {
    LinkState.PENDING: "needs affirmation",
    LinkState.DIRECTLY_OUTDATED: "needs re-affirmation",
    LinkState.DOUBLY_OUTDATED: "needs re-affirmation",
}

_STATE_REASONS = {
    LinkState.ACTIVE: "it is active — nothing to affirm",
    LinkState.TRANSITIVELY_SUSPECT: "it clears by recomputation, not by a new affirmation",
    LinkState.BROKEN: "an endpoint is missing from the current records",
}


def add_show_arguments(parser: argparse.ArgumentParser) -> None:
    _selector.add_selector_arguments(parser)
    parser.add_argument("--current", help="the producer supplying the current stream")


def add_affirm_arguments(parser: argparse.ArgumentParser) -> None:
    """Register ``edge affirm``'s own arguments.

    :implements: SEG-SREQ-106

    ``--role``/``--reason`` are both ``required=True`` — including when the
    reason is empty, which ``required`` still accepts as a given value —
    so neither is ever silently defaulted.
    """
    _selector.add_selector_arguments(parser)
    parser.add_argument("--current", help="the producer supplying the current stream")
    parser.add_argument("--role", required=True, help="the capacity the affirmation is made in")
    parser.add_argument("--reason", required=True, help="the justification, may be empty")
    parser.add_argument("--revision", help="record this revision as given, for every endpoint")


def handle_show(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Render the per-hash comparison and recovered before-content.

    :implements: SEG-SREQ-085
    :implements: SEG-SREQ-103
    """
    built, error_status = _build(args, config, store)
    if built is None:
        return error_status
    matched = _selector.select(built.edges, _selector.selector_from_args(args), built)
    if not matched:
        _outcome.render_refusal("the selector matched no edge", as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    rows = [_shown(built, edge, store, config, verbose=args.verbose) for edge in matched]
    if args.json:
        _outcome.render_json({"edges": rows})
    else:
        _print_shown(rows)
    return _outcome.exit_for(_outcome.POSITIVE)


def handle_affirm(args: argparse.Namespace, config: Config, store: AffirmationStore) -> int:
    """Record an affirmation over every affirmable member of a selection.

    :implements: SEG-SREQ-086
    :implements: SEG-SREQ-087
    :implements: SEG-SREQ-088
    :implements: SEG-SREQ-103
    :implements: SEG-SREQ-104

    Two kinds of "cannot" are kept apart. The role is one input for the
    whole invocation, checked once before any edge is even looked at; a
    revision that cannot be resolved for an affirmable edge's endpoint is
    the same kind of failure, one this invocation cannot proceed past —
    either refuses the whole request (exit 2), nothing written, before the
    recorder is asked to compose anything. Only the recorder's own
    signposts — :func:`~affirmatrix.affirmation.affirmable` finding a state
    or kind it cannot resolve, :class:`~affirmatrix.affirmation.AffirmationError`
    from :func:`~affirmatrix.affirmation.compose` itself — land in the
    per-edge "not affirmed" list the 0/1 verdict (SEG-SREQ-087/088) reads.

    The endpoint node records are written with their extraction revisions, by
    the rule of :mod:`affirmatrix.cli._extraction`. A revision given with
    ``--revision`` goes into the review event only, never into a node record.
    After the affirmed lines, one line names each repository that has node
    records written without a revision.
    """
    selector = _selector.selector_from_args(args)
    if selector.is_empty():
        _outcome.render_refusal("edge affirm requires an explicit selector", as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    built, error_status = _build(args, config, store)
    if built is None:
        return error_status
    matched = _selector.select(built.edges, selector, built)
    if not matched:
        _outcome.render_refusal("the selector matched no edge", as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)
    try:
        _judgement.check_role(args.role, config)
    except _judgement.JudgementError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return _outcome.exit_for(_outcome.INDETERMINATE)

    not_affirmed: list[dict[str, str]] = [
        {"edge": _label(edge), "reason": _state_reason(edge)}
        for edge in matched
        if not affirmation.affirmable(edge.state, edge.kind)
    ]
    affirmable_edges = [edge for edge in matched if affirmation.affirmable(edge.state, edge.kind)]

    composed: list[affirmation.Affirmation] = []
    for edge in affirmable_edges:
        from_node = built.node(edge.from_id)
        to_node = built.node(edge.to_id)
        try:
            from_revision = _judgement.resolve_revision(
                from_node, config=config, given=args.revision, label=edge.from_id
            )
            to_revision = _judgement.resolve_revision(
                to_node, config=config, given=args.revision, label=edge.to_id
            )
        except _judgement.JudgementError as error:
            _outcome.render_refusal(str(error), as_json=args.json)
            return _outcome.exit_for(_outcome.INDETERMINATE)
        try:
            affirmed = affirmation.compose(
                edge,
                from_node=from_node,
                to_node=to_node,
                role=args.role,
                reason=args.reason,
                from_source_revision=from_revision,
                to_source_revision=to_revision,
            )
        except affirmation.AffirmationError as error:
            not_affirmed.append({"edge": _label(edge), "reason": str(error)})
            continue
        composed.append(affirmed)

    missing: Mapping[str, int] = {}
    if composed:
        endpoint_nodes = {}
        for one in composed:
            endpoint_nodes[one.event.from_id] = built.node(one.event.from_id)
            endpoint_nodes[one.event.to_id] = built.node(one.event.to_id)
        held = {node.local_id: node for node in store.nodes()}
        stamped = _extraction.stamp(endpoint_nodes.values(), held, config)
        missing = stamped.missing
        store.write_nodes(stamped.nodes)
        store.write_edges([one.edge for one in composed])
        store.append_review_events([one.event for one in composed])

    report = {
        "affirmed": [_label(one.edge) for one in composed],
        "notAffirmed": not_affirmed,
    }
    if args.json:
        _outcome.render_json(report)
    else:
        for one in composed:
            print(f"affirmed: {_label(one.edge)}")
        _extraction.report(missing)
        for entry in not_affirmed:
            print(f"not affirmed: {entry['edge']} ({entry['reason']})")
    return _outcome.exit_for(_outcome.POSITIVE if composed else _outcome.NEGATIVE)


def _build(args: argparse.Namespace, config: Config, store: AffirmationStore):
    """The built graph over both streams, or ``(None, exit_status)`` on refusal."""
    try:
        current = _judgement.resolve_current(args.current, config)
    except _judgement.JudgementError as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return None, _outcome.exit_for(_outcome.INDETERMINATE)
    try:
        derivation = drift.derive(recorded=store, current=current)
        built = graph.build(derivation)
    except (graph.GraphError, drift.DriftError, SourceError) as error:
        _outcome.render_refusal(str(error), as_json=args.json)
        return None, _outcome.exit_for(_outcome.INDETERMINATE)
    return built, None


def _label(edge) -> str:
    return f"{edge.from_id} -> {edge.to_id} ({edge.kind})"


def _state_reason(edge) -> str:
    if edge.kind not in taxonomy.propagating_edge_kinds():
        return "an evidence edge is resolved by re-execution, not by a judgement"
    return _STATE_REASONS.get(edge.state, "not affirmable")


def _shown(built, edge, store: AffirmationStore, config: Config, *, verbose: bool) -> dict:
    row: dict[str, object] = {
        "from": edge.from_id,
        "to": edge.to_id,
        "kind": edge.kind,
        "state": edge.state.value,
    }
    if edge.kind in taxonomy.propagating_edge_kinds():
        tag = _RE_AFFIRMATION_TAGS.get(edge.state)
        if tag:
            row["tag"] = tag
    if edge.edge_hash is not None and edge.state is not LinkState.BROKEN:
        reference = EdgeReference(kind=edge.kind, from_id=edge.from_id, to_id=edge.to_id)
        latest = store.latest_review_event(reference)
        if latest is not None:
            comparison = drift.compare(
                reference,
                current_from=built.node(edge.from_id),
                current_to=built.node(edge.to_id),
                event=latest,
            )
            row["comparison"] = _rendered_comparison(comparison, verbose=verbose)
            if verbose:
                row["beforeContent"] = {
                    "from": _before_content_entry(
                        built.node(edge.from_id), latest.from_source_revision, config
                    ),
                    "to": _before_content_entry(
                        built.node(edge.to_id), latest.to_source_revision, config
                    ),
                }
    return row


def _rendered_comparison(comparison, *, verbose: bool) -> list[dict[str, object]]:
    rows = []
    for side, hashes in (("from", comparison.from_hashes), ("to", comparison.to_hashes)):
        for item in hashes:
            rows.append(
                {
                    "endpoint": side,
                    "name": item.name,
                    "status": item.status.value,
                    "recorded": _outcome.anchor_display(item.recorded, verbose=verbose),
                    "current": _outcome.anchor_display(item.current, verbose=verbose),
                }
            )
    return rows


def _before_content_entry(node, revision: str, config: Config) -> dict[str, object]:
    """The before-content an endpoint's anchor recovers at ``revision``, headed by it.

    :implements: SEG-SREQ-111

    Carries the revision alongside the recovered bytes (or ``None``, when
    nothing could be recovered) so a renderer can name what was recovered
    at without a second lookup.
    """
    content = _judgement.recover_before_content(node, revision, config)
    return {
        "revision": revision,
        "content": content.decode("utf-8", errors="replace") if content is not None else None,
    }


def _print_shown(rows: list[dict[str, object]]) -> None:
    for row in rows:
        tag = f" [{row['tag']}]" if row.get("tag") else ""
        print(f"{row['from']} --[{row['kind']}]--> {row['to']} ({row['state']}){tag}")
        for item in row.get("comparison", []) or []:
            recorded = item["recorded"] if item["recorded"] is not None else "—"
            current = item["current"] if item["current"] is not None else "—"
            print(
                f"  {item['endpoint']} {item['name']}: {recorded} → {current} "
                f"({item['status']})"
            )
        for endpoint, entry in (row.get("beforeContent") or {}).items():
            if entry["content"] is None:
                continue
            print(f"  before-content @ {endpoint} (revision {entry['revision']}):")
            for line in entry["content"].splitlines() or [""]:
                print(f"    {line}")


__all__ = ["add_affirm_arguments", "add_show_arguments", "handle_affirm", "handle_show"]
