"""CLI Ingestion Tool for Kavach.

Ingests all PDFs and documents in data/raw/ into the local persistent vector store.
Usage:
    python scripts/ingest.py [optional_directory_path]
"""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.config import get_settings
from src.ingestion.loader import load_documents_from_dir
from src.ingestion.chunker import chunk_documents
from src.ingestion.indexer import get_indexer


def main():
    settings = get_settings()
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(settings.raw_docs_dir)

    print(f"🛡️ Kavach Sovereign Ingestion Starting...")
    print(f"Target Directory: {target_dir}")

    if not target_dir.exists():
        print(f"Directory {target_dir} does not exist. Creating it...")
        target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load documents
    pages = load_documents_from_dir(target_dir)
    print(f"Loaded {len(pages)} page(s) from local storage.")

    if not pages:
        print("No documents found to ingest. Place confidential PDFs into data/raw/.")
        return

    # 2. Chunk documents with clearance rank detection
    # Map detected clearance labels to numeric ranks for Zero-Trust filtering
    CLEARANCE_LABEL_TO_RANK = {
        "secret": 3,
        "confidential": 2,
        "restricted": 2,
        "public": 1,
    }

    chunks = chunk_documents(
        pages=pages,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        extra_metadata={
            "uploaded_by_role": "CLI",
            "clearance_rank": 1,  # Default; per-chunk rank set below
        },
    )

    # Stamp per-chunk clearance_rank from the detected clearance label
    for chunk in chunks:
        label = chunk.metadata.get("clearance", "public")
        chunk.metadata["clearance_rank"] = CLEARANCE_LABEL_TO_RANK.get(label, 1)

    print(f"Generated {len(chunks)} text chunk(s) (size={settings.chunk_size}, overlap={settings.chunk_overlap}).")

    # 3. Embed & Index into Vector Store
    indexer = get_indexer()
    indexed_count = indexer.index_chunks(chunks)
    print(f"✅ Successfully indexed {indexed_count} chunks into {settings.vectorstore_dir}.")
    print(f"Total chunks in persistent store: {indexer.count()}")


if __name__ == "__main__":
    main()
