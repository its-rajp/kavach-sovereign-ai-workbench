"""PDF, CSV, and Text Document Loader for Kavach Ingestion.

Extracts text and page metadata locally with no external network calls.
Supports PDF, TXT, CSV, and Markdown classified files.
"""

from pathlib import Path
from typing import List, Dict, Any
import csv
import PyPDF2


def load_pdf_document(pdf_path: Path) -> List[Dict[str, Any]]:
    """Load a PDF file and return a list of page objects with text and metadata."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pages = []

    # Strategy 1: Try PyPDF2 / pypdf
    try:
        try:
            import pypdf
            reader = pypdf.PdfReader(str(pdf_path))
        except ImportError:
            import PyPDF2
            reader = PyPDF2.PdfReader(str(pdf_path))

        total_pages = len(reader.pages)
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append({
                "text": text.strip(),
                "metadata": {
                    "source": pdf_path.name,
                    "source_path": str(pdf_path),
                    "page": idx + 1,
                    "total_pages": total_pages,
                }
            })
    except Exception as e:
        print(f"⚠️ PyPDF read warning for {pdf_path.name}: {e}")

    # Strategy 2: If extracted text is empty, try pdfplumber if installed
    total_extracted_chars = sum(len(p["text"]) for p in pages)
    if total_extracted_chars == 0:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                pages = []
                for idx, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    pages.append({
                        "text": text.strip(),
                        "metadata": {
                            "source": pdf_path.name,
                            "source_path": str(pdf_path),
                            "page": idx + 1,
                            "total_pages": len(pdf.pages),
                        }
                    })
                total_extracted_chars = sum(len(p["text"]) for p in pages)
        except Exception:
            pass

    print(f"📄 [PDF INGESTION] Loaded {len(pages)} page(s) from '{pdf_path.name}' ({total_extracted_chars} total characters extracted)")
    return pages


def load_any_document(file_path: Path) -> List[Dict[str, Any]]:
    """Load any supported file (.pdf, .txt, .csv, .md) into page chunks."""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return load_pdf_document(file_path)

    elif suffix in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return [{
            "text": content.strip(),
            "metadata": {
                "source": file_path.name,
                "source_path": str(file_path),
                "page": 1,
                "total_pages": 1,
            }
        }]

    elif suffix == ".csv":
        rows = []
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            headers = next(reader, None)
            header_str = ", ".join(headers) if headers else ""
            for idx, r in enumerate(reader):
                if headers:
                    row_desc = ", ".join(f"{h}: {val}" for h, val in zip(headers, r))
                else:
                    row_desc = ", ".join(r)
                rows.append(f"Record {idx + 1}: {row_desc}")

        text = f"Dataset: {file_path.name}\nFields: {header_str}\n\n" + "\n".join(rows)
        return [{
            "text": text.strip(),
            "metadata": {
                "source": file_path.name,
                "source_path": str(file_path),
                "page": 1,
                "total_pages": 1,
            }
        }]

    else:
        raise ValueError(f"Unsupported document format: {suffix}")


def load_documents_from_dir(dir_path: Path) -> List[Dict[str, Any]]:
    """Load all supported documents from a target directory."""
    dir_path = Path(dir_path)
    if not dir_path.exists():
        return []

    all_pages = []
    for file_path in dir_path.iterdir():
        if file_path.suffix.lower() in (".pdf", ".txt", ".csv", ".md"):
            try:
                all_pages.extend(load_any_document(file_path))
            except Exception:
                pass

    return all_pages
