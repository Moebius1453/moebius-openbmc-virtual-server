#!/usr/bin/env python3
"""Stage the controller when invoked; bounded retries accommodate BMC startup."""
import argparse
from pathlib import Path
import subprocess
import sys
import time


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempts', type=int, default=12)
    p.add_argument('stage_arguments', nargs=argparse.REMAINDER)
    a = p.parse_args()
    if not 1 <= a.attempts <= 20:
        p.error('attempts must be between 1 and 20')
    arguments = a.stage_arguments
    if arguments[:1] == ['--']:
        arguments = arguments[1:]
    if not arguments:
        p.error('Supply stage-x86-fan-controller.py arguments after --')
    script = Path(__file__).with_name('stage-x86-fan-controller.py')
    for attempt in range(a.attempts):
        result = subprocess.run([sys.executable, str(script), *arguments],
                                timeout=90, check=False)
        if result.returncode == 0:
            break
        if result.returncode != 75 or attempt + 1 == a.attempts:
            raise SystemExit(result.returncode)
        print('BMC staging not ready; retry in 15 seconds', flush=True)
        time.sleep(15)
