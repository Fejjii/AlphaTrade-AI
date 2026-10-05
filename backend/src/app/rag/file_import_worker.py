"""Isolated, resource-limited text extraction. No files are extracted to disk."""

from __future__ import annotations

import io
import json
import sys
import zipfile

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARACTERS = 100_000
MAX_DOCX_EXPANDED_BYTES = 16 * 1024 * 1024
MAX_PDF_PAGES = 100
PARSER_VERSION = "knowledge-file/v1"


def checked_text(text: str) -> str:
    if len(text) > MAX_TEXT_CHARACTERS:
        raise ValueError("Extracted text exceeds 100,000 characters.")
    if not text.strip():
        raise ValueError("The file contains no readable text.")
    if any(ord(char) < 32 and char not in "\n\r\t" for char in text):
        raise ValueError("The file contains binary or unsupported control characters.")
    return text.strip()


def parse_text(content: bytes) -> tuple[str, list[str]]:
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    try:
        text = content.decode(encoding)
    except UnicodeError as exc:
        raise ValueError("Text files must use UTF-8 or BOM-marked UTF-16.") from exc
    return checked_text(text), []


def parse_docx(content: bytes) -> tuple[str, list[str]]:
    from defusedxml.common import DefusedXmlException
    from defusedxml.ElementTree import fromstring

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(members) > 2000 or len(names) != len(set(names)):
            raise ValueError("DOCX archive has excessive or duplicate entries.")
        if sum(member.file_size for member in members) > MAX_DOCX_EXPANDED_BYTES:
            raise ValueError("DOCX expanded content exceeds 16 MiB.")
        for member in members:
            if member.flag_bits & 1 or member.file_size > max(member.compress_size, 1) * 200:
                raise ValueError("Encrypted or excessively compressed DOCX content is unsupported.")
        if "[Content_Types].xml" not in names or "word/document.xml" not in names:
            raise ValueError("The file is not a valid DOCX document.")
        try:
            content_types = fromstring(archive.read("[Content_Types].xml"))
            root = fromstring(archive.read("word/document.xml"))
        except DefusedXmlException as exc:
            raise ValueError("DOCX is malformed; XML entities are unsupported.") from exc
    if content_types.tag != "{http://schemas.openxmlformats.org/package/2006/content-types}Types":
        raise ValueError("The DOCX content types are malformed.")
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    if root.tag != f"{namespace}document":
        raise ValueError("The DOCX document body is malformed.")
    body = root.find(f"{namespace}body")
    if body is None:
        raise ValueError("The DOCX document body is missing.")
    paragraphs = []
    length = 0
    for paragraph in body.iter(f"{namespace}p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{namespace}t":
                parts.append(node.text or "")
            elif node.tag == f"{namespace}tab":
                parts.append("\t")
            elif node.tag in {f"{namespace}br", f"{namespace}cr"}:
                parts.append("\n")
        text = "".join(parts)
        length += len(text) + 2
        if length > MAX_TEXT_CHARACTERS:
            raise ValueError("Extracted text exceeds 100,000 characters.")
        if text.strip():
            paragraphs.append(text)
    return checked_text("\n\n".join(paragraphs)), [
        "DOCX preview includes body paragraphs and table text. Headers, footers, footnotes, "
        "embedded files and image text are not imported."
    ]


def parse_pdf(content: bytes) -> tuple[str, list[str]]:
    from pypdf import PdfReader

    if not content.startswith(b"%PDF-"):
        raise ValueError("The file is not a valid PDF document.")
    reader = PdfReader(io.BytesIO(content), strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported. Upload an unlocked text PDF.")
    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError("PDF exceeds the 100-page limit.")
    pages = []
    length = 0
    empty_pages = 0
    for ordinal, page in enumerate(reader.pages, start=1):
        stream = page.get_contents()
        if stream is not None and len(stream.get_data()) > 2 * 1024 * 1024:
            raise ValueError("A PDF page exceeds the supported content-stream limit.")
        text = page.extract_text() or ""
        if not text.strip():
            empty_pages += 1
            continue
        extracted = f"[Page {ordinal}]\n{text}"
        length += len(extracted) + 2
        if length > MAX_TEXT_CHARACTERS:
            raise ValueError("Extracted text exceeds 100,000 characters.")
        pages.append(extracted)
    if not pages:
        raise ValueError(
            "PDF has no selectable text. Scanned PDFs need OCR, which this import does not support."
        )
    warnings = ["PDF text order and layout may differ from the original. Review the preview."]
    if empty_pages:
        warnings.append(f"{empty_pages} PDF pages had no selectable text and are not imported.")
    return checked_text("\n\n".join(pages)), warnings


def main() -> None:
    # Linux/macOS resource limits execute in the child, never via preexec_fn in
    # the threaded API. Unsupported platforms fail rather than run unbounded.
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        content = sys.stdin.buffer.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise ValueError("File exceeds the 5 MiB limit.")
        file_type = sys.argv[1]
        parser = {"txt": parse_text, "md": parse_text, "docx": parse_docx, "pdf": parse_pdf}
        text, warnings = parser[file_type](content)
        result = {"text": text, "warnings": warnings}
    except ValueError as exc:
        result = {"error": str(exc)[:240]}
    except MemoryError:
        result = {"error": "File parsing exceeded the memory limit."}
    except Exception:
        result = {"error": "The file is malformed or uses unsupported document features."}
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
