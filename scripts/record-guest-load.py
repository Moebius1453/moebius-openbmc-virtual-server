#!/usr/bin/env python3
"""Validate guest sampler JSON lines and append a private evidence stream."""
import argparse
import json
import math
from pathlib import Path
import sys
import time


def validate(record):
    if not isinstance(record, dict) or record.get('source') != 'guest-proc-stat':
        raise ValueError('Expected a guest-proc-stat object')
    load = record.get('load')
    if isinstance(load, bool) or not isinstance(load, (int, float)):
        raise ValueError('CPU utilization must be numeric')
    if not math.isfinite(load) or not 0 <= load <= 1:
        raise ValueError('CPU utilization must be in [0, 1]')
    return {'load': load, 'source': 'guest-proc-stat', 'received_at': time.time()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    # Explicitly append a private sample stream; never replace manual input here.
    if args.destination.exists():
        raise SystemExit('Use a new stream path; existing data is not overwritten')
    with args.destination.open('x') as stream:
        for line in sys.stdin:
            record = validate(json.loads(line))
            stream.write(json.dumps(record) + '\n')
            stream.flush()
