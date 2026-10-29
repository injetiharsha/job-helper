import json
import time
import urllib.request
import urllib.error
import re
from datetime import datetime, date
from src.core.config import NOTION_TOKEN, NOTION_DATABASE_ID, NO_RESPONSE_DAYS
from src.core.stages import HiringStage

class NotionClient:
    def __init__(self):
        if not NOTION_TOKEN or not NOTION_DATABASE_ID:
            raise ValueError("Notion credentials missing in .env")
        self.headers = {
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }
        self.database_id = NOTION_DATABASE_ID
        self._property_types = {}
        self._fetch_db_schema()

    def _fetch_db_schema(self):
        """Discovers database schema dynamically to adapt to status vs select types."""
        try:
            req = urllib.request.Request(
                f"https://api.notion.com/v1/databases/{self.database_id}",
                headers=self.headers
            )
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for name, p in data.get('properties', {}).items():
                    self._property_types[name] = p.get('type')
        except Exception as e:
            print(f"[Notion] Warning: Could not pre-fetch schema: {e}")

    def get_all_applications(self):
        """Fetches all applications currently stored in the Notion database."""
        pages = []
        has_more = True
        next_cursor = None

        while has_more:
            payload = {"page_size": 100}
            if next_cursor:
                payload["start_cursor"] = next_cursor

            req = urllib.request.Request(
                f"https://api.notion.com/v1/databases/{self.database_id}/query",
                data=json.dumps(payload).encode('utf-8'),
                headers=self.headers,
                method='POST'
            )

            try:
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    pages.extend(data.get('results', []))
                    has_more = data.get('has_more', False)
                    next_cursor = data.get('next_cursor')
            except Exception as e:
                print(f"[Notion] Query error: {e}")
                break
            time.sleep(0.3)

        parsed = []
        for p in pages:
            props = p.get('properties', {})
            title_list = (props.get('Company') or {}).get('title', [])
            comp = title_list[0].get('text', {}).get('content', '').strip() if title_list else ''

            role_list = (props.get('Role') or {}).get('rich_text', [])
            role = role_list[0].get('text', {}).get('content', '').strip() if role_list else ''

            s_no = (props.get('S. No.') or {}).get('unique_id', {}).get('number')
            applied_date = ((props.get('Applied Date') or {}).get('date') or {}).get('start', '')
            updated_date = ((props.get('Updated Date') or {}).get('date') or {}).get('start', '')

            status_prop = props.get('Status') or {}
            status = (status_prop.get('status') or status_prop.get('select') or {}).get('name', '')

            up_status_prop = props.get('Updated Status') or {}
            updated_status = (up_status_prop.get('status') or up_status_prop.get('select') or {}).get('name', '')

            url = (props.get('URL') or {}).get('url', '')
            deadline = ((props.get('Deadline / Event Date') or {}).get('date') or {}).get('start', '')
            
            json_list = (props.get('JSON') or {}).get('rich_text', [])
            json_raw = json_list[0].get('text', {}).get('content', '') if json_list else ''
            json_meta = {}
            if json_raw:
                try:
                    json_meta = json.loads(json_raw)
                except Exception:
                    pass

            parsed.append({
                'id': p['id'],
                's_no': s_no,
                'company': comp,
                'role': role,
                'applied_date': applied_date,
                'updated_date': updated_date,
                'deadline': deadline,
                'status': status,
                'updated_status': updated_status,
                'url': url,
                'metadata': json_meta
            })

        return parsed

    def create_application(self, app):
        """Creates a new application row in Notion."""
        status_type = self._property_types.get("Status", "select")
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": {
                "Company": {"title": [{"text": {"content": app['company']}}]},
                "Role": {"rich_text": [{"text": {"content": app['role']}}]},
                "Applied Date": {"date": {"start": app['date']}},
                "Portal": {"select": {"name": app['portal']}},
                "URL": {"url": app['url']},
                "Status": {status_type: {"name": "Submitted"}}
            }
        }

        req = urllib.request.Request(
            "https://api.notion.com/v1/pages",
            data=json.dumps(payload).encode('utf-8'),
            headers=self.headers,
            method='POST'
        )

        for _ in range(3):
            try:
                with urllib.request.urlopen(req) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode('utf-8'))
                        s_no = (data.get('properties', {}).get('S. No.', {}).get('unique_id') or {}).get('number')
                        s_no_lbl = f"S.No {s_no}" if s_no else "[New Entry]"
                        print(f"  [+] Created {s_no_lbl}: {app['company']:22s} | {app['role'][:35]:35s} | {app['date']}")
                        return True
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(2)
                else:
                    time.sleep(1)
            except Exception:
                time.sleep(1)
            time.sleep(0.35)
        return False

    def update_stage_status(self, page_id, s_no, company, stage_name, update_date_str, deadline_str=None, metadata=None):
        """Updates Updated Status, Updated Date, optional Deadline, and metadata JSON for an existing page."""
        up_status_type = self._property_types.get("Updated Status", "select")
        payload = {
            "properties": {
                "Updated Status": {up_status_type: {"name": stage_name}},
                "Updated Date": {"date": {"start": update_date_str}}
            }
        }
        if deadline_str:
            payload["properties"]["Deadline / Event Date"] = {"date": {"start": deadline_str}}
        if metadata:
            payload["properties"]["JSON"] = {"rich_text": [{"text": {"content": json.dumps(metadata)}}]}

        req = urllib.request.Request(
            f"https://api.notion.com/v1/pages/{page_id}",
            data=json.dumps(payload).encode('utf-8'),
            headers=self.headers,
            method='PATCH'
        )
        for _ in range(3):
            try:
                with urllib.request.urlopen(req) as resp:
                    if resp.status == 200:
                        dl_info = f" | Deadline: {deadline_str}" if deadline_str else ""
                        s_no_lbl = f"S.No {s_no} " if s_no else ""
                        print(f"  [*] Updated {s_no_lbl}({company}) -> {stage_name} ({update_date_str}){dl_info}")
                        return True
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(2)
                else:
                    time.sleep(1)
            except Exception:
                time.sleep(1)
            time.sleep(0.35)
        return False

    def auto_mark_stale_applications(self, current_pages, current_date=None):
        """
        Criteria:
        If applied date is >= NO_RESPONSE_DAYS (e.g. 30 days) from current date,
        and application has not received an active status (Interview, Hired, Rejected, No Response),
        mark it as 'No Response' so it automatically groups into completed/rejected.
        """
        if not current_date:
            current_date = date.today()

        stale_count = 0
        for p in current_pages:
            app_date_str = p.get('applied_date')
            if not app_date_str:
                continue

            try:
                app_date = datetime.strptime(app_date_str, '%Y-%m-%d').date()
            except Exception:
                continue

            days_old = (current_date - app_date).days
            up_status = p.get('updated_status', '').lower()

            # Active terminal or ongoing statuses that should not be marked No Response
            exempt_statuses = ['rejected', 'interview', 'hired', 'no response', 'offer', 'final round', 'technical round']
            if days_old >= NO_RESPONSE_DAYS and up_status not in exempt_statuses:
                date_str = current_date.strftime('%Y-%m-%d')
                if self.update_stage_status(p['id'], p.get('s_no'), p.get('company'), 'No Response', date_str):
                    stale_count += 1
                time.sleep(0.35)

        return stale_count
