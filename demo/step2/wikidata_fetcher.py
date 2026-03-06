# wikidata_fetcher.py
"""Fetch supplemental data from Wikidata for a set of QIDs.

The module contains a small mapping ``CATEGORY_PROPERTIES`` that defines which
Wikidata property IDs (Pxxx) we want for each entity category. The function
:func:`enrich_entities` takes the deduplicated mapping produced by ``dedup`` and
returns a list of enriched records ready for CSV export.

Rate‑limiting and simple retry logic are implemented – the public SPARQL
endpoint allows a few requests per second. Batching is performed with a default of
50 QIDs per request.
"""

import json
import logging
import time
from itertools import islice
from typing import Dict, List, Set, Tuple

import requests

# Simple logger – the calling script can configure the root logger to write to a
# file; we just obtain a module‑level logger.
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Property configuration per category. The keys are the canonical category names
# used throughout the pipeline. Each value is a list of ``(property_id, column_name)``.
# Adjust as needed – additional properties can be added without code changes.
# ---------------------------------------------------------------------------
CATEGORY_PROPERTIES: Dict[str, List[Tuple[str, str]]] = {
    "persons": [
        ("P569", "date_of_birth"),
        ("P570", "date_of_death"),
        ("P106", "occupation"),
        ("P27", "country_of_citizenship"),
    ],
    "places": [
        ("P31", "instance_of"),
        ("P625", "coordinates"),
        ("P17", "country"),
    ],
    "institutions": [
        ("P31", "instance_of"),
        ("P159", "headquarters_location"),
        ("P571", "inception"),
    ],
    "publishers": [
        ("P31", "instance_of"),
        ("P159", "headquarters_location"),
        ("P112", "founded_by"),
    ],
    "works": [
        ("P31", "instance_of"),
        ("P50", "author"),
        ("P577", "publication_date"),
    ],
    "events": [
        ("P31", "instance_of"),
        ("P580", "start_time"),
        ("P582", "end_time"),
        ("P276", "location"),
    ],
    "citations": [
        ("P1476", "title"),
        ("P356", "doi"),
        ("P1433", "published_in"),
    ],
}

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
BATCH_SIZE = 50
RETRY_COUNT = 3
RETRY_DELAY = 2  # seconds


def _build_sparql(qids: List[str], properties: List[Tuple[str, str]]) -> str:
    """Return a SPARQL query that fetches ``properties`` for each QID in ``qids``.

    The query uses ``VALUES`` to bind the QIDs and optional ``SERVICE wikibase:label``
    to retrieve English labels for any property values that are entities.
    """
    # Build the property part – each property is optional (PLACEHOLDER) to avoid
    # dropping rows when a value is missing.
    optional_clauses = []
    for pid, _col in properties:
        optional_clauses.append(
            f"OPTIONAL {{ ?item wdt:{pid} ?{pid}_val . SERVICE wikibase:label {{ bd:serviceParam wikibase:language \"en\" . OPTIONAL {{ ?{pid}_val rdfs:label ?{pid}_valLabel . }} }} }}"
        )
    optional_block = "\n".join(optional_clauses)

    # Prefix each QID with the wd: namespace for the VALUES clause
    values_block = " ".join([f"wd:{qid}" for qid in qids])
    query = f"""
SELECT ?item {' '.join([f'?{pid}_val ?{pid}_valLabel' for pid, _ in properties])} WHERE {{
  VALUES ?item {{ {values_block} }}
  {optional_block}
}}
"""
    return query


