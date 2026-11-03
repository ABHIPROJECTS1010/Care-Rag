import os

# Disable third-party telemetry calls (Privacy & Data Loss Prevention — SEC-11)
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"
os.environ["DO_NOT_TRACK"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import chromadb
from chromadb.utils import embedding_functions
from ingest import load_and_chunk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

# Step 1: Load our chunks from Day 2's work
chunks = load_and_chunk()

# Step 2: Set up the embedding function (free, local model)
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

# Step 3: Create a persistent ChromaDB client (saves to disk in ./chroma_db)
client = chromadb.PersistentClient(path=CHROMA_PATH)

# Step 4: Create (or get) a collection to store our chunks
collection = client.get_or_create_collection(
    name="care_rag_faq",
    embedding_function=embedding_fn
)

# Step 5: Add chunks to the collection (only if not already added)
existing_count = collection.count()
if existing_count == 0:
    collection.add(
        documents=chunks,
        ids=[f"chunk_{i}" for i in range(len(chunks))]
    )
    print(f"Added {len(chunks)} chunks to ChromaDB.\n")


def search(query: str, top_k: int = 3, distance_threshold: float = 0.75):
    """
    Search the vector store for relevant chunks to a query.
    Filters out results above the distance_threshold (i.e. not actually relevant).
    Clamps inputs to prevent unexpected resource allocation.
    """
    safe_top_k = max(1, min(10, int(top_k)))
    safe_threshold = max(0.0, min(2.0, float(distance_threshold)))
    safe_query = str(query)[:1000].strip() if query else ""
    if not safe_query:
        return []

    results = collection.query(
        query_texts=[safe_query],
        n_results=safe_top_k
    )
    docs = results["documents"][0]
    distances = results["distances"][0]

    # Keep only results below the threshold (closer = more relevant)
    relevant = [(doc, dist) for doc, dist in zip(docs, distances) if dist <= safe_threshold]

    return relevant


if __name__ == "__main__":
    # Quick sanity check
    test_results = search("How do I track my order?", top_k=3)
    print(f"\nFound {len(test_results)} relevant results:")
    for doc, dist in test_results:
        print(f"\n(distance: {dist:.4f}) {doc[:150]}")
