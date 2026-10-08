"""Calendar persistence independent of crawler and notice schemas."""
import calendar
import json
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

FIELDS = {'category', 'location', 'title', 'date', 'time', 'end_time', 'notes', 'priority', 'reminder_minutes', 'timezone_offset', 'source_url', 'completed', 'reminded', 'list_id', 'subtasks', 'repeat', 'repeat_until'}
DEFAULTS = dict(category='other', location='', date='', time='', end_time='', notes='', priority='normal', reminder_minutes=None, timezone_offset=480, source_url='', completed=False, reminded=False, list_id=None, repeat='none', repeat_until='')


def iso_day(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('日程日期无效')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('日程日期无效') from None


def validate_event(value):
    if not isinstance(value, dict) or set(value) - FIELDS:
        raise ValueError('不支持的日程字段')
    event = {**DEFAULTS, 'subtasks': [], **value}
    for key, limit in [('title', 200), ('location', 200), ('notes', 4000), ('source_url', 2000)]:
        if not isinstance(event.get(key), str) or len(event[key]) > limit:
            raise ValueError(f'{key} 长度或格式不正确')
    event['title'] = event['title'].strip()
    if not event['title']:
        raise ValueError('请填写日程标题')
    day = None if event['date'] == '' else iso_day(event['date'])
    for key in ['time', 'end_time']:
        if not isinstance(event[key], str) or (event[key] and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', event[key])):
            raise ValueError('日程时间无效')
    if event['end_time'] and (not event['time'] or event['end_time'] <= event['time']):
        raise ValueError('结束时间须晚于开始时间')
    if event['category'] not in ('study', 'work', 'activity', 'personal', 'other'):
        raise ValueError('日程分类无效')
    if event['priority'] not in ('high', 'normal', 'low'):
        raise ValueError('优先级无效')
    if event['reminder_minutes'] is not None and (type(event['reminder_minutes']) is not int or event['reminder_minutes'] not in [0, 5, 15, 30, 60, 1440]):
        raise ValueError('提醒时间无效')
    if type(event['timezone_offset']) is not int or not -840 <= event['timezone_offset'] <= 840:
        raise ValueError('时区无效')
    if any(type(event[k]) is not bool for k in ['completed', 'reminded']):
        raise ValueError('日程状态必须是布尔值')
    if event['list_id'] is not None and (type(event['list_id']) is not int or event['list_id'] <= 0):
        raise ValueError('清单无效')
    if event['repeat'] not in ('none', 'daily', 'weekly', 'monthly'):
        raise ValueError('重复规则无效')
    if event['repeat_until'] != '':
        until = iso_day(event['repeat_until'])
        if not day or until < day:
            raise ValueError('重复截止日期须不早于任务日期')
    if not day and (event['time'] or event['end_time'] or event['reminder_minutes'] is not None or event['repeat'] != 'none'):
        raise ValueError('请先设置日期，再设置时间、提醒或重复')
    if not isinstance(event['subtasks'], list) or len(event['subtasks']) > 100:
        raise ValueError('子任务最多 100 项')
    subtasks, ids = [], set()
    for item in event['subtasks']:
        if not isinstance(item, dict) or set(item) != {'id', 'title', 'completed'}:
            raise ValueError('子任务字段无效')
        if not isinstance(item['id'], str) or not item['id'].strip() or len(item['id']) > 100 or item['id'] in ids:
            raise ValueError('子任务标识无效或重复')
        if not isinstance(item['title'], str) or not item['title'].strip() or len(item['title']) > 200 or type(item['completed']) is not bool:
            raise ValueError('子任务标题或状态无效')
        ids.add(item['id'])
        subtasks.append({**item, 'title': item['title'].strip()})
    event['subtasks'] = subtasks
    if event['source_url']:
        url = urlparse(event['source_url'])
        if url.scheme not in ('http', 'https') or not url.hostname:
            raise ValueError('原文链接无效')
    event['remind_at'] = None
    if event['reminder_minutes'] is not None:
        start = datetime.fromisoformat(f"{day.isoformat()}T{event['time'] or '09:00'}").replace(tzinfo=timezone(timedelta(minutes=event['timezone_offset'])))
        event['remind_at'] = (start - timedelta(minutes=event['reminder_minutes'])).astimezone(timezone.utc).isoformat(timespec='seconds')
    return event


def validate_list(value):
    if not isinstance(value, dict) or set(value) - {'name', 'color'}:
        raise ValueError('不支持的清单字段')
    name, color = value.get('name'), value.get('color', 'blue')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
        raise ValueError('清单名称须为 1 到 60 个字符')
    if color not in ('blue', 'teal', 'purple', 'orange', 'gray'):
        raise ValueError('清单颜色无效')
    return {'name': name.strip(), 'color': color}


def next_day(event):
    day = iso_day(event['date'])
    try:
        if event['repeat'] == 'monthly':
            year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
            result = date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
        else:
            result = day + timedelta(days=1 if event['repeat'] == 'daily' else 7)
    except (OverflowError, ValueError):
        return None
    return result.isoformat() if not event['repeat_until'] or result <= iso_day(event['repeat_until']) else None


class CalendarMixin:
    def initialize_calendar(self):
        with self._lock, self.db:
            self.db.execute('CREATE TABLE IF NOT EXISTS calendar_events(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS calendar_lists(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, color TEXT NOT NULL)')

    def _calendar_row(self, row):
        payload = json.loads(row['payload'])
        payload.pop('_next_event_id', None)
        return {**DEFAULTS, 'subtasks': [], **payload, 'id': row['id'], 'created_at': row['created_at'], 'updated_at': row['updated_at']}

    def list_events(self):
        with self._lock:
            rows = self.db.execute('SELECT * FROM calendar_events').fetchall()
        return sorted((self._calendar_row(r) for r in rows), key=lambda e: (e['date'], e['time'], e['id']))

    def _validate_list_reference(self, event):
        if event['list_id'] is not None and not self.db.execute('SELECT id FROM calendar_lists WHERE id=?', (event['list_id'],)).fetchone():
            raise ValueError('清单不存在')

    def _insert_event(self, event, now):
        cursor = self.db.execute('INSERT INTO calendar_events(payload,created_at,updated_at) VALUES(?,?,?)', (json.dumps(event, ensure_ascii=False), now, now))
        return {**event, 'id': cursor.lastrowid, 'created_at': now, 'updated_at': now}

    def create_event(self, value):
        event = validate_event(value)
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        with self._lock, self.db:
            self._validate_list_reference(event)
            return self._insert_event(event, now)

    def update_event(self, event_id, patch):
        if not isinstance(patch, dict) or not patch or set(patch) - FIELDS:
            raise ValueError('不支持的日程字段')
        with self._lock, self.db:
            row = self.db.execute('SELECT * FROM calendar_events WHERE id=?', (event_id,)).fetchone()
            if not row:
                return None
            stored = json.loads(row['payload'])
            previous = {**DEFAULTS, 'subtasks': [], **{k: v for k, v in stored.items() if k in FIELDS}}
            event = validate_event({**previous, **patch})
            self._validate_list_reference(event)
            if any(k in patch and patch[k] != previous[k] for k in ['date', 'time', 'reminder_minutes', 'timezone_offset']):
                event['reminded'] = False
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            successor = None
            # Retain the marker even after deletion or undo, preventing duplicate occurrences.
            if '_next_event_id' in stored:
                event['_next_event_id'] = stored['_next_event_id']
                if event['completed']:
                    child = self.db.execute('SELECT * FROM calendar_events WHERE id=?', (stored['_next_event_id'],)).fetchone()
                    if child:
                        successor = self._calendar_row(child)
            elif not previous['completed'] and event['completed'] and event['repeat'] != 'none':
                following = next_day(event)
                if following:
                    child = validate_event({**{k: v for k, v in event.items() if k in FIELDS}, 'date': following, 'completed': False, 'reminded': False, 'subtasks': [{**s, 'completed': False} for s in event['subtasks']]})
                    successor = self._insert_event(child, now)
                    event['_next_event_id'] = successor['id']
            self.db.execute('UPDATE calendar_events SET payload=?,updated_at=? WHERE id=?', (json.dumps(event, ensure_ascii=False), now, event_id))
            event.pop('_next_event_id', None)
            result = {**event, 'id': event_id, 'created_at': row['created_at'], 'updated_at': now}
            if successor:
                result['next_event'] = successor
            return result

    def delete_event(self, event_id):
        with self._lock, self.db:
            return self.db.execute('DELETE FROM calendar_events WHERE id=?', (event_id,)).rowcount > 0

    def list_calendar_lists(self):
        with self._lock:
            return [dict(row) for row in self.db.execute('SELECT * FROM calendar_lists ORDER BY id')]

    def create_calendar_list(self, value):
        item = validate_list(value)
        with self._lock, self.db:
            cursor = self.db.execute('INSERT INTO calendar_lists(name,color) VALUES(?,?)', (item['name'], item['color']))
            return {**item, 'id': cursor.lastrowid}

    def update_calendar_list(self, list_id, patch):
        if not isinstance(patch, dict) or not patch or set(patch) - {'name', 'color'}:
            raise ValueError('不支持的清单字段')
        with self._lock, self.db:
            row = self.db.execute('SELECT * FROM calendar_lists WHERE id=?', (list_id,)).fetchone()
            if not row:
                return None
            item = validate_list({'name': row['name'], 'color': row['color'], **patch})
            self.db.execute('UPDATE calendar_lists SET name=?,color=? WHERE id=?', (item['name'], item['color'], list_id))
            return {**item, 'id': list_id}

    def delete_calendar_list(self, list_id):
        with self._lock, self.db:
            if not self.db.execute('DELETE FROM calendar_lists WHERE id=?', (list_id,)).rowcount:
                return False
            now = datetime.now(timezone.utc).isoformat(timespec='seconds')
            for row in self.db.execute('SELECT id,payload FROM calendar_events').fetchall():
                payload = json.loads(row['payload'])
                if payload.get('list_id') == list_id:
                    payload['list_id'] = None
                    self.db.execute('UPDATE calendar_events SET payload=?,updated_at=? WHERE id=?', (json.dumps(payload, ensure_ascii=False), now, row['id']))
            return True
