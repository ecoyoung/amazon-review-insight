from __future__ import annotations

import os
import signal
import subprocess
import sys


def main() -> int:
    worker_count = int(os.getenv("RQ_WORKER_CONCURRENCY", "2"))
    processes: list[subprocess.Popen[str]] = []
    try:
        for _ in range(max(worker_count, 1)):
            processes.append(
                subprocess.Popen(
                    [sys.executable, "-m", "backend.run_worker"],
                    text=True,
                )
            )
        return_codes = [process.wait() for process in processes]
        return 0 if all(code == 0 for code in return_codes) else 1
    except KeyboardInterrupt:
        for process in processes:
            process.send_signal(signal.SIGTERM)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
