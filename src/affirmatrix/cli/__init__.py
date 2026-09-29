"""The command-line interface — a thin layer over the library.

``affirmatrix <noun> <verb>`` (SEG-SYS-010), configuration from
``affirmatrix.yaml``. The engine is a library with a clean programmatic core
and no logic buried in command handlers, so a later interface — a web API, a
review UI, a terminal UI — is another thin adapter over the same core rather
than a second implementation of the same rules.

Eleven commands over four nouns: ``case init|check|sync|refresh|remove``,
``graph check|status``, ``edge show|affirm``, ``proof check|generate``. Every
verb's outcome is the library's alone to decide (SEG-SREQ-068); this package
renders that outcome and does no judgement of its own. One shared outcome
vocabulary (:mod:`affirmatrix.cli._outcome`), one edge selection grammar
(:mod:`affirmatrix.cli._selector`), one judgement-inputs resolver
(:mod:`affirmatrix.cli._judgement`) that also holds the three read-only
repository operations (:mod:`affirmatrix.cli._repository`), and one module
per noun.

Iteration-0 backlog item B19.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path

from affirmatrix import config as _config
from affirmatrix.case import AffirmationStore
from affirmatrix.cli import _case, _edge, _graph, _judgement, _outcome, _proof


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, dispatch to the named verb's handler, and return its exit status.

    :implements: SEG-SREQ-068

    The one place a noun/verb pair resolves to a handler and the handler is
    called; nothing here judges anything the library did not already decide.
    Global options (``--case``, ``--config``) are read before the case is
    opened; a verb's own options are its module's to add.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"affirmatrix {_version()}")
        return _outcome.exit_for(_outcome.POSITIVE)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return _outcome.exit_for(_outcome.INDETERMINATE)
    given_config = getattr(args, "config", None)
    given_case = getattr(args, "case", None)
    config_path = Path(given_config) if given_config else _config.DEFAULT_CONFIG_PATH
    args.config_path = config_path
    try:
        resolved_config = _config.load(config_path, case=Path(given_case) if given_case else None)
    except _config.ConfigError as error:
        _outcome.render_refusal(str(error), as_json=getattr(args, "json", False))
        return _outcome.exit_for(_outcome.INDETERMINATE)
    store = AffirmationStore(root=resolved_config.case)
    try:
        return handler(args, resolved_config, store)
    except _judgement.JudgementError as error:
        _outcome.render_refusal(str(error), as_json=getattr(args, "json", False))
        return _outcome.exit_for(_outcome.INDETERMINATE)


def _global_options() -> argparse.ArgumentParser:
    """``--case``/``--config`` as a parent every leaf subparser shares.

    Registered on the top parser and every noun and verb subparser, so both
    ``affirmatrix --case X case init`` and ``affirmatrix case init --case X``
    work — an operator should not have to remember which side of the noun a
    global option belongs on. ``default=SUPPRESS`` at every level is load
    bearing: without it, a deeper subparser's own default (unset) would
    overwrite a value the outer parser already read, since each level's
    ``parse_args`` re-applies its own defaults to the shared namespace in
    turn. With it, a level only touches the namespace when the operator
    actually gave the flag at that level.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--case",
        default=argparse.SUPPRESS,
        help="the case root (default from configuration, then ./case)",
    )
    parent.add_argument(
        "--config",
        default=argparse.SUPPRESS,
        help="the configuration file (default ./affirmatrix.yaml)",
    )
    return parent


def _build_parser() -> argparse.ArgumentParser:
    globals_ = _global_options()
    parser = argparse.ArgumentParser(prog="affirmatrix", parents=[globals_])
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    nouns = parser.add_subparsers(dest="noun")

    case_parser = nouns.add_parser("case", parents=[globals_])
    case_verbs = case_parser.add_subparsers(dest="verb")

    init_verb = case_verbs.add_parser("init", parents=[globals_])
    init_verb.set_defaults(handler=_case.handle_init, json=False)

    check_verb = case_verbs.add_parser("check", parents=[globals_])
    _add_json(check_verb)
    _case.add_check_arguments(check_verb)
    check_verb.set_defaults(handler=_case.handle_check)

    sync_verb = case_verbs.add_parser("sync", parents=[globals_])
    _case.add_sync_arguments(sync_verb)
    sync_verb.set_defaults(handler=_case.handle_sync, json=False)

    refresh_verb = case_verbs.add_parser("refresh", parents=[globals_])
    _add_json(refresh_verb)
    refresh_verb.set_defaults(handler=_case.handle_refresh)

    remove_verb = case_verbs.add_parser("remove", parents=[globals_])
    _case.add_remove_arguments(remove_verb)
    remove_verb.set_defaults(handler=_case.handle_remove, json=False)

    graph_parser = nouns.add_parser("graph", parents=[globals_])
    graph_verbs = graph_parser.add_subparsers(dest="verb")

    graph_check_verb = graph_verbs.add_parser("check", parents=[globals_])
    _add_json(graph_check_verb)
    _graph.add_check_arguments(graph_check_verb)
    graph_check_verb.set_defaults(handler=_graph.handle_check)

    graph_status_verb = graph_verbs.add_parser("status", parents=[globals_])
    _add_json(graph_status_verb, verbose=True)
    _graph.add_status_arguments(graph_status_verb)
    graph_status_verb.set_defaults(handler=_graph.handle_status)

    edge_parser = nouns.add_parser("edge", parents=[globals_])
    edge_verbs = edge_parser.add_subparsers(dest="verb")

    edge_show_verb = edge_verbs.add_parser("show", parents=[globals_])
    _add_json(edge_show_verb, verbose=True)
    _edge.add_show_arguments(edge_show_verb)
    edge_show_verb.set_defaults(handler=_edge.handle_show)

    edge_affirm_verb = edge_verbs.add_parser("affirm", parents=[globals_])
    _edge.add_affirm_arguments(edge_affirm_verb)
    edge_affirm_verb.set_defaults(handler=_edge.handle_affirm, json=False)

    proof_parser = nouns.add_parser("proof", parents=[globals_])
    proof_verbs = proof_parser.add_subparsers(dest="verb")

    proof_check_verb = proof_verbs.add_parser("check", parents=[globals_])
    _add_json(proof_check_verb)
    _proof.add_check_arguments(proof_check_verb)
    proof_check_verb.set_defaults(handler=_proof.handle_check)

    proof_generate_verb = proof_verbs.add_parser("generate", parents=[globals_])
    _proof.add_generate_arguments(proof_generate_verb)
    proof_generate_verb.set_defaults(handler=_proof.handle_generate, json=False)

    return parser


def _version() -> str:
    """The installed package version, or ``unknown`` outside an installed distribution.

    Read at call time rather than import time, and never via
    ``sys.exit`` — argparse's own ``version`` action exits the process,
    which a caller running ``main`` in-process for its return value cannot
    observe.
    """
    try:
        return metadata.version("affirmatrix")
    except metadata.PackageNotFoundError:
        return "unknown"


def _add_json(parser: argparse.ArgumentParser, *, verbose: bool = False) -> None:
    """Register ``--json`` (SEG-SREQ-098), and ``-v`` where a verb renders hashes.

    Read-only verbs only: a write verb's own subparser never calls this, so
    its namespace gets ``json=False`` from :func:`_build_parser`'s own
    defaults instead of a flag nobody asked to see the shape of.
    """
    parser.add_argument("--json", action="store_true", help="a structured rendering of the report")
    if verbose:
        parser.add_argument(
            "-v", "--verbose", action="store_true", help="full hashes and before-content"
        )
    else:
        parser.set_defaults(verbose=False)


__all__ = ["main"]
