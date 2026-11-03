import json
import math
from pathlib import Path
import time

from thermal_model import ThermalModel


class ThermalBridge:
    def __init__(self, state):
        self.state = Path(state)
        self.model = ThermalModel()
        self.fan_path = None
        self.temperature_path = None
        self.previous = None
        self.last_log = 0

    def discover(self, qmp):
        devices = qmp.call('qom-list', path='/machine/unattached')
        for device in devices:
            kind = device.get('type', '')
            path = '/machine/unattached/' + device['name']
            if kind == 'child<max31785>':
                self.fan_path = path
            elif kind == 'child<tmp105>':
                self.temperature_path = path
        if self.fan_path is None or self.temperature_path is None:
            raise RuntimeError('Thermal bridge needs MAX31785 and TMP105')
        qmp.call('qom-set', path=self.fan_path,
                 property='external-fan-feedback', value=True)
        self.previous = time.monotonic()

    def step(self, qmp, powered):
        if self.fan_path is None:
            self.discover(qmp)
        now = time.monotonic()
        elapsed = now - self.previous
        if elapsed < 1:
            return
        # One delayed poll must not jump the physical model across a reboot.
        elapsed = min(elapsed, 5)
        load = 0.0
        source = 'host-off'
        if powered:
            try:
                request = json.loads((self.state / 'thermal-load.json').read_text())
                if not isinstance(request, dict):
                    raise ValueError('Thermal input must be an object')
            except (OSError, ValueError):
                request = {'load': 1.0, 'source': 'guest-proc-stat', 'received_at': 0}
            load = request['load']
            if isinstance(load, bool) or not isinstance(load, (float, int)):
                raise ValueError('Thermal load must be numeric')
            if not math.isfinite(load) or not 0 <= load <= 1:
                raise ValueError('Thermal load must be in [0, 1]')
            source = request.get('source', 'manual')
            if source == 'guest-proc-stat':
                received = request.get('received_at')
                if (isinstance(received, bool)
                        or not isinstance(received, (int, float))
                        or not math.isfinite(received)
                        or not 0 <= time.time() - received <= 5):
                    # Stale telemetry must not make an active host look idle.
                    load = 1.0
                    source = 'stale-guest-conservative'
            elif source != 'manual':
                raise ValueError('Unknown thermal load source')
        targets = [qmp.call('qom-get', path=self.fan_path,
                            property=f'fan{i}-target') for i in range(4)]
        temperature, rpm = self.model.step(elapsed, load, powered, targets)
        for index, value in enumerate(rpm):
            qmp.call('qom-set', path=self.fan_path,
                     property=f'fan{index}-actual', value=value)
        qmp.call('qom-set', path=self.temperature_path,
                 property='temperature', value=round(temperature * 1000))
        self.previous = now
        if now - self.last_log >= 5:
            print(json.dumps({'event': 'thermal_sample', 'load_source': source,
                              'load': load, 'powered': powered,
                              'temperature_c': round(temperature, 3),
                              'target_rpm': targets, 'actual_rpm': rpm}), flush=True)
            self.last_log = now
