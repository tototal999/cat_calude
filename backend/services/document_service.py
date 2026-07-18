"""Local, evidence-first document indexing for the document assistant.

The service intentionally has no network client.  It indexes only text formats
whose source locations can be preserved deterministically; Office/PDF support
is deferred until the offline package includes page-aware converters.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from config import settings

DOCUMENTS_DIR = settings.LOG_DIR / 'documents'
_SUPPORTED_SUFFIXES = {'.txt', '.md', '.csv', '.pdf', '.docx', '.pptx', '.xlsx'}
_TOKEN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", re.UNICODE)


def _ensure_dir() -> None:
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


def _tokens(text: str) -> set[str]:
    return {
        item.lower() for item in _TOKEN.findall(text)
        if len(item) > 1 or '\u4e00' <= item <= '\u9fff'
    }


def _chunks(text: str, suffix: str) -> list[dict]:
    """Split text into small, line-addressable evidence blocks."""
    lines = text.splitlines()
    chunks: list[dict] = []
    heading = ''
    buffer: list[str] = []
    start = 1

    def flush(end: int) -> None:
        nonlocal buffer, start
        body = '\n'.join(buffer).strip()
        if body:
            chunks.append({
                'text': body,
                'source': {
                    'kind': 'line_range',
                    'locator': f'第 {start}–{end} 行' + (f' · {heading}' if heading else ''),
                    'heading': heading,
                    'line_start': start,
                    'line_end': end,
                },
            })
        buffer = []

    for line_no, line in enumerate(lines, start=1):
        if suffix == '.md' and line.startswith('#'):
            flush(line_no - 1)
            heading = line.lstrip('#').strip()
            start = line_no + 1
            continue
        if not line.strip() and buffer:
            flush(line_no - 1)
            start = line_no + 1
            continue
        if not buffer:
            start = line_no
        buffer.append(line)
        if len(buffer) >= 12:
            flush(line_no)
            start = line_no + 1
    flush(len(lines))
    return chunks


def _index_path(document_id: str) -> Path:
    return DOCUMENTS_DIR / f'{document_id}.json'


def _source(kind: str, locator: str, **values) -> dict:
    return {'kind': kind, 'locator': locator, **values}


def _extract_pdf(path: Path) -> list[dict]:
    from pypdf import PdfReader
    chunks = []
    for page_no, page in enumerate(PdfReader(path).pages, start=1):
        text = (page.extract_text() or '').strip()
        if text:
            chunks.append({'text': text, 'source': _source('pdf_page', f'第 {page_no} 頁', page=page_no)})
    if not chunks:
        raise ValueError('此掃描型 PDF 需先經 OCR 才能閱讀。')
    return chunks


def _extract_docx(path: Path) -> list[dict]:
    from docx import Document
    chunks = []
    heading = ''
    paragraph_no = 0
    for paragraph in Document(path).paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        paragraph_no += 1
        style_name = (paragraph.style.name or '').lower() if paragraph.style else ''
        if style_name.startswith('heading'):
            heading = text
            continue
        locator = f'第 {paragraph_no} 段' + (f' · {heading}' if heading else '')
        chunks.append({'text': text, 'source': _source(
            'word_paragraph', locator, heading=heading, paragraph=paragraph_no)})
    if not chunks:
        raise ValueError('Word 文件沒有可擷取文字。')
    return chunks


def _extract_pptx(path: Path) -> list[dict]:
    from pptx import Presentation
    chunks = []
    for slide_no, slide in enumerate(Presentation(path).slides, start=1):
        text_parts = [shape.text.strip() for shape in slide.shapes if hasattr(shape, 'text') and shape.text.strip()]
        if not text_parts:
            continue
        title = slide.shapes.title.text.strip() if slide.shapes.title and slide.shapes.title.text else ''
        locator = f'投影片 {slide_no}' + (f' · {title}' if title else '')
        chunks.append({'text': '\n'.join(text_parts), 'source': _source(
            'powerpoint_slide', locator, slide=slide_no, heading=title)})
    if not chunks:
        raise ValueError('PowerPoint 沒有可擷取文字。')
    return chunks


def _extract_xlsx(path: Path) -> list[dict]:
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=True)
    chunks = []
    for worksheet in workbook.worksheets:
        for row_no, row in enumerate(worksheet.iter_rows(values_only=True), start=1):
            values = [str(value).strip() for value in row if value is not None and str(value).strip()]
            if not values:
                continue
            last_column = max(1, len(row))
            cell_range = f'A{row_no}:{_column_name(last_column)}{row_no}'
            locator = f'工作表 {worksheet.title} · {cell_range}'
            chunks.append({'text': ' | '.join(values), 'source': _source(
                'excel_range', locator, sheet=worksheet.title, cell_range=cell_range)})
    workbook.close()
    if not chunks:
        raise ValueError('Excel 沒有可擷取儲存格內容。')
    return chunks


def _column_name(index: int) -> str:
    result = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _extract_chunks(path: Path, suffix: str) -> list[dict]:
    if suffix in {'.txt', '.md', '.csv'}:
        try:
            return _chunks(path.read_text(encoding='utf-8-sig'), suffix)
        except UnicodeDecodeError as exc:
            raise ValueError('此文字檔不是 UTF-8 編碼，無法安全建立本機索引。') from exc
    extractors = {'.pdf': _extract_pdf, '.docx': _extract_docx, '.pptx': _extract_pptx, '.xlsx': _extract_xlsx}
    return extractors[suffix](path)


def _to_markdown(path: Path) -> str | None:
    """Use MarkItDown as the local structural representation when available.

    Citation locations still come from the native extractors above; Markdown is
    retained for future local-model prompts, never sent to a remote endpoint.
    """
    try:
        from markitdown import MarkItDown
        return MarkItDown().convert(str(path)).text_content
    except Exception:
        return None


def ingest(path_value: str) -> dict:
    path = Path(path_value)
    if not path.is_file():
        return {'error': '找不到選取的檔案。'}
    suffix = path.suffix.lower()
    if suffix not in _SUPPORTED_SUFFIXES:
        return {'error': (
            f'{suffix or "此格式"} 尚未啟用可驗證來源定位。'
            '支援 TXT、Markdown、CSV、PDF、DOCX、PPTX 與 XLSX。'
        )}
    try:
        chunks = _extract_chunks(path, suffix)
    except (OSError, ValueError, ImportError) as exc:
        return {'error': str(exc)}
    except Exception as exc:
        return {'error': f'無法解析 {suffix.upper().lstrip(".")}：{exc}'}
    if not chunks:
        return {'error': '文件沒有可建立索引的文字內容。'}

    _ensure_dir()
    document_id = str(uuid.uuid4())
    document = {
        'id': document_id,
        'name': path.name,
        'suffix': suffix,
        'markdown': _to_markdown(path),
        'chunks': chunks,
    }
    _index_path(document_id).write_text(json.dumps(document, ensure_ascii=False), encoding='utf-8')
    return {'document': _summary(document)}


def _load(document_id: str) -> dict | None:
    try:
        return json.loads(_index_path(str(uuid.UUID(document_id))).read_text(encoding='utf-8'))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _summary(document: dict) -> dict:
    return {'id': document['id'], 'name': document['name'], 'chunk_count': len(document['chunks'])}


def list_documents() -> list[dict]:
    _ensure_dir()
    result = []
    for path in DOCUMENTS_DIR.glob('*.json'):
        try:
            result.append(_summary(json.loads(path.read_text(encoding='utf-8'))))
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    return sorted(result, key=lambda item: item['name'].lower())


def remove(document_id: str) -> dict:
    try:
        _index_path(str(uuid.UUID(document_id))).unlink(missing_ok=True)
    except ValueError:
        return {'error': '無效的文件識別碼。'}
    return {'status': 'ok'}


def query(document_id: str, question: str, limit: int = 3) -> dict:
    document = _load(document_id)
    if document is None:
        return {'error': '找不到文件索引。'}
    terms = _tokens(question)
    if not terms:
        return {'answer': '請輸入較具體的問題。', 'sources': []}

    ranked = []
    for chunk in document['chunks']:
        score = len(terms & _tokens(chunk['text']))
        if score:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if not ranked:
        return {'answer': '此文件沒有描述此問題，無法依文件確認。', 'sources': []}

    sources = []
    for _, chunk in ranked[:limit]:
        source = dict(chunk['source'])
        source['document_name'] = document['name']
        sources.append({'excerpt': chunk['text'], 'source': source})
    # This deliberately returns evidence rather than inventing a prose answer.
    return {'answer': '找到下列與問題相關的文件內容：', 'sources': sources}


def context(document_id: str, limit: int = 12) -> dict:
    """Return bounded, source-bearing evidence for document-wide actions."""
    document = _load(document_id)
    if document is None:
        return {'error': '找不到文件索引。'}
    sources = []
    for chunk in document['chunks'][:limit]:
        source = dict(chunk['source'])
        source['document_name'] = document['name']
        sources.append({'excerpt': chunk['text'], 'source': source})
    if not sources:
        return {'error': '文件沒有可用內容。'}
    return {'sources': sources}
