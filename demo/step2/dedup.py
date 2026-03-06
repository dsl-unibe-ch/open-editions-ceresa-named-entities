# dedup.py
"""Deduplication utilities for parsed entities.

Two entities are considered the same when they share the same QID (if present) or
when their normalized label is identical (case‑folded, Unicode‑NFC). The function
returns a cleaned mapping category → list of unique entities. When the same QID
appears in multiple categories the most specific category is kept – the order
defined in ``CATEGORY_PRIORITY`` determines which category wins.
"""

import unicodedata
from typing import Dict, List, Set, Tuple, Optional

from parse_entities import Entity, CATEGORY_ALIASES

# Priority order – earlier entries win when a QID appears in more than one category.
CATEGORY_PRIORITY = [
    "persons",
    "places",
    "institutions",
    "publishers",
    "works",
    "events",
    "citations",
]


def _norm_label(label: str) -> str:
    """Return a canonical representation of *label* for deduplication.

    Unicode normalization (NFC) and case‑folding are applied.
    """
    return unicodedata.normalize("NFC", label).casefold().strip()


def canonical_key(entity: Entity) -> Tuple[Optional[str], str]:
    """Return a tuple that can be used as a deduplication key.

    The first element is the QID (or ``None``) and the second is the normalized
    label. This allows a QID to take precedence but also falls back to the label.
    """
    qid = entity.get("qid")
    label = entity.get("label", "")
    return (qid, _norm_label(label))


def deduplicate(sections: Dict[str, List[Entity]]) -> Dict[str, List[Entity]]:
    """Deduplicate entities across and within categories.

    The algorithm works in two passes:
    1. Build a global map of key → (entity, category) keeping the highest‑priority
       category for duplicates.
    2. Re‑populate the per‑category lists from that map.
    """
    # Global map: key -> (entity, category)
    global_map: Dict[Tuple[Optional[str], str], Tuple[Entity, str]] = {}
    for cat, ents in sections.items():
        for ent in ents:
            key = canonical_key(ent)
            if key in global_map:
                # Resolve category conflict using priority list
                _, existing_cat = global_map[key]
                if CATEGORY_PRIORITY.index(cat) < CATEGORY_PRIORITY.index(existing_cat):
                    global_map[key] = (ent, cat)
            else:
                global_map[key] = (ent, cat)

    # Re‑assemble per‑category lists
    deduped: Dict[str, List[Entity]] = {c: [] for c in CATEGORY_PRIORITY}
    for (entity, cat) in global_map.values():
        deduped[cat].append(entity)
    return deduped
