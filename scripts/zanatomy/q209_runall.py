#!/usr/bin/env python3
"""Q209: run a list of shell job lines (one per line) with N parallel workers; logs build/q209_logs/jobNN.log, status in status.txt."""
import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
jobs = [l.strip() for l in Path(sys.argv[1]).read_text().splitlines() if l.strip()]
(REPO / "build/q209_logs").mkdir(parents=True, exist_ok=True)

def run(i):
    with open(REPO / f"build/q209_logs/job{i+1:02d}.log", "w") as f:
        rc = subprocess.call(jobs[i], shell=True, cwd=REPO, stdout=f, stderr=subprocess.STDOUT)
    with open(REPO / "build/q209_logs/status.txt", "a") as f:
        f.write(f"job{i+1:02d} rc={rc} {jobs[i]}\n")

with ThreadPoolExecutor(int(sys.argv[2])) as ex:
    list(ex.map(run, range(len(jobs))))
