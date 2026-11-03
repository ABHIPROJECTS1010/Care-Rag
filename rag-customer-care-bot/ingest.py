"""
ingest.py
Loads the knowledge base and splits it into clean, retrievable chunks.

Chunking strategy chosen: Q&A-block-based splitting.
Why: Our knowledge base is FAQ-style, where each Q&A pair is a complete,
self-contained unit of meaning. Splitting on blank lines between blocks
keeps each chunk semantically whole (no cut-off questions or answers),
while staying small enough for precise retrieval — unlike section-based
chunking (too coarse, mixes multiple topics per chunk) or fixed-size
chunking (risks cutting a Q&A pair across a chunk boundary).
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_BASE_PATH = os.path.join(BASE_DIR, "data", "knowledge_base.txt")


def load_and_chunk(file_path: str = KNOWLEDGE_BASE_PATH) -> list[str]:
    """
    Loads the knowledge base file and splits it into Q&A-block chunks.

    Returns:
        A list of strings, each one a complete Q&A block.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    chunks = [
        chunk.strip()
        for chunk in raw_text.split("\n\n")
        if chunk.strip()
        and not chunk.strip().startswith("===")
        and not chunk.strip().startswith("Care-RAG")
        and not chunk.strip().startswith("TechNest")
    ]

    return chunks


if __name__ == "__main__":
    # Quick sanity check when running this file directly
    chunks = load_and_chunk()
    print(f"Loaded {len(chunks)} chunks from {KNOWLEDGE_BASE_PATH}\n")
    for i, chunk in enumerate(chunks[:3], start=1):
        print(f"--- Chunk {i} ---\n{chunk}\n")
