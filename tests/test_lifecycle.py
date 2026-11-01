import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    'lab_manager', Path(__file__).resolve().parents[1] / 'src' / 'lab_manager.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class LifecycleTests(unittest.TestCase):
    def test_bmc_reset_preserves_paused_host_until_output_recovers(self):
        bmc = MagicMock()
        bmc.poll.return_value = None
        host = MagicMock()
        host.poll.return_value = None
        frames = [(True, True, False), (False, False, True),
                  (False, False, False), (False, False, False),
                  (True, True, False), (False, True, False)]
        state = {'index': 0}
        actions = []
        feedback = []

        class Client:
            def __init__(self, path):
                self.reset_seen = False

            def call(self, command, **arguments):
                request, reset, reboot = frames[state['index']]
                if command == 'qom-get':
                    if reboot:
                        self.reset_seen = True
                    if arguments['property'] == 'gpioD3':
                        return False
                    return request if arguments['property'] == 'gpioD1' else reset
                if command == 'query-status':
                    return {'status': 'paused', 'running': False}
                if command == 'qom-set':
                    feedback.append(arguments['value'])
                    return {}
                if command == 'system_reset':
                    actions.append('host_reset')
                    return {}
                raise AssertionError(command)

            def close(self):
                pass

        def tick(seconds):
            state['index'] += 1
            if state['index'] == len(frames):
                lab.stopping = True

        def end(process, path):
            if process is host:
                actions.append(('host_off', state['index']))
                host.poll.return_value = 0

        lab.stopping = False
        with (patch.object(lab, 'QMP', Client),
              patch.object(lab, 'RUNTIME', MagicMock()),
              patch.object(lab, 'start_bmc', return_value=bmc),
              patch.object(lab, 'start_host', return_value=host),
              patch.object(lab, 'end_process', side_effect=end),
              patch.object(lab.signal, 'signal'),
              patch.object(lab.time, 'sleep', side_effect=tick),
              patch.object(lab, 'log')):
            lab.main()
        self.assertEqual(actions, [('host_off', 5)])
        self.assertTrue(feedback[0])

    def test_graceful_request_waits_for_guest_exit_without_restarting_it(self):
        bmc = MagicMock()
        bmc.poll.return_value = None
        host = MagicMock()
        frames = [(True, False, False), (True, True, False),
                  (True, True, True), (True, True, True),
                  (False, False, True), (True, False, False)]
        state = {'index': 0}
        commands = []
        acknowledgements = []
        starts = []

        def poll():
            if state['index'] >= len(frames):
                return 0
            return 0 if frames[state['index']][2] else None

        host.poll.side_effect = poll

        class Client:
            def __init__(self, path):
                self.reset_seen = False

            def call(self, command, **arguments):
                request, shutdown, exited = frames[state['index']]
                if command == 'qom-get':
                    return {'gpioD1': request, 'gpioA1': True,
                            'gpioD3': shutdown}[arguments['property']]
                if command == 'query-status':
                    return {'status': 'running', 'running': True}
                if command == 'system_powerdown':
                    commands.append(state['index'])
                    return {}
                if command == 'qom-set':
                    if arguments['property'] == 'gpioD4':
                        acknowledgements.append((state['index'], arguments['value']))
                    return {}
                raise AssertionError(command)

            def close(self):
                pass

        def start():
            starts.append(state['index'])
            return host

        def tick(seconds):
            state['index'] += 1
            if state['index'] == len(frames):
                lab.stopping = True

        lab.stopping = False
        with (patch.object(lab, 'QMP', Client),
              patch.object(lab, 'RUNTIME', MagicMock()),
              patch.object(lab, 'start_bmc', return_value=bmc),
              patch.object(lab, 'start_host', side_effect=start),
              patch.object(lab, 'end_process'),
              patch.object(lab.signal, 'signal'),
              patch.object(lab.time, 'sleep', side_effect=tick),
              patch.object(lab, 'log')):
            lab.main()
        self.assertEqual(commands, [1])
        self.assertEqual(starts, [0, 5])
        self.assertIn((2, True), acknowledgements)
        self.assertNotIn((1, True), acknowledgements)


if __name__ == '__main__':
    unittest.main()
