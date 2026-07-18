import json
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import api
from backend.routes.api import JsApi, _session_path
from backend.services import document_service as documents
from backend.services import local_llm
from backend.services import llm_service as llm
import scheduler
import worker


class SchedulerTests(unittest.TestCase):
    def test_invalid_json_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'schedule.json'
            path.write_text('{bad json', encoding='utf-8')
            result = scheduler.Scheduler(path)
            self.assertTrue(result.errors)
            self.assertEqual(result.items, [])

    def test_daily_lead_and_ontime_fire_once(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'schedule.json'
            now = datetime(2026, 7, 17, 9, 0)
            path.write_text(json.dumps([{
                'id': 'daily-test', 'title': 'Daily Test', 'type': 'daily',
                'time': '09:02', 'lead_min': 1, 'enabled': True,
            }]), encoding='utf-8')
            result = scheduler.Scheduler(path)

            self.assertEqual([(item['id'], kind) for item, kind in result.tick(now + timedelta(minutes=1))],
                             [('daily-test', 'lead')])
            self.assertEqual(result.tick(now + timedelta(minutes=1)), [])
            self.assertEqual([(item['id'], kind) for item, kind in result.tick(now + timedelta(minutes=2))],
                             [('daily-test', 'ontime')])


class ApiTests(unittest.TestCase):
    def test_read_access_token_uses_configured_credentials_path(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = Path(directory) / '.credentials.json'
            credentials.write_text(json.dumps({
                'claudeAiOauth': {'accessToken': 'test-token'},
            }), encoding='utf-8')
            with patch.object(api, 'CLAUDE_CREDENTIALS', credentials):
                self.assertEqual(api.read_access_token(), 'test-token')

    def test_session_path_rejects_traversal(self):
        self.assertIsNone(_session_path('../config'))
        self.assertIsNotNone(_session_path('550e8400-e29b-41d4-a716-446655440000'))

    def test_claude_usage_api_is_hard_disabled_before_http_request(self):
        api.set_usage_api_enabled(False)
        try:
            self.assertFalse(api.USAGE_API_ENABLED)
            with patch.object(api.requests, 'get') as request:
                result = api.fetch_usage()
            self.assertEqual(result['error'], 'Claude usage monitor disabled')
            request.assert_not_called()
        finally:
            api.set_usage_api_enabled(False)

    def test_claude_usage_api_toggle_changes_only_the_optional_monitor(self):
        api.set_usage_api_enabled(True)
        try:
            self.assertTrue(api.USAGE_API_ENABLED)
        finally:
            api.set_usage_api_enabled(False)


class LlmTests(unittest.TestCase):
    def test_model_list_deduplicates_primary_and_fallbacks(self):
        with patch.object(llm, '_config', {
            'model': 'primary',
            'fallback_models': ['fallback', 'primary', 'fallback'],
        }):
            self.assertEqual(llm.list_models(), ['primary', 'fallback'])

    def test_context_overflow_detection(self):
        self.assertTrue(llm._looks_like_context_overflow('Maximum context length exceeded'))
        self.assertFalse(llm._looks_like_context_overflow('Authentication failed'))

    def test_file_size_limit_has_a_safe_default(self):
        with patch.object(llm, '_config', {}):
            self.assertEqual(llm.max_file_bytes(), 10 * 1024 * 1024)

    def test_local_endpoint_rejects_non_loopback_address(self):
        with self.assertRaises(ValueError):
            llm.use_local_endpoint('http://192.168.1.10:8080/v1')

    def test_local_endpoint_detection_requires_loopback(self):
        with patch.object(llm, '_config', {'base_url': 'http://example.test/v1'}):
            self.assertFalse(llm.is_local_endpoint())
        with patch.object(llm, '_config', {'base_url': 'http://127.0.0.1:8080/v1'}):
            self.assertTrue(llm.is_local_endpoint())



class LocalLlmRuntimeTests(unittest.TestCase):
    def test_disabled_runtime_does_not_start_a_process(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps({'local_llm': {'enabled': False}}), encoding='utf-8')
            self.assertEqual(local_llm.init(config)['status'], '本機模型未啟用。')


class DocumentServiceTests(unittest.TestCase):
    def test_markdown_query_returns_deterministic_line_citation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / '採購.md'
            source.write_text('# 付款條款\n付款期限為收貨後 30 日。\n', encoding='utf-8')
            with patch.object(documents, 'DOCUMENTS_DIR', root / 'documents'):
                result = documents.ingest(str(source))
                self.assertNotIn('error', result)
                answer = documents.query(result['document']['id'], '付款期限')
                self.assertEqual(answer['answer'], '找到下列與問題相關的文件內容：')
                self.assertEqual(answer['sources'][0]['source']['document_name'], '採購.md')
                self.assertEqual(answer['sources'][0]['source']['line_start'], 2)
                self.assertEqual(answer['sources'][0]['source']['heading'], '付款條款')

    def test_missing_evidence_does_not_invent_an_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / '流程.txt'
            source.write_text('申請人填寫表單。\n', encoding='utf-8')
            with patch.object(documents, 'DOCUMENTS_DIR', root / 'documents'):
                result = documents.ingest(str(source))
                answer = documents.query(result['document']['id'], '付款期限')
                self.assertEqual(answer['answer'], '此文件沒有描述此問題，無法依文件確認。')
                self.assertEqual(answer['sources'], [])

    def test_pdf_is_rejected_until_page_aware_converter_is_packaged(self):
        from pypdf import PdfWriter
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'scan.pdf'
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            with source.open('wb') as output:
                writer.write(output)
            result = documents.ingest(str(source))
            self.assertEqual(result['error'], '此掃描型 PDF 需先經 OCR 才能閱讀。')

    def test_xlsx_query_returns_sheet_and_cell_range(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / '付款.xlsx'
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = '付款條款'
            sheet.append(['條件', '內容'])
            sheet.append(['付款期限', '收貨後 30 日'])
            workbook.save(source)
            with patch.object(documents, 'DOCUMENTS_DIR', root / 'documents'):
                result = documents.ingest(str(source))
                answer = documents.query(result['document']['id'], '付款期限')
                self.assertEqual(answer['sources'][0]['source']['sheet'], '付款條款')
                self.assertEqual(answer['sources'][0]['source']['cell_range'], 'A2:B2')

    def test_office_and_pdf_extractors_preserve_native_locations(self):
        from docx import Document
        from pptx import Presentation
        from reportlab.pdfgen.canvas import Canvas
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            word_path = root / 'policy.docx'
            word = Document()
            word.add_heading('Payment terms', level=1)
            word.add_paragraph('Payment is due in 30 days.')
            word.save(word_path)

            ppt_path = root / 'policy.pptx'
            deck = Presentation()
            slide = deck.slides.add_slide(deck.slide_layouts[1])
            slide.shapes.title.text = 'Approval'
            slide.placeholders[1].text = 'Manager approval is required.'
            deck.save(ppt_path)

            pdf_path = root / 'policy.pdf'
            pdf = Canvas(str(pdf_path))
            pdf.drawString(72, 720, 'Payment is due in 30 days.')
            pdf.save()

            with patch.object(documents, 'DOCUMENTS_DIR', root / 'documents'):
                word_result = documents.ingest(str(word_path))
                ppt_result = documents.ingest(str(ppt_path))
                pdf_result = documents.ingest(str(pdf_path))
                self.assertEqual(documents.context(word_result['document']['id'])['sources'][0]['source']['kind'], 'word_paragraph')
                self.assertEqual(documents.context(ppt_result['document']['id'])['sources'][0]['source']['locator'], '投影片 1 · Approval')
                self.assertEqual(documents.context(pdf_result['document']['id'])['sources'][0]['source']['locator'], '第 1 頁')

    def test_document_question_sends_only_retrieved_evidence_to_llm(self):
        evidence = {
            'answer': '找到下列與問題相關的文件內容：',
            'sources': [{'excerpt': '付款期限為收貨後 30 日。', 'source': {
                'document_name': '採購.md', 'locator': '第 2 行 · 付款條款'}}],
        }
        with patch.object(documents, 'query', return_value=evidence), \
             patch.object(llm, 'chat', return_value={'content': '付款期限為收貨後 30 日。'} ) as chat:
            result = JsApi().query_document('550e8400-e29b-41d4-a716-446655440000', '付款期限？')
        self.assertEqual(result['answer'], '付款期限為收貨後 30 日。')
        prompt = chat.call_args.args[0][1]['content']
        self.assertIn('付款期限為收貨後 30 日。', prompt)
        self.assertIn('採購.md · 第 2 行 · 付款條款', prompt)

    def test_document_summary_action_carries_source_metadata(self):
        evidence = {'sources': [{'excerpt': '採購前需取得主管核准。', 'source': {
            'document_name': '流程.md', 'locator': '第 4 行'}}]}
        with patch.object(documents, 'context', return_value=evidence), \
             patch.object(llm, 'chat', return_value={'content': '需先取得主管核准。'}) as chat:
            result = JsApi().document_action('550e8400-e29b-41d4-a716-446655440000', 'summary')
        self.assertEqual(result['answer'], '需先取得主管核准。')
        self.assertEqual(result['sources'], evidence['sources'])
        self.assertIn('流程.md · 第 4 行', chat.call_args.args[0][1]['content'])

    def test_document_comparison_carries_both_documents_sources(self):
        first = {'sources': [{'excerpt': '付款 30 日。', 'source': {'document_name': 'A.md', 'locator': '第 1 行'}}]}
        second = {'sources': [{'excerpt': '付款 45 日。', 'source': {'document_name': 'B.md', 'locator': '第 1 行'}}]}
        with patch.object(documents, 'context', side_effect=[first, second]), \
             patch.object(llm, 'chat', return_value={'content': '兩份文件付款期限不同。'}) as chat:
            result = JsApi().compare_documents('550e8400-e29b-41d4-a716-446655440000', '11111111-1111-4111-8111-111111111111')
        self.assertEqual(len(result['sources']), 2)
        prompt = chat.call_args.args[0][1]['content']
        self.assertIn('A.md · 第 1 行', prompt)
        self.assertIn('B.md · 第 1 行', prompt)


class WorkerTests(unittest.TestCase):
    def test_xlsx_worker_uses_openpyxl_without_pandas(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'sample.xlsx'
            workbook = Workbook()
            workbook.active.append(['name', 'value'])
            workbook.active.append(['payment', 30])
            workbook.save(source)
            output = io.StringIO()
            with redirect_stdout(output):
                worker.main(str(source))
            self.assertIn('payment,30', output.getvalue())


if __name__ == '__main__':
    unittest.main()
