"""
Deterministic schedule engine for ClaudeCat (Part 1).
======================================================

Pure logic, no LLM, no UI: loads/validates schedule.json, decides what is
due on each 30s tick, records fired marks to prevent duplicates, writes
back. The popup/alert presentation lives in cat.py; the webview form
talks to this module through chat/window.py's js_api.

schedule.json item format (spec 1.2):
    { "id": "s1", "title": "開會", "type": "daily",
      "time": "09:00", "lead_min": 10, "enabled": true }
    type: daily | weekly | hourly
    weekly adds "day": MO..SU; hourly uses "minute": 0-59 instead of time.

Dedup: each item carries last_fired_lead / last_fired_ontime keyed by the
occurrence minute ("YYYY-MM-DDTHH:MM"), so the 30s tick hitting the same
minute twice fires only once. Missed occurrences are never back-filled
(錯過不補): only the current minute is ever matched.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

DAYS = ('MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU')
TYPES = ('daily', 'weekly', 'hourly')
_TIME_RE = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')


def validate(item: dict) -> str | None:
    """Return a human-readable error for one schedule item, or None if OK."""
    if not isinstance(item, dict):
        return '不是物件'
    if not str(item.get('title', '')).strip():
        return '缺 title'
    t = item.get('type')
    if t not in TYPES:
        return f'type 必須是 {"/".join(TYPES)},收到 {t!r}'
    if t in ('daily', 'weekly'):
        if not _TIME_RE.match(str(item.get('time', ''))):
            return f'time 必須是 HH:MM,收到 {item.get("time")!r}'
    if t == 'weekly' and item.get('day') not in DAYS:
        return f'day 必須是 {"/".join(DAYS)},收到 {item.get("day")!r}'
    if t == 'hourly':
        m = item.get('minute')
        if not isinstance(m, int) or not 0 <= m <= 59:
            return f'minute 必須是 0-59 整數,收到 {m!r}'
    lead = item.get('lead_min', 0)
    if not isinstance(lead, int) or lead < 0:
        return f'lead_min 必須是 >=0 整數,收到 {lead!r}'
    if not isinstance(item.get('enabled', True), bool):
        return 'enabled 必須是 true/false'
    return None


def _minute_key(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%dT%H:%M')


def _candidate_occurrences(item: dict, now: datetime) -> list[datetime]:
    """Occurrences near `now` (previous/current/next cycle). Checking all
    three lets lead warnings that cross a midnight/week/hour boundary
    still line up with the occurrence they announce."""
    if item['type'] == 'daily':
        hh, mm = map(int, item['time'].split(':'))
        base = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        step = timedelta(days=1)
    elif item['type'] == 'weekly':
        hh, mm = map(int, item['time'].split(':'))
        delta = (DAYS.index(item['day']) - now.weekday()) % 7
        base = (now + timedelta(days=delta)).replace(
            hour=hh, minute=mm, second=0, microsecond=0)
        step = timedelta(days=7)
    else:  # hourly
        base = now.replace(minute=item['minute'], second=0, microsecond=0)
        step = timedelta(hours=1)
    return [base - step, base, base + step]


class Scheduler:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._mtime: float | None = None
        self.items: list[dict] = []
        self.errors: list[str] = []
        self.reload(force=True)

    # ---- persistence ------------------------------------------------------

    def reload(self, force: bool = False) -> bool:
        """Re-read schedule.json if it changed on disk (webview edits it
        through this module too, but external edits also get picked up).
        Bad entries are reported in self.errors; good ones still load."""
        with self._lock:
            try:
                mtime = self.path.stat().st_mtime
            except OSError:
                mtime = None
            if not force and mtime == self._mtime:
                return False
            self._mtime = mtime
            raw: list = []
            self.errors = []
            if mtime is not None:
                try:
                    raw = json.loads(self.path.read_text(encoding='utf-8'))
                    if not isinstance(raw, list):
                        self.errors.append('schedule.json 最外層必須是清單')
                        raw = []
                except ValueError as exc:
                    self.errors.append(f'schedule.json 解析失敗: {exc}')
                    raw = []
            items = []
            for i, it in enumerate(raw):
                err = validate(it)
                if err:
                    title = it.get('title', '?') if isinstance(it, dict) else '?'
                    self.errors.append(f'第 {i + 1} 筆「{title}」: {err}')
                else:
                    items.append(it)
            self.items = items
            return True

    def save(self) -> None:
        with self._lock:
            self.path.write_text(
                json.dumps(self.items, ensure_ascii=False, indent=1),
                encoding='utf-8')
            try:
                self._mtime = self.path.stat().st_mtime
            except OSError:
                self._mtime = None

    # ---- CRUD for the webview form (即改即存) ------------------------------

    def list(self) -> list[dict]:
        with self._lock:
            self.reload()
            return [dict(it) for it in self.items]

    def upsert(self, item: dict) -> str | None:
        """Insert or replace by id. Returns an error string, or None on OK."""
        err = validate(item)
        if err:
            return err
        with self._lock:
            self.reload()
            if not item.get('id'):
                item['id'] = uuid.uuid4().hex[:8]
            for i, it in enumerate(self.items):
                if it.get('id') == item['id']:
                    # Editing resets fired marks so the new time can fire today
                    item.pop('last_fired_lead', None)
                    item.pop('last_fired_ontime', None)
                    self.items[i] = item
                    break
            else:
                self.items.append(item)
            self.save()
            return None

    def delete(self, sid: str) -> None:
        with self._lock:
            self.reload()
            self.items = [it for it in self.items if it.get('id') != sid]
            self.save()

    # ---- tick --------------------------------------------------------------

    def tick(self, now: datetime) -> list[tuple[dict, str]]:
        """Return [(item, 'lead'|'ontime'), ...] due at this instant."""
        fired: list[tuple[dict, str]] = []
        with self._lock:
            self.reload()
            changed = False
            now_key = _minute_key(now)
            for it in self.items:
                if not it.get('enabled', True):
                    continue
                lead = int(it.get('lead_min', 0))
                for occ in _candidate_occurrences(it, now):
                    occ_key = _minute_key(occ)
                    if now_key == occ_key and it.get('last_fired_ontime') != occ_key:
                        it['last_fired_ontime'] = occ_key
                        fired.append((it, 'ontime'))
                        changed = True
                    if lead > 0 and now_key == _minute_key(occ - timedelta(minutes=lead)) \
                            and it.get('last_fired_lead') != occ_key:
                        it['last_fired_lead'] = occ_key
                        fired.append((it, 'lead'))
                        changed = True
            if changed:
                self.save()
        return fired


def card_text(item: dict, kind: str) -> str:
    """Popup wording per spec: lead=「N 分鐘後:標題」, ontime=「現在:標題」."""
    if kind == 'lead':
        return f'{item.get("lead_min", 0)} 分鐘後:{item["title"]}'
    return f'現在:{item["title"]}'
