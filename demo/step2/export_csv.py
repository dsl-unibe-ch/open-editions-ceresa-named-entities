# export_csv.py
"""Export enriched entity records to a CSV file.

The function :func:`write_entities_csv` receives the list returned by
``wikidata_fetcher.enrich_entities`` and writes a CSV with a header that
covers all possible columns (label, qid, category plus the union of the
category‑specific property columns). Missing values are written as empty cells.
"""

import csv
from pathlib import Path
from typing import List, Dict, Set

from wikidata_fetcher import CATEGORY_PROPERTIES


def _gather_all_columns(enriched: List[Dict]) -> List[str]:
    """Return the ordered list of CSV column names.

    Base columns are ``label``, ``qid``, ``category`` and ``wikidata_label``.
    Additional columns include:
    * the property columns defined in ``CATEGORY_PROPERTIES``
    * any ``<property>_label`` columns that were added when a property points to
      another Wikidata entity.
    The function builds the union of all these names and returns them in a
    deterministic (alphabetical) order after the base columns.
    """
    base = ["label", "qid", "category", "wikidata_label"]
    extra: Set[str] = set()
    for cat, props in CATEGORY_PROPERTIES.items():
        for _pid, col in props:
            extra.add(col)
            extra.add(f"{col}_label")
    # Also include any custom columns that may have been added dynamically.
    for record in enriched:
        for key in record.keys():
            if key not in base:
                extra.add(key)
    extra_ordered = sorted(extra)
    return base + extra_ordered


def write_entities_csv(enriched: List[Dict], output_path: str = "entities_enriched.csv") -> None:
    """Write *enriched* records to *output_path* as a CSV.

    Parameters
    ----------
    enriched:
        List of dictionaries as produced by ``wikidata_fetcher.enrich_entities``.
    output_path:
        Destination file name (relative to the current working directory).
    """
    if not enriched:
        raise ValueError("No records to write to CSV")
    columns = _gather_all_columns(enriched)
    out_file = Path(output_path)
    with out_file.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for record in enriched:
            # Ensure all expected keys exist (missing -> empty string)
            row = {col: record.get(col, "") for col in columns}
            writer.writerow(row)
