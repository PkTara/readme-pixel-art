"""Runs the pixel test cases in tests/*.yml through unittest, one test per file.

Run from the repo root:
    uv run python -B -m unittest discover -s tests -v

or use the bot's own runner:
    uv run python -B main.py --self-test

The scenario format and the checks live in src/selftest.py.
"""

import os
import re
import sys
import types
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Don't leave __pycache__ folders in the repo
sys.dont_write_bytecode = True

# main.py imports PyGithub at the top but only uses it when run for real
try:
    import github  # noqa: F401
except ImportError:
    sys.modules['github'] = types.SimpleNamespace(Github=None)

# Import from the repo root in case main.py or src/ read files when imported
sys.path.insert(0, REPO_ROOT)
_cwd = os.getcwd()
os.chdir(REPO_ROOT)
import main as bot  # noqa: E402
import src.selftest as selftest  # noqa: E402
os.chdir(_cwd)


class TestPixel(unittest.TestCase):

    def run_scenario(self, path):
        _, results = selftest.run_scenario(path, bot.main)
        for number, (step, errors) in enumerate(results, start=1):
            with self.subTest(issue=number, title=step['title']):
                if errors:
                    self.fail('; '.join(errors))


# One test per .yml file, named after it (e.g. test_canvas_state)
for _path in selftest.scenario_files():
    _name = 'test_' + re.sub(r'\W', '_', os.path.splitext(os.path.basename(_path))[0])
    setattr(TestPixel, _name, lambda self, path=_path: self.run_scenario(path))


if __name__ == '__main__':
    unittest.main()
