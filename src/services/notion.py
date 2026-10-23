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

            status = ((props.get('Status') or {}).get('status') or {}).get('name', '')
            updated_status = ((props.get('Updated Status') or {}).get('status') or {}).get('name', '')
            url = (props.get('URL') or {}).get('url', '')

            parsed.append({
                'id': p['id'],
                's_no': s_no,
                'company': comp,
                'role': role,
                'applied_date': applied_date,
                'status': status,
                'updated_status': updated_status,
                'url': url
            })

        return parsed

    def create_application(self, app):
        """Creates a new application row in Notion."""
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": {
                "Company": {"title": [{"text": {"content": app['company']}}]},
                "Role": {"rich_text": [{"text": {"content": app['role']}}]},
                "Applied Date": {"date": {"start": app['date']}},
                "Portal": {"select": {"name": app['portal']}},
                "URL": {"url": app['url']},
                "Status": {"status": {"name": "Submitted"}}
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
                        print(f"  [+] Created S.No {s_no}: {app['company']:22s} | {app['role'][:35]:35s} | {app['date']}")
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

    def update_stage_status(self, page_id, s_no, company, stage_name, update_date_str):
        """Updates Updated Status and Updated Date for an existing page."""
        payload = {
            "properties": {
                "Updated Status": {"status": {"name": stage_name}},
                "Updated Date": {"date": {"start": update_date_str}}
            }
        }
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
                        print(f"  [*] Updated S.No {s_no} ({company}) -> {stage_name} ({update_date_str})")
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
