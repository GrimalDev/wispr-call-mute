#!/usr/bin/env python3
"""Karabiner Alt-T bridge: mute calls, start/stop Flow, restore calls."""
import argparse
import concurrent.futures
import fcntl
import json
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent
TUPLE = '/Applications/Tuple.app/Contents/SharedSupport/bin/tuple'
FLOW_PREFS = Path.home() / 'Library/Application Support/Wispr Flow/config.json'


def command(argv, timeout=5):
    p = subprocess.run(argv, text=True, capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(f'{Path(argv[0]).name}: {p.stderr.strip() or p.stdout.strip()}')
    return p.stdout.strip()


def tuple_mute(apply=False, session=None):
    running = subprocess.run(['/usr/bin/pgrep', '-x', 'Tuple'], capture_output=True)
    if running.returncode == 1:
        return 'not running'
    if running.returncode != 0:
        raise RuntimeError('Cannot determine whether Tuple is running')
    state = json.loads(command([TUPLE, '--format', 'json', 'state']))
    if state.get('in_call') is False:
        return 'no call'
    call = state.get('call') or {}
    if state.get('in_call') is not True or not isinstance(call.get('muted'), bool):
        raise RuntimeError('Unknown Tuple call state')
    if call['muted']:
        return 'muted'
    if not apply:
        return 'unmuted'
    call_id = call['call_id']
    if session is not None:
        session.tuple_call = call_id
    command([TUPLE, '--format', 'json', 'call', 'mute', '--call', call_id])
    verified = json.loads(command([TUPLE, '--format', 'json', 'state']))
    if verified.get('in_call') is False:
        return 'call ended'
    current = verified.get('call') or {}
    if current.get('call_id') != call_id or current.get('muted') is not True:
        raise RuntimeError('Tuple did not confirm mute on the same call')
    return 'muted'


def meet_mute(apply=False, token=''):
    result = json.loads(command(['/usr/bin/osascript', '-l', 'JavaScript',
        str(ROOT / 'vivaldi.js'), 'mute' if apply else 'inspect', str(ROOT / 'meet.js'), token], timeout=8))
    states = [m['state'] for m in result['meetings']]
    if any(s not in ('muted', 'unmuted') for s in states):
        raise RuntimeError('Meet microphone control not recognized or mute not confirmed')
    if apply and any(s != 'muted' for s in states):
        raise RuntimeError('Meet did not confirm mute')
    return states or ['no meeting tabs']


def mute_calls(apply=False, session=None):
    # Both apps are attempted even if one fails. Flow starts only if both succeed.
    results, errors = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        pending = {
            pool.submit(tuple_mute, apply, session): 'Tuple',
            pool.submit(meet_mute, apply, session.token if session else ''): 'Meet',
        }
        for future, name in pending.items():
            try:
                results[name] = future.result()
            except Exception as error:
                errors.append(f'{name}: {error}')
    if errors:
        raise RuntimeError('; '.join(errors))
    return results


class CallSession:
    def __init__(self):
        self.token = uuid.uuid4().hex
        self.tuple_call = None

    def mute(self, apply=True):
        return mute_calls(apply, self)

    def restore_tuple(self):
        if self.tuple_call is None:
            return
        state = json.loads(command([TUPLE, '--format', 'json', 'state']))
        call = state.get('call') or {}
        # Never unmute a replacement call or a call that started muted.
        if state.get('in_call') is not True or call.get('call_id') != self.tuple_call:
            return
        if call.get('muted') is True:
            command([TUPLE, '--format', 'json', 'call', 'unmute', '--call', self.tuple_call])
            verified = json.loads(command([TUPLE, '--format', 'json', 'state']))
            current = verified.get('call') or {}
            if current.get('call_id') == self.tuple_call and current.get('muted') is not False:
                raise RuntimeError('Tuple did not confirm restoration')

    def restore_meet(self):
        result = json.loads(command(['/usr/bin/osascript', '-l', 'JavaScript',
            str(ROOT / 'vivaldi.js'), 'restore', str(ROOT / 'meet.js'), self.token], timeout=8))
        if any(m['state'] not in ('unmuted', 'untouched') for m in result['meetings']):
            raise RuntimeError('Meet did not confirm restoration; check its microphone')

    def restore(self):
        errors = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.restore_tuple), pool.submit(self.restore_meet)]
            for future in futures:
                try:
                    future.result()
                except Exception as error:
                    errors.append(str(error))
        if errors:
            raise RuntimeError('; '.join(errors))


