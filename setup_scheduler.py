import sys
import subprocess
from pathlib import Path

def setup_task(time_str="09:00", task_name="JobHelperDailySync"):
    """
    Registers a native Windows Scheduled Task to run Job Helper daily at the specified time.
    time_str format: 'HH:MM' (24-hour, e.g. '09:00' or '22:30')
    """
    python_exe = sys.executable
    script_path = Path(__file__).resolve().parent / "run_sync.py"

    cmd = [
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", f'"{python_exe}" "{script_path}"',
        "/sc", "daily",
        "/st", time_str,
        "/f"
    ]

    print(f"[*] Registering Windows Scheduled Task '{task_name}' for daily run at {time_str}...")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[+] Task '{task_name}' registered successfully to run daily at {time_str}!")
            print(f"    Command: {python_exe} {script_path}")
        else:
            print(f"[-] Failed to register task:\n{res.stderr}")
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    time_arg = sys.argv[1] if len(sys.argv) > 1 else "09:00"
    setup_task(time_arg)
