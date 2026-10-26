from dataclasses import dataclass
import hashlib
import re
import unicodedata
from pathlib import PurePosixPath
from app.core.errors import require


def normalize_question(value: str):
    value = unicodedata.normalize("NFKC", value).lower().strip()
    return re.sub(r"[\s\W_]+", "", value)


def question_key(value: str):
    return hashlib.sha256(normalize_question(value).encode()).hexdigest()


def safe_upload_path(path: str, file_name: str):
    value = (path or file_name).replace("\\", "/")
    p = PurePosixPath(value)
    require(not p.is_absolute() and ":" not in value and ".." not in p.parts and "\x00" not in value,
            "上传路径不合法")
    require(0 < len(value) <= 600, "上传路径过长")
    return str(p)


@dataclass
class TextChunk:
    content: str
    heading: str
    start_offset: int
    end_offset: int
    page: int | None = None


def split_text(content: str, size: int = 800, overlap: int = 100):
    require(size >= 32 and 0 <= overlap < size, "切片配置不合法")
    chunks = []
    headings = list(re.finditer(r"(?m)^#{1,6}\s+(.+)$", content))
    start = 0
    while start < len(content):
        end = min(start + size, len(content))
        if end < len(content):
            # Prefer a paragraph boundary in the latter half; otherwise preserve hard size bound.
            boundary = content.rfind("\n\n", start + size // 2, end)
            if boundary > start:
                end = boundary + 2
        piece = content[start:end]
        if piece.strip():
            # A chunk holding only an image link carries no retrievable text; the image still renders
            # from knowledge_units.content.
            if re.sub(r'!\[[^\]]*\]\([^)]*\)', '', piece).strip():
                heading = next((h.group(1) for h in reversed(headings) if h.start() <= start), "")
                chunks.append(TextChunk(piece, heading[:600], start, end))
        if end == len(content):
            break
        start = max(start + 1, end - overlap)
    return chunks
