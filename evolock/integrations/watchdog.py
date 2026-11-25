"""
EvoLock Watchdog — tự khởi động lại EvoLock nếu bị tắt.
Thêm watchdog.py vào Windows startup cùng với main.py để bảo vệ.
"""
import os
import time
import subprocess
import sys
import psutil
from evolock.paths import MAIN_SCRIPT, PROJECT_ROOT
from evolock.integrations.instance import is_instance_running

PYTHON = sys.executable
MAIN   = str(MAIN_SCRIPT)
MAIN_ABS = os.path.abspath(MAIN)
INTERVAL = 15


def _is_running() -> bool:
    # Authoritative for updated launchers, regardless of Python flags or cwd.
    if is_instance_running():
        return True
    for proc in psutil.process_iter(["cmdline"]):
        try:
            cmdline = proc.info["cmdline"] or []
            if len(cmdline) < 2:
                continue
            # Also recognize older processes started before the instance guard.
            index = 1
            while index < len(cmdline):
                arg = cmdline[index]
                if arg == '-m':
                    if index + 1 < len(cmdline) and cmdline[index + 1] == 'evolock':
                        if os.path.normcase(os.path.abspath(proc.cwd())) == os.path.normcase(str(PROJECT_ROOT)):
                            return True
                    break
                if arg == '-c':
                    break
                if arg in ('-W', '-X'):
                    index += 2
                    continue
                if arg.startswith('-'):
                    index += 1
                    continue
                script = arg if os.path.isabs(arg) else os.path.join(proc.cwd(), arg)
                if os.path.normcase(os.path.abspath(script)) == os.path.normcase(MAIN_ABS):
                    return True
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def main():
    devnull = open(os.devnull, "w")
    while True:
        time.sleep(INTERVAL)
        if not _is_running():
            subprocess.Popen([PYTHON, MAIN], stdout=devnull, stderr=devnull)


if __name__ == "__main__":
    main()
