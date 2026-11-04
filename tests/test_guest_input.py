import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class GuestInputTests(unittest.TestCase):
    def test_cpu_guest_time_is_not_counted_twice(self):
        sampler = module('sampler', 'scripts/sample-guest-load.py')
        self.assertEqual(sampler.cpu_times('cpu 10 0 10 70 10 0 0 0 8 0\n'),
                         (100, 80))

    def test_cpu_delta(self):
        sampler = module('sampler_delta', 'scripts/sample-guest-load.py')
        self.assertEqual(sampler.utilization((100, 80), (200, 100)), 0.8)

    def test_cpu_reset_is_rejected(self):
        sampler = module('sampler_reset', 'scripts/sample-guest-load.py')
        with self.assertRaises(ValueError):
            sampler.utilization((100, 80), (50, 40))

    def test_record_rejects_bool_and_nonfinite(self):
        recorder = module('recorder', 'scripts/record-guest-load.py')
        for value in (True, float('nan'), -1, 2):
            with self.subTest(value=value), self.assertRaises(ValueError):
                recorder.validate({'source': 'guest-proc-stat', 'load': value})

    def test_record_keeps_actual_source(self):
        recorder = module('recorder_valid', 'scripts/record-guest-load.py')
        record = recorder.validate({'source': 'guest-proc-stat', 'load': 0.25})
        self.assertEqual(record['load'], 0.25)
        self.assertEqual(record['source'], 'guest-proc-stat')
        self.assertIn('received_at', record)
