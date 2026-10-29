import sys
import argparse
import subprocess
from pathlib import Path

def setup_task(schedule_type="daily", time_str="09:00", interval_minutes=30, task_name="JobHelperSync"):
    """
    Registers a native Windows Scheduled Task to run Job Helper.
    Supports either daily (at HH:MM) or interval in minutes (e.g. every 15 or 30 mins).
    """
    python_exe = sys.executable
    script_path = Path(__file__).resolve().parent / "run_sync.py"

    if schedule_type == "minute":
        cmd = [
            "schtasks", "/create",
            "/tn", task_name,
            "/tr", f'"{python_exe}" "{script_path}"',
            "/sc", "minute",
            "/mo", str(interval_minutes),
            "/f"
        ]
        desc = f"every {interval_minutes} minutes"
    else:
        cmd = [
            "schtasks", "/create",
            "/tn", task_name,
            "/tr", f'"{python_exe}" "{script_path}"',
            "/sc", "daily",
            "/st", time_str,
            "/f"
        ]
        desc = f"daily at {time_str}"

    print(f"[*] Registering Windows Scheduled Task '{task_name}' to run {desc}...")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[+] Task '{task_name}' registered successfully ({desc})!")
            print(f"    Command: {python_exe} {script_path}")
        else:
            print(f"[-] Failed to register task:\n{res.stderr}")
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configure Job Helper Windows Task Scheduler")
    parser.add_argument("--minutes", type=int, help="Run every N minutes (e.g. --minutes 30 or --minutes 15)")
    parser.add_argument("--daily", type=str, default="09:00", help="Run daily at specific time (e.g. --daily 09:00)")
    args = parser.parse_args()

    if args.minutes:
        setup_task(schedule_type="minute", interval_minutes=args.minutes)
    else:
        setup_task(schedule_type="daily", time_str=args.daily)
