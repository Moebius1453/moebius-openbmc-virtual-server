import unittest
from src.thermal_model import ThermalModel


class ThermalTests(unittest.TestCase):
    def test_load_heats_and_airflow_cools(self):
        idle = ThermalModel()
        loaded = ThermalModel()
        fast = ThermalModel()
        for _ in range(180):
            idle.step(1, 0, True, [5000] * 4)
            loaded.step(1, 1, True, [5000] * 4)
            fast.step(1, 1, True, [10500] * 4)
        self.assertGreater(loaded.temperature, idle.temperature)
        self.assertGreater(loaded.temperature, fast.temperature)

    def test_fan_has_inertia(self):
        model = ThermalModel()
        _, rpm = model.step(1, 0, False, [5000] * 4)
        self.assertTrue(all(5000 < speed < 10500 for speed in rpm))

    def test_power_off_cools_toward_ambient(self):
        model = ThermalModel(temperature=60)
        model.step(1, 1, False, [8000] * 4)
        self.assertTrue(25 < model.temperature < 60)

    def test_bad_load_is_rejected(self):
        with self.assertRaises(ValueError):
            ThermalModel().step(1, float('nan'), True, [8000] * 4)
