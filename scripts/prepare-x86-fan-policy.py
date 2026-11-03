#!/usr/bin/env python3
"""Generate an explicit virtual-x86 policy without changing OCC state."""
import argparse
from pathlib import Path

OLD = '''              - name: occ0_object
                interface: org.open_power.OCC.Status
                property:
                    name: OccActive
                    type: bool
                    value: true
              - name: occ1_object
                interface: org.open_power.OCC.Status
                property:
                    name: OccActive
                    type: bool
                    value: true
'''
NEW = '''              - name: poweron_pgood
                interface: org.openbmc.control.Power
                property:
                    name: pgood
                    type: int32_t
                    value: 1
'''


def adapt(text):
    marker = '    - name: occ_active_speed_changes\n'
    if text.count(marker) != 1:
        raise ValueError('Expected exactly one OCC-gated temperature policy')
    before, section = text.split(marker, 1)
    if section.count(OLD) != 1:
        raise ValueError('Unsupported policy activation block')
    section = section.replace(OLD, NEW, 1)
    return before + '    - name: virtual_x86_powered_speed_changes\n' + section


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = adapt(args.source.read_text())
    with args.output.open('x') as stream:
        stream.write(result)
