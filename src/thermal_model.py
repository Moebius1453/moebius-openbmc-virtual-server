import math
from dataclasses import dataclass, field


@dataclass
class ThermalModel:
    ambient: float = 25.0
    temperature: float = 25.0
    rpm: list = field(default_factory=lambda: [10500.0] * 4)

    def step(self, seconds, load, powered, targets):
        if not math.isfinite(seconds) or not 0 < seconds <= 5:
            raise ValueError('Thermal timestep must be in (0, 5] seconds')
        if not math.isfinite(load) or not 0 <= load <= 1:
            raise ValueError('Load must be in [0, 1]')
        if len(targets) != len(self.rpm):
            raise ValueError('Expected four fan targets')
        if any(not math.isfinite(t) or not 0 <= t <= 32767 for t in targets):
            raise ValueError('Fan targets must be in [0, 32767] RPM')
        # First-order inertia keeps commanded speed separate from tach feedback.
        fraction = -math.expm1(-seconds / 2.0)
        for index, target in enumerate(targets):
            self.rpm[index] += (target - self.rpm[index]) * fraction
        airflow = sum(self.rpm) / (len(self.rpm) * 10500.0)
        cooling = 0.008 + 0.032 * airflow
        heating = (0.30 + 1.20 * load) if powered else 0.0
        equilibrium = self.ambient + heating / cooling
        self.temperature = equilibrium + (self.temperature - equilibrium) * math.exp(-cooling * seconds)
        return self.temperature, tuple(round(value) for value in self.rpm)
