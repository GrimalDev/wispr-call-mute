#!/usr/bin/env python3
"""Short Karabiner callbacks; recording runs in a detached worker."""
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / '.runtime'


def handle(action):
    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    marker = RUNTIME / 'key.token'
    if action == 'release':
        marker.unlink(missing_ok=True)
        return
    if action != 'press':
        raise ValueError('Expected press or release')
    token = uuid.uuid4().hex
    temporary = marker.with_suffix('.' + token + '.tmp')
    temporary.write_text(token)
    os.replace(temporary, marker)
    with (RUNTIME / 'bridge.log').open('a') as log:
        subprocess.Popen([sys.executable, str(ROOT / 'mute_flow.py'),
                          '--hold', '--hold-token', token],
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, close_fds=True)


if __name__ == '__main__':
    handle(sys.argv[1])
