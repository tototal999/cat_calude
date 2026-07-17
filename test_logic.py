import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import api
from backend.routes.api import _session_path
from backend.services import llm_service as llm
import scheduler


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


if __name__ == '__main__':
    unittest.main()