def _run_sparql(query: str) -> List[Dict[str, str]]:
    """Execute *query* against the public Wikidata SPARQL endpoint.

    Retries are performed on network errors or HTTP status != 200.
    Returns a list of result dicts where keys are the variable names from the query.
    """
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "goose-wikidata-fetcher/0.1 (https://github.com/blockai/goose)"
    }
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            resp = requests.post(SPARQL_ENDPOINT, data={"query": query}, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", {}).get("bindings", [])
            else:
                logger.warning("SPARQL request failed (status %s). Attempt %d/%d", resp.status_code, attempt, RETRY_COUNT)
        except Exception as e:
            logger.warning("SPARQL request exception: %s (attempt %d/%d)", e, attempt, RETRY_COUNT)
        time.sleep(RETRY_DELAY)
    raise RuntimeError("Failed to fetch data from Wikidata after multiple attempts")


def enrich_entities(deduped: Dict[str, List[Dict]]) -> List[Dict]:
    """Enrich the deduplicated entity mapping with Wikidata properties.

    This version uses the Wikidata EntityData JSON API (https://www.wikidata.org/wiki/Special:EntityData/QID.json)
    instead of SPARQL to avoid server‑side 500 errors caused by large or complex queries.
    For each QID we request the entity JSON once and extract the properties defined in
    ``CATEGORY_PROPERTIES``. Entities without a QID are emitted with empty property columns.

    Additionally we retrieve the English Wikidata label for each QID (column ``wikidata_label``)
    and resolve any property values that are themselves Wikidata entity IDs to their
    English labels (column ``<property>_label``). The raw QID is kept in the original
    property column so that both machine‑readable and human‑readable forms are available.
    """
    enriched: List[Dict] = []
    session = requests.Session()
    session.headers.update({
        "User-Agent": "goose-wikidata-fetcher/0.1 (https://github.com/blockai/goose)"
    })
    # Cache for entity label look‑ups to avoid repeated HTTP calls.
    label_cache: Dict[str, str] = {}

    def fetch_entity_json(qid: str) -> Dict:
        """Return the JSON payload for *qid* or an empty dict on failure."""
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.json().get('entities', {}).get(qid, {})
            else:
                logger.warning("Wikidata entity fetch failed for %s (status %s)", qid, resp.status_code)
        except Exception as e:
            logger.warning("Exception while fetching %s: %s", qid, e)
        return {}

    def get_label(qid: str) -> str:
        """Return the English label for *qid*, using the cache when possible."""
        if qid in label_cache:
            return label_cache[qid]
        data = fetch_entity_json(qid)
        label = data.get('labels', {}).get('en', {}).get('value', '')
        label_cache[qid] = label
        return label

    for category, entities in deduped.items():
        props = CATEGORY_PROPERTIES.get(category, [])
        # Entities with QIDs
        for ent in [e for e in entities if e.get('qid')]:
            qid = ent['qid']
            json_data = fetch_entity_json(qid)
            enriched_record = {
                "label": ent.get('label', ''),
                "qid": qid,
                "category": category,
                "wikidata_label": get_label(qid),
            }
            # Extract needed properties
            for pid, col_name in props:
                # The data structure is claims[pid][0]['mainsnak']['datavalue']['value']
                raw_value = ''
                label_value = ''
                claims = json_data.get('claims', {})
                if pid in claims:
                    mainsnak = claims[pid][0].get('mainsnak', {})
                    dv = mainsnak.get('datavalue', {})
                    # Simple handling for common value types
                    if dv.get('type') == 'string':
                        raw_value = dv.get('value', '')
                        label_value = raw_value
                    elif dv.get('type') == 'wikibase-entityid':
                        target_qid = f"Q{dv.get('value', {}).get('numeric-id', '')}"
                        raw_value = target_qid
                        label_value = get_label(target_qid)
                    elif dv.get('type') == 'time':
                        raw_value = dv.get('value', {}).get('time', '')
                        label_value = raw_value
                    elif dv.get('type') == 'quantity':
                        raw_value = str(dv.get('value', {}).get('amount', ''))
                        label_value = raw_value
                enriched_record[col_name] = raw_value
                # also store a human‑readable column if it differs
                if label_value and label_value != raw_value:
                    enriched_record[f"{col_name}_label"] = label_value
            enriched.append(enriched_record)
        # Entities without QID – still output a row with empty extra fields.
        for ent in [e for e in entities if not e.get('qid')]:
            empty_record = {
                "label": ent.get('label', ''),
                "qid": "",
                "category": category,
                "wikidata_label": "",
            }
            for _, col_name in props:
                empty_record[col_name] = ""
                empty_record[f"{col_name}_label"] = ""
            enriched.append(empty_record)
    return enriched
