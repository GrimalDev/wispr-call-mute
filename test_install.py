import copy
from pathlib import Path
import shlex
import unittest

from install_karabiner import DESCRIPTION, make_rule, update_profile


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.existing = {'description': 'Existing shortcut', 'manipulators': []}
        self.config = {'profiles': [
            {'name': 'Active', 'selected': True, 'complex_modifications': {'rules': [self.existing]}},
            {'name': 'Other', 'selected': False, 'complex_modifications': {'rules': [self.existing]}},
        ]}

    def test_install_and_remove_preserve_unrelated_rules_and_profiles(self):
        original = copy.deepcopy(self.config)
        update_profile(self.config, make_rule())
        rules = self.config['profiles'][0]['complex_modifications']['rules']
        self.assertEqual(rules[0]['description'], DESCRIPTION)
        self.assertEqual(rules[1], self.existing)
        self.assertEqual(self.config['profiles'][1], original['profiles'][1])
        update_profile(self.config, make_rule(), remove=True)
        self.assertEqual(self.config, original)

    def test_reinstall_replaces_instead_of_duplicating(self):
        update_profile(self.config, make_rule(Path('/old path')))
        update_profile(self.config, make_rule(Path('/new path')))
        rules = self.config['profiles'][0]['complex_modifications']['rules']
        self.assertEqual(len(rules), 2)
        self.assertIn('/new path', rules[0]['manipulators'][0]['to'][0]['shell_command'])

    def test_shell_arguments_with_spaces_and_metacharacters_are_literal(self):
        root = Path('/tmp/some path/$(echo unsafe)/quote\'')
        rule = make_rule(root, '/tmp/python path/python3')
        args = shlex.split(rule['manipulators'][0]['to'][0]['shell_command'])
        self.assertEqual(args, ['/tmp/python path/python3', str(root / 'key_control.py'), 'press'])

    def test_missing_selected_profile_is_rejected_without_changes(self):
        for profile in self.config['profiles']:
            profile['selected'] = False
        original = copy.deepcopy(self.config)
        with self.assertRaises(ValueError):
            update_profile(self.config, make_rule())
        self.assertEqual(self.config, original)


if __name__ == '__main__':
    unittest.main()
