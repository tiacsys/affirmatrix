"""Record-source adapters — the implementations behind the input seam.

Container package, not a component: the components are the adapters inside it.
Each turns some outside thing into the record stream the engine consumes, and
each emits *content hashes*, never content — producers hash.

This is the only package that changes when iteration 0's hand-authored store is
replaced by real extraction. That is what makes the adapters' interchangeability
a demonstrated property rather than an asserted one.

Nothing here may import ``affirmatrix.graph``: adapters sit below the graph.

The one thing the package itself defines is :class:`SourceError`, the base every
adapter's own error derives from.
"""


from __future__ import annotations


class SourceError(Exception):
    """A record source cannot supply its stream.

    The common base of every error an adapter raises for an input it cannot
    read, so a caller that only needs to say "this producer cannot be judged"
    catches one type, whether the failure came when the source was built or
    while its records were being taken.
    """


__all__ = ["SourceError"]
