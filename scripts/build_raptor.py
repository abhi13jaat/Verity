"""
Build RAPTOR summary nodes from all ingested chunks.

RAPTOR (Recursive Abstractive Processing for Tree-Organized Retrieval):
  - Clusters all base chunks by embedding similarity
  - Summarizes each cluster with an LLM
  - Stores summaries in Qdrant as level-1 nodes

These high-level summaries help answer broad questions that require
synthesizing information from many documents.

Usage:
    python -m scripts.build_raptor               # all domains
    python -m scripts.build_raptor --domain ml   # only ml domain chunks
"""

import argparse

from backend.db.qdrant_client import init_collection
from backend.ingestion.raptor.summarizer import build_raptor_summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RAPTOR summaries for Verity")
    parser.add_argument("--domain", default=None, help="Limit to a specific domain (e.g. ml, bio)")
    args = parser.parse_args()

    print("\n=== RAPTOR Summary Builder ===\n")
    init_collection()

    domain_label = args.domain or "all domains"
    print(f"Building summaries for: {domain_label}\n")

    n = build_raptor_summaries(domain=args.domain)
    print(f"\nDone — {n} summary nodes added to Qdrant.")


if __name__ == "__main__":
    main()
