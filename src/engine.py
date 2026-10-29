import json
import re
import sys
from datetime import datetime, date, timedelta
from src.core.config import STATE_FILE, NO_RESPONSE_DAYS
from src.core.stages import HiringStage
from src.services.gmail import GmailClient
from src.services.notion import NotionClient
from src.services.sarvam import SarvamClient

# Safe encoding on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

class JobHelperEngine:
    def __init__(self):
        self.notion = NotionClient()
        self.sarvam = SarvamClient()

    def _load_state(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        default_start = (date.today() - timedelta(days=3)).strftime('%d-%b-%Y')
        return {"last_synced_date": default_start}

    def _save_state(self, state):
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

    def run(self, force_since_date=None):
        print("==================================================")
        print("🚀 Job Helper: Recruitment Lifecycle Sync Engine")
        print("==================================================")

        state = self._load_state()
        since_date = force_since_date or state.get("last_synced_date")
        print(f"[*] Scanning Gmail for recruitment events since: {since_date}")

        # 1. Fetch current Notion applications
        print("[*] Loading current Notion database state...")
        existing_pages = self.notion.get_all_applications()
        print(f"[*] Loaded {len(existing_pages)} total entries from Notion.")

        # Build index of existing applications by (company, role) to preserve multi-role applications
        existing_index = set()
        active_companies = []
        for p in existing_pages:
            c = p.get('company', '').strip()
            if c:
                active_companies.append(c)
            c_norm = re.sub(r'[^a-zA-Z0-9]', '', c.lower())
            r_norm = re.sub(r'[^a-zA-Z0-9]', '', p.get('role', '').lower())[:15]
            if c_norm:
                existing_index.add((c_norm, r_norm))

        # 2. Fetch recruitment events from Gmail
        gmail = GmailClient()
        try:
            new_applications, status_updates = gmail.fetch_recruitment_events(since_date, active_companies=active_companies)
        finally:
            gmail.close()

        print(f"[*] Ingested: {len(new_applications)} new submissions, {len(status_updates)} lifecycle progression updates.")

        # 3. Create net-new applications in Notion
        created_count = 0
        to_create = []
        for app in new_applications:
            c_norm = re.sub(r'[^a-zA-Z0-9]', '', (app.get('company') or '').lower())
            r_norm = re.sub(r'[^a-zA-Z0-9]', '', (app.get('role') or '').lower())[:15]
            if (c_norm, r_norm) not in existing_index and c_norm:
                existing_index.add((c_norm, r_norm))
                to_create.append(app)

        if to_create:
            print(f"\n[*] Creating {len(to_create)} new applications in Notion...")
            for app in to_create:
                if self.notion.create_application(app):
                    created_count += 1
        else:
            print("[*] No net-new applications to create.")

        # 4. Process lifecycle stage updates & rejections
        updated_count = 0
        if status_updates:
            print(f"\n[*] Processing {len(status_updates)} lifecycle stage transitions...")
            # Sort updates chronologically so latest event wins
            status_updates.sort(key=lambda x: x.get('date', ''))
            for update in status_updates:
                u_comp = update.get('company') or ''
                u_date = update.get('date', '')
                u_stage = update.get('stage')
                u_deadline = update.get('deadline')
                stage_name = u_stage.value if hasattr(u_stage, 'value') else str(u_stage)

                c_norm = re.sub(r'[^a-zA-Z0-9]', '', u_comp.lower())
                if not c_norm:
                    continue
                
                # Match against existing Notion pages
                for p in existing_pages:
                    p_c_norm = re.sub(r'[^a-zA-Z0-9]', '', p.get('company', '').lower())
                    if p_c_norm and (p_c_norm == c_norm or c_norm in p_c_norm or p_c_norm in c_norm):
                        current_status = p.get('updated_status', '')
                        p_up_date = p.get('updated_date', '')

                        # Never overwrite a newer rejection with an older assessment/review
                        if 'rejected' in current_status.lower() and 'rejected' not in stage_name.lower():
                            if p_up_date and p_up_date >= u_date:
                                break

                        if current_status != stage_name or u_deadline:
                            meta = None
                            if update.get('meeting_link') or u_deadline:
                                meta = {
                                    'meeting_link': update.get('meeting_link'),
                                    'calendar_synced': False
                                }
                            if self.notion.update_stage_status(p['id'], p.get('s_no'), p.get('company'), stage_name, u_date, u_deadline, metadata=meta):
                                p['updated_status'] = stage_name
                                p['updated_date'] = u_date
                                updated_count += 1
                            break

        # 5. Auto-mark stale applications (> 30 days) as 'No Response'
        print(f"\n[*] Evaluating applications older than {NO_RESPONSE_DAYS} days for 'No Response' transition...")
        stale_count = self.notion.auto_mark_stale_applications(existing_pages)
        print(f"[*] Moved {stale_count} stale applications to 'No Response'.")

        # 6. Save sync state
        today_str = date.today().strftime('%d-%b-%Y')
        self._save_state({"last_synced_date": today_str, "last_run_timestamp": datetime.now().isoformat()})

        print("\n==================================================")
        print("✅ Sync Cycle Completed Successfully!")
        print(f"   • New Applications Created:  {created_count}")
        print(f"   • Stage Transitions Updated: {updated_count}")
        print(f"   • Stale Moved (No Response): {stale_count}")
        print("==================================================")
