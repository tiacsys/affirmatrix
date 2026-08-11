"""The affirmation store's refusal type.

Its own module so that layout, atomicity, serialization and validation can all
raise it without any of them importing the component's public face.
"""

from __future__ import annotations


class AffirmationStoreError(Exception):
    """The affirmation store refuses to write, or cannot read what is there.

    Named in full rather than ``StoreError``, which the would-be store already
    uses. The two stores hold opposite things — one content, one hashes and
    references — and a shared word for their failures would be the first step
    towards a shared word for them (ADR-0004).
    """


class DemotionNotRequestedError(AffirmationStoreError):
    """A write and its demotion request disagree about which edges lose standing.

    Raised when a write would replace an edge record carrying the hash it was
    affirmed against with one carrying none, and no demotion request names that
    edge (SEG-SREQ-051) — and equally when a request names an edge the write
    does not demote, because a request that did nothing, silently, is the same
    disagreement seen from the other side. Its own type so a caller can tell
    "name the demotion" apart from every other refusal; still the store's
    refusal type underneath, so nothing that catches that stops catching this.
    """


__all__ = ["AffirmationStoreError", "DemotionNotRequestedError"]