class Keyboard:
    """Hold token plus Flow's native start/stop commands. No key synthesis."""
    def __init__(self, hold_token=None):
        self.hold_token = hold_token
        self.start_requested = False

    def held(self):
        if not self.hold_token:
            return False
        try:
            return (ROOT / '.runtime/key.token').read_text() == self.hold_token
        except FileNotFoundError:
            return False

    @staticmethod
    def active_session():
        return json.loads(FLOW_PREFS.read_text()).get('prefs', {}).get('activeDictationSession')

    def flow(self, down):
        if down:
            if self.active_session():
                raise RuntimeError('Flow is already recording or processing; wait for it to finish')
            self.start_requested = True
            command(['/usr/bin/open', '-g', '-b', 'com.electron.wispr-flow',
                     'wispr-flow://start-hands-free'])
            # Confirm acceptance using Flow's own recording sentinel. Its URL
            # dispatcher does not acknowledge ignored requests through open().
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self.active_session():
                    print('Flow confirmed an active dictation session', flush=True)
                    return
                if not self.held():
                    return
                time.sleep(0.03)
            raise RuntimeError('Flow did not acknowledge the start command')
        elif self.start_requested:
            command(['/usr/bin/open', '-g', '-b', 'com.electron.wispr-flow',
                     'wispr-flow://stop-hands-free'])
            self.start_requested = False


def bridge(keyboard, mute=mute_calls, sleep=time.sleep, restore=lambda: None):
    if not keyboard.held():
        return  # Released before the worker started.
    safe_to_restore = True
    try:
        mute_started = time.monotonic()
        mute(True)
        print(f'Mute preflight took {time.monotonic() - mute_started:.2f}s', flush=True)
        if not keyboard.held():
            print('Released during mute preflight; no Flow recording started', flush=True)
            return  # Never start after the physical chord was released.
        started = time.monotonic()
        try:
            safe_to_restore = False
            keyboard.flow(True)
            print('Flow started through native URL command', flush=True)
            deadline = started + 19 * 60
            while keyboard.held() and time.monotonic() < deadline:
                sleep(0.01)
        finally:
            keyboard.flow(False)
            safe_to_restore = True
            print(f'Flow stop command after {time.monotonic() - started:.2f}s', flush=True)
        # Allow Flow to handle the stop command before restoring call microphones.
        sleep(0.15)
    finally:
        if safe_to_restore:
            restore()
            print('Previous call mute states restored', flush=True)
        else:
            print('Flow stop failed; calls left muted', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--hold', action='store_true')
    parser.add_argument('--hold-token')
    parser.add_argument('--mute-only', action='store_true')
    args = parser.parse_args()
    keyboard = Keyboard(args.hold_token)
    if not args.hold:
        print(json.dumps({'flow_active': bool(keyboard.active_session()), 'calls': mute_calls(args.mute_only)}))
        return
    if not args.hold_token:
        raise RuntimeError('Use the Karabiner press/release trigger')
    runtime = ROOT / '.runtime'
    runtime.mkdir(mode=0o700, exist_ok=True)
    with (runtime / 'hold.lock').open('a') as lock:
        try:
            # A new press may arrive while the previous invocation restores
            # calls. Serialize them so the old invocation cannot unmute the new one.
            if args.hold_token:
                fcntl.flock(lock, fcntl.LOCK_EX)
            else:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        def stop(_sig, _frame):
            raise KeyboardInterrupt()
        signal.signal(signal.SIGTERM, stop)
        session = CallSession()
        bridge(keyboard, session.mute, restore=session.restore)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f'Dictation bridge error: {error}', file=sys.stderr)
        if '--hold' in sys.argv:
            subprocess.run(['/usr/bin/osascript', '-e',
                'display notification "The shortcut failed. Check Flow and your call mute controls." with title "Wispr call mute"'],
                capture_output=True, timeout=3)
        sys.exit(1)
