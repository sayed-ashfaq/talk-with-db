"""Turning an uploaded PDF into embedded, storable chunks.

Called from app.services.documents inside asyncio.to_thread — pypdf parsing and fastembed inference
are both CPU-bound, and this module never touches the network or a database itself, so the service
layer owns getting it off the event loop rather than this module reaching for asyncio itself.

The raw PDF is never kept: only what comes out of it (see app.db.models.document.Document).
"""

import io
from functools import lru_cache

from fastembed import TextEmbedding
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.core.exceptions import EmptyDocumentError

# characters, not tokens — fastembed's tokenizer runs well under the model's context window at
# this size, and a character bound is cheap to reason about without importing a tokenizer just to
# pick chunk boundaries
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


@lru_cache(maxsize=1)
def _embedding_model() -> TextEmbedding:
    # one instance per process: construction loads model weights from disk, too slow to repeat per
    # upload or per query
    return TextEmbedding()


def embed_text(text: str) -> list[float]:
    """One string's embedding — used for a retrieval query, where there's exactly one to embed."""
    return next(iter(_embedding_model().embed([text]))).tolist()


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]


def ingest_pdf(pdf_bytes: bytes) -> list[tuple[str, list[float]]]:
    """PDF bytes -> (chunk text, embedding) pairs, ready to store as DocumentChunk rows.

    Raises EmptyDocumentError for a PDF with no extractable text (a scan with no OCR layer, for
    instance) — better to reject at upload than to silently create a document nothing can ever
    retrieve from.
    """
    text = _extract_text(pdf_bytes)
    chunks = _chunk_text(text)
    if not chunks:
        raise EmptyDocumentError

    vectors = [vector.tolist() for vector in _embedding_model().embed(chunks)]
    return list(zip(chunks, vectors))
