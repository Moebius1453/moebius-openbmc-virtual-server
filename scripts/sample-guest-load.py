#!/usr/bin/env python3
"""Sample CPU utilization inside the guest; emit one JSON record per second."""
import argparse
import json
from pathlib import Path
import time


def cpu_times(text):
    fields = text.splitlines()[0].split()
    if fields[0] != 'cpu' or len(fields) < 6:
        raise ValueError('Missing aggregate CPU counters')
    # guest and guest_nice are already included in user and nice.
    values = [int(value) for value in fields[1:9]]
    return sum(values), values[3] + (values[4] if len(values) > 4 else 0)


def utilization(previous, current):
    total = current[0] - previous[0]
    idle = current[1] - previous[1]
    if total <= 0 or idle < 0 or idle > total:
        raise ValueError('CPU counters reset or did not advance')
    return (total - idle) / total


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.samples <= 600:
        parser.error('samples must be between 1 and 600')
    previous = cpu_times(Path('/proc/stat').read_text())
    for _ in range(args.samples):
        time.sleep(1)
        current = cpu_times(Path('/proc/stat').read_text())
        print(json.dumps({'load': utilization(previous, current),
                          'source': 'guest-proc-stat',
                          'sampled_at': time.time()}), flush=True)
        previous = current
