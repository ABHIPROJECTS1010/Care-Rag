from langchain_community.document_loaders import TextLoader

# Load the document
loader = TextLoader("data/knowledge_base.txt", encoding="utf-8")
documents = loader.load()

print(f"Number of documents loaded: {len(documents)}")
print(f"First 300 characters:\n{documents[0].page_content[:300]}")

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Strategy 1: Fixed-size chunking
fixed_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=80,
    separators=["\n\n", "\n", ". ", " ", ""]
)

fixed_chunks = fixed_splitter.split_documents(documents)

print(f"\n=== FIXED-SIZE CHUNKING ===")
print(f"Number of chunks: {len(fixed_chunks)}")
print(f"\n--- Sample chunk 1 ---\n{fixed_chunks[0].page_content}")
print(f"\n--- Sample chunk 2 ---\n{fixed_chunks[1].page_content}")

import re

with open("data/knowledge_base.txt", "r", encoding="utf-8") as f:
    raw_text = f.read()

# Split on section headers
sections = re.split(r'=== SECTION \d+: .*? ===', raw_text)
section_titles = re.findall(r'=== SECTION \d+: (.*?) ===', raw_text)

# Drop the leading title chunk (text before the first "=== SECTION ===" marker)
section_chunks = [s.strip() for s in sections if s.strip()][1:] if len(sections) > len(section_titles) else [s.strip() for s in sections if s.strip()]

print(f"\n=== SECTION-BASED CHUNKING ===")
print(f"Number of chunks: {len(section_chunks)}")
print(f"\n--- Sample chunk 1 (Section: {section_titles[0]}) ---\n{section_chunks[0][:500]}")

# Strategy 3: Q&A-block-based chunking (best fit for this FAQ structure)
qa_chunks = [chunk.strip() for chunk in raw_text.split("\n\n") if chunk.strip() and not chunk.strip().startswith("===") and not chunk.strip().startswith("Care-RAG") and not chunk.strip().startswith("TechNest")]

print(f"\n=== Q&A-BLOCK CHUNKING ===")
print(f"Number of chunks: {len(qa_chunks)}")
print(f"\n--- Sample chunk 1 ---\n{qa_chunks[0]}")
print(f"\n--- Sample chunk 2 ---\n{qa_chunks[1]}")