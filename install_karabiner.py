#!/usr/bin/env python3
"""Install one Karabiner rule without changing other shortcuts or Flow settings."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shlex
import shutil
import sys

ROOT = Path(__file__).resolve().parent
DESCRIPTION = 'Wispr call mute: hold Option-T, restore call mutes on release'


def make_rule(root=ROOT, python=sys.executable):
    command = shlex.join([str(python), str(root / 'key_control.py')])
    return {
        'description': DESCRIPTION,
        'manipulators': [{
            'type': 'basic',
            'from': {'key_code': 't', 'modifiers': {'mandatory': ['option']}},
            'to': [{'shell_command': command + ' press'}],
            'to_after_key_up': [{'shell_command': command + ' release'}],
        }],
    }


def update_profile(config, rule, remove=False):
    profiles = [p for p in config.get('profiles', []) if p.get('selected')]
    if len(profiles) != 1:
        raise ValueError('Select one profile in Karabiner-Elements first.')
    rules = profiles[0].setdefault('complex_modifications', {}).setdefault('rules', [])
    rules[:] = [r for r in rules if r.get('description') != DESCRIPTION]
    if not remove:
        rules.insert(0, rule)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remove', action='store_true', help='Remove this rule from the selected profile')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('This automation requires macOS.')
    if sys.version_info < (3, 9):
        parser.error('Python 3.9 or newer is required.')
    path = Path.home() / '.config/karabiner/karabiner.json'
    if not path.exists():
        parser.error('Open Karabiner-Elements once to create its configuration, then retry.')
    original = path.read_text()
    config = json.loads(original)
    try:
        update_profile(config, make_rule(), args.remove)
    except ValueError as error:
        parser.error(str(error))
    if config == json.loads(original):
        print('Already configured; no changes needed.')
        return
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = path.with_name('karabiner.before-wispr-' + stamp + '.json')
    shutil.copy2(path, backup)
    temporary = path.with_name('karabiner.wispr-' + stamp + '.tmp')
    try:
        temporary.write_text(json.dumps(config, indent=4) + '\n')
        os.chmod(temporary, path.stat().st_mode & 0o777)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    print('Wispr call mute rule ' + ('removed.' if args.remove else 'installed. Hold Option-T to dictate; release T to stop.'))
    print(f'Backup: {backup}')


if __name__ == '__main__':
    main()
