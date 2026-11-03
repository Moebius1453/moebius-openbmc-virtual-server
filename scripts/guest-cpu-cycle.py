#!/usr/bin/env python3
"""Run a bounded two-worker CPU experiment inside the disposable guest."""
import argparse
import json
import multiprocessing
from pathlib import Path
import signal
import time


def counters():
    v = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    return sum(v), v[3] + v[4]


def burn(seconds):
    deadline = time.monotonic() + seconds + 5
    while time.monotonic() < deadline:
        sum(i * i for i in range(10000))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--warmup', type=int, default=120)
    parser.add_argument('--load-seconds', type=int, default=120)
    parser.add_argument('--cooldown', type=int, default=120)
    args = parser.parse_args()
    if any(not 10 <= value <= 180 for value in
           (args.warmup, args.load_seconds, args.cooldown)):
        parser.error('Each phase must be between 10 and 180 seconds')
    workers = []
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    previous = counters()
    duration = args.warmup + args.load_seconds + args.cooldown
    try:
        for second in range(duration):
            if second == args.warmup:
                workers = [multiprocessing.Process(target=burn, args=(args.load_seconds,)) for _ in range(2)]
                for worker in workers:
                    worker.start()
            if second == args.warmup + args.load_seconds:
                for worker in workers:
                    if worker.is_alive():
                        worker.terminate()
                    worker.join(timeout=3)
            time.sleep(1)
            current = counters()
            total = current[0] - previous[0]
            idle = current[1] - previous[1]
            if total <= 0 or not 0 <= idle <= total:
                raise RuntimeError('CPU counter discontinuity')
            print(json.dumps({'load': (total - idle) / total,
                              'source': 'guest-proc-stat',
                              'phase': 'idle' if second < args.warmup else 'load' if second < args.warmup + args.load_seconds else 'cooldown',
                              'elapsed_seconds': second + 1,
                              'total_seconds': duration,
                              'sampled_at': time.time()}), flush=True)
            previous = current
    finally:
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
            worker.join(timeout=3)
