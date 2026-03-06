import json
import logging

# parse_entities.py
"""Parse the raw LLMEntityLinker output into structured sections.

The expected format is a simple markdown‑like hierarchy where a heading line
contains the category name (e.g. ``## Persons``) followed by a list of entries.
Each entry is typically of the form ``- Label (Q123)`` but the Q‑ID part may be
missing.

The parser returns a dictionary mapping a *canonical* category name (lower‑case) to
a list of ``Entity`` dicts with the keys ``label`` and ``qid`` (optional).
"""

import re
from typing import Dict, List, TypedDict, Optional


class Entity(TypedDict, total=False):
    label: str
    qid: Optional[str]
    raw: str  # original line, useful for debugging

# Mapping of the headings we care about – the file may use slightly different
# phrasing; we normalise to the canonical list used later.
CATEGORY_ALIASES = {
    "persons": "persons",
    "people": "persons",
    "places": "places",
    "institutions": "institutions",
    "publishers": "publishers",
    "works": "works",
    "events": "events",
    "citations": "citations",
}

# Regex to capture a label optionally followed by a Q‑ID like (Q123).
ENTRY_RE = re.compile(r"^[-*+]\s+(?P<label>.+?)(?:\s+\((?P<qid>Q\d+)\))?\s*$")


def normalize_heading(heading: str) -> Optional[str]:
    """Return a canonical category name for a heading or ``None`` if unknown.

    The heading string may contain leading ``#`` characters and whitespace.
    """
    # Strip markdown heading markers and whitespace
    heading = heading.lstrip("#").strip().lower()
    return CATEGORY_ALIASES.get(heading)


import json
import logging

def parse_sections(lines: List[str]) -> Dict[str, List[Entity]]:
    """Parse a list of lines into a dict of category → list of :class:`Entity`.

    Supports two formats:
    1. Markdown‑style headings (``## Persons``) with ``- label (Q123)`` entries.
    2. JSON blocks introduced by ``Final linked entities for text X:`` as produced by
       the LLMEntityLinker. Each block is a JSON object where the keys are the
       canonical categories and the values map a label to a list of dictionaries
       that may contain a ``qid`` field.
    """
    # Initialise an empty result for all known categories.
    result: Dict[str, List[Entity]] = {cat: [] for cat in CATEGORY_ALIASES.values()}
    current_cat: Optional[str] = None
    json_mode = False
    json_buffer: List[str] = []
    brace_balance = 0

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        # ------------------------------------------------------------------
        # Detect the start of a JSON block produced by the LLMEntityLinker.
        # ------------------------------------------------------------------
        if line.startswith("Final linked entities for text"):
            json_mode = True
            json_buffer = []
            brace_balance = 0
            continue
        if json_mode:
            # Update brace balance to know when the JSON object ends.
            brace_balance += raw_line.count('{')
            brace_balance -= raw_line.count('}')
            json_buffer.append(raw_line)
            if brace_balance == 0:
                # Attempt to parse the accumulated JSON block.
                try:
                    block_str = "\n".join(json_buffer)
                    data = json.loads(block_str)
                except json.JSONDecodeError as e:
                    logging.warning("Failed to parse JSON block: %s", e)
                else:
                    for cat_key, entries in data.items():
                        cat = CATEGORY_ALIASES.get(cat_key.lower())
                        if not cat:
                            continue
                        for label, obj_list in entries.items():
                            if isinstance(obj_list, list) and obj_list:
                                for obj in obj_list:
                                    qid = obj.get('qid') if isinstance(obj, dict) else None
                                    entity: Entity = {'label': label, 'raw': raw_line}
                                    if qid:
                                        entity['qid'] = qid
                                    result[cat].append(entity)
                            else:
                                result[cat].append({'label': label, 'raw': raw_line})
                # Reset for next block
                json_mode = False
                json_buffer = []
                brace_balance = 0
            continue
        # ---------------------------------------------------------------
        # Markdown‑style parsing (fallback).
        # ---------------------------------------------------------------
        if line.startswith("#"):
            cat = normalize_heading(line)
            current_cat = cat if cat else None
            continue
        if current_cat:
            m = ENTRY_RE.match(line)
            if m:
                label = m.group('label').strip()
                qid = m.group('qid')
                entity: Entity = {'label': label, 'raw': raw_line}
                if qid:
                    entity['qid'] = qid
                result[current_cat].append(entity)
            else:
                result[current_cat].append({'label': line, 'raw': raw_line})
    return result
