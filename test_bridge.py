import unittest
from unittest.mock import Mock, patch
import json
import tempfile
from pathlib import Path
from mute_flow import bridge, CallSession, tuple_mute, Keyboard


class BridgeTests(unittest.TestCase):
    def test_failed_flow_stop_leaves_calls_muted(self):
        keyboard, restore = Mock(), Mock()
        keyboard.held.side_effect = [True, True, False]
        keyboard.flow.side_effect = [None, RuntimeError('stop failed')]
        with self.assertRaises(RuntimeError):
            bridge(keyboard, Mock(), lambda _: None, restore)
        restore.assert_not_called()

    @patch('mute_flow.command')
    def test_flow_uses_separate_start_stop_commands(self, command):
        keyboard = Keyboard('held')
        keyboard.active_session = Mock(side_effect=[None, {'uuid': 'test'}])
        keyboard.flow(True)
        keyboard.flow(False)
        self.assertEqual(command.call_args_list[0].args[0][-1], 'wispr-flow://start-hands-free')
        self.assertEqual(command.call_args_list[1].args[0][-1], 'wispr-flow://stop-hands-free')
        self.assertIn('-g', command.call_args_list[0].args[0])

    @patch('mute_flow.command')
    def test_existing_flow_session_is_not_stopped(self, command):
        keyboard = Keyboard('held')
        keyboard.active_session = Mock(return_value={'uuid': 'someone-else'})
        with self.assertRaises(RuntimeError):
            keyboard.flow(True)
        keyboard.flow(False)
        command.assert_not_called()

    def test_karabiner_release_and_new_press_end_old_hold(self):
        with tempfile.TemporaryDirectory() as directory, patch('mute_flow.ROOT', Path(directory)):
            marker = Path(directory) / '.runtime/key.token'
            marker.parent.mkdir()
            keyboard = Keyboard.__new__(Keyboard)
            keyboard.hold_token = 'first'
            marker.write_text('first')
            self.assertTrue(keyboard.held())
            marker.write_text('second')
            self.assertFalse(keyboard.held())
            marker.unlink()
            self.assertFalse(keyboard.held())

    def test_mutes_before_recording_and_releases(self):
        events = []
        keyboard = Mock()
        keyboard.held.side_effect = [True, True, True, False]
        keyboard.flow.side_effect = lambda down: events.append(('flow', down))
        bridge(keyboard, lambda apply: events.append(('mute', apply)), lambda _: None)
        self.assertEqual(events, [('mute', True), ('flow', True), ('flow', False)])

    def test_mute_failure_never_starts_dictation(self):
        keyboard = Mock()
        keyboard.held.return_value = True
        with self.assertRaises(RuntimeError):
            bridge(keyboard, Mock(side_effect=RuntimeError('Mute failed')))
        keyboard.flow.assert_not_called()

    def test_release_during_mute_does_not_start_recording(self):
        keyboard = Mock()
        keyboard.held.side_effect = [True, False]
        bridge(keyboard, Mock())
        keyboard.flow.assert_not_called()

    def test_interrupt_releases_flow_key(self):
        keyboard = Mock()
        keyboard.held.return_value = True
        with self.assertRaises(KeyboardInterrupt):
            bridge(keyboard, Mock(), Mock(side_effect=KeyboardInterrupt))
        self.assertEqual(keyboard.flow.call_args_list[-1].args, (False,))

    def test_restore_happens_after_flow_key_up(self):
        events = []
        keyboard = Mock()
        keyboard.held.side_effect = [True, True, False]
        keyboard.flow.side_effect = lambda down: events.append(('flow', down))
        bridge(keyboard, lambda _: events.append(('mute', True)), lambda _: None,
               lambda: events.append(('restore', True)))
        self.assertEqual(events, [('mute', True), ('flow', True), ('flow', False), ('restore', True)])

    def test_partial_failure_restores_calls_already_muted(self):
        keyboard, restore = Mock(), Mock()
        keyboard.held.return_value = True
        with self.assertRaises(RuntimeError):
            bridge(keyboard, Mock(side_effect=RuntimeError('Meet failed')), restore=restore)
        restore.assert_called_once()
        keyboard.flow.assert_not_called()

    def test_early_release_restores_previous_state(self):
        keyboard, restore = Mock(), Mock()
        keyboard.held.side_effect = [True, False]
        bridge(keyboard, Mock(), restore=restore)
        restore.assert_called_once()
        keyboard.flow.assert_not_called()

    @patch('mute_flow.command')
    def test_tuple_new_call_is_not_unmuted(self, command):
        session = CallSession()
        session.tuple_call = 'original'
        command.return_value = json.dumps({'in_call': True, 'call': {'call_id': 'replacement', 'muted': True}})
        session.restore_tuple()
        self.assertEqual(command.call_count, 1)

    @patch('mute_flow.command')
    def test_tuple_original_call_restored(self, command):
        session = CallSession()
        session.tuple_call = 'original'
        command.side_effect = [
            json.dumps({'in_call': True, 'call': {'call_id': 'original', 'muted': True}}),
            '{}',
            json.dumps({'in_call': True, 'call': {'call_id': 'original', 'muted': False}}),
        ]
        session.restore_tuple()
        self.assertIn('unmute', command.call_args_list[1].args[0])

    @patch('mute_flow.subprocess.run', return_value=Mock(returncode=0))
    @patch('mute_flow.command')
    def test_tuple_already_muted_not_marked_for_restoration(self, command, _run):
        session = CallSession()
        command.return_value = json.dumps({'in_call': True, 'call': {'call_id': 'original', 'muted': True}})
        self.assertEqual(tuple_mute(True, session), 'muted')
        self.assertIsNone(session.tuple_call)
        session.restore_tuple()
        self.assertEqual(command.call_count, 1)


if __name__ == '__main__':
    unittest.main()
