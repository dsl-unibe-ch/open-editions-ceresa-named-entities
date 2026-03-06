# main.py
"""Entry point for the named‑entity enrichment pipeline.

The script performs the following steps:
1. Configure a simple logger that writes to ``pipeline.log``.
2. Load the raw LLMEntityLinker output file.
3. Parse the file into category sections.
4. Deduplicate entries across categories.
5. Enrich the deduplicated entities with Wikidata properties.
6. Export the enriched data to ``entities_enriched.csv``.

Running the script directly:
    python -m main --input path/to/output-gemini3-flash-preview.txt

All output files are written inside the current working directory (the repository
root for this task).
"""

import argparse
import logging
import sys
from pathlib import Path

from load_input import load_file
from parse_entities import parse_sections
from dedup import deduplicate
from wikidata_fetcher import enrich_entities
from export_csv import write_entities_csv


def configure_logging(log_path: Path) -> None:
    """Configure root logger to write INFO level messages to *log_path*.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # Also output to stdout for immediate feedback.
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    logger.addHandler(stream)


def run_pipeline(input_file: str, output_file: str = "entities_enriched.csv") -> None:
    logger = logging.getLogger(__name__)
    logger.info("Pipeline started")
    # 1. Load raw file
    logger.info("Loading input file: %s", input_file)
    lines = load_file(input_file)
    logger.info("Loaded %d lines", len(lines))
    # 2. Parse sections
    logger.info("Parsing sections")
    sections = parse_sections(lines)
    for cat, ents in sections.items():
        logger.info("%s: %d raw entries", cat, len(ents))
    # 3. Deduplicate
    logger.info("Deduplicating entries")
    deduped = deduplicate(sections)
    for cat, ents in deduped.items():
        logger.info("%s: %d unique entries after dedup", cat, len(ents))
    # 4. Enrich with Wikidata
    logger.info("Enriching entities via Wikidata")
    enriched = enrich_entities(deduped)
    logger.info("Enrichment complete – %d total records", len(enriched))
    # 5. Export CSV
    logger.info("Writing CSV to %s", output_file)
    write_entities_csv(enriched, output_path=output_file)
    logger.info("Pipeline finished successfully")


def main() -> None:
    parser = argparse.ArgumentParser(description="Named entity deduplication and Wikidata enrichment pipeline")
    parser.add_argument("--input", required=True, help="Path to the LLMEntityLinker output text file")
    parser.add_argument("--output", default="entities_enriched.csv", help="Output CSV file name")
    parser.add_argument("--log", default="pipeline.log", help="Log file path")
    args = parser.parse_args()

    log_path = Path(args.log)
    configure_logging(log_path)
    run_pipeline(args.input, args.output)


if __name__ == "__main__":
    main()
