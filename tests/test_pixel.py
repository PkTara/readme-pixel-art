"""Black-box tests for the pixel bot. Nothing here talks to GitHub.

Run from the repo root:
    .venv/bin/python -B -m unittest discover -s tests -v

Each test copies the repo into a temporary folder, runs main() there with a
fake issue, then checks what the bot said and what happened to the README.
Your real README.md and data/ are never touched.

The tests only assume this much about your code (change the constants below
if you pick something different):
  - main(issue, issue_author, repo_owner) is the entry point and returns
    (ok, reason), like the chess version does
  - the issue title is "Pixel: Paint <column><row>", e.g. "Pixel: Paint B2"
  - the colour comes from the issue body, the way a GitHub issue form with a
    "Colour" dropdown renders it: "### Colour\n\nred"
  - the canvas is drawn in README.md between CANVAS_BEGIN and CANVAS_END
"""

import os
import re
import sys
import shutil
import tempfile
import types
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COLUMNS = 'ABCDEFGHIJKL'   # 12 columns
ROWS = 16
PALETTE = ['white', 'black', 'grey', 'red', 'orange', 'yellow',
           'green', 'cyan', 'blue', 'purple', 'pink', 'brown']
CANVAS_BEGIN = '<!-- BEGIN CANVAS -->'
CANVAS_END = '<!-- END CANVAS -->'

AUTHOR = '@someone'
OWNER = '@PkTara'

# main.py imports PyGithub at the top but only uses it when run for real
if 'github' not in sys.modules:
    try:
        import github  # noqa: F401
    except ImportError:
        sys.modules['github'] = types.SimpleNamespace(Github=None)

# Don't leave __pycache__ folders in the repo
sys.dont_write_bytecode = True

# Import from the repo root in case main.py or src/ read files when imported
sys.path.insert(0, REPO_ROOT)
_cwd = os.getcwd()
os.chdir(REPO_ROOT)
import main as bot  # noqa: E402
os.chdir(_cwd)


class FakeIssue:
    """Stands in for a PyGithub Issue and records everything the bot does to it"""

    def __init__(self, title, body=''):
        self.title = title
        self.body = body
        self.user = types.SimpleNamespace(login=AUTHOR.lstrip('@'))
        self.comments = []
        self.labels = []
        self.state = 'open'

    def create_comment(self, text):
        self.comments.append(text)

    def edit(self, state=None, labels=None, **kwargs):
        if state is not None:
            self.state = state
        if labels is not None:
            self.labels = list(labels)

    def add_to_labels(self, *labels):
        self.labels += list(labels)


def colour_body(colour):
    return f'### Colour\n\n{colour}'


class PixelTestCase(unittest.TestCase):

    def setUp(self):
        self.old_cwd = os.getcwd()
        self.tmp = tempfile.mkdtemp(prefix='pixel-test-')
        self.repo = os.path.join(self.tmp, 'repo')
        shutil.copytree(REPO_ROOT, self.repo,
                        ignore=shutil.ignore_patterns('.git', '.venv', 'tests', '__pycache__'))
        os.chdir(self.repo)
        os.environ.setdefault('GITHUB_REPOSITORY', 'PkTara/readme-pixel-art')
        self.blank_readme = self.readme()

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.tmp)

    # Helpers

    def run_bot(self, title, body='', author=AUTHOR):
        issue = FakeIssue(title, body)
        result = bot.main(issue, author, OWNER)
        ok = result[0] if isinstance(result, tuple) else result
        return issue, ok

    def paint(self, pixel, colour, author=AUTHOR):
        return self.run_bot(f'Pixel: Paint {pixel}', colour_body(colour), author)

    def readme(self):
        with open('README.md') as file:
            return file.read()

    def canvas(self, readme=None):
        """The part of the README between the canvas markers"""
        readme = readme if readme is not None else self.readme()
        if CANVAS_BEGIN not in readme or CANVAS_END not in readme:
            self.fail(f'README.md has no {CANVAS_BEGIN} ... {CANVAS_END} section')
        return readme.split(CANVAS_BEGIN, 1)[1].split(CANVAS_END, 1)[0]

    def assertClosedWithComment(self, issue):
        self.assertEqual(issue.state, 'closed', 'issue should be closed')
        self.assertEqual(len(issue.comments), 1, f'expected exactly one comment, got {issue.comments}')
        self.assertIn(AUTHOR, issue.comments[0], 'comment should mention the author')

    def assertRejected(self, issue, ok):
        self.assertClosedWithComment(issue)
        self.assertFalse(ok, 'main() should report failure')
        self.assertEqual(self.canvas(), self.canvas(self.blank_readme), 'canvas should not change')


class TestRibbet(PixelTestCase):

    def test_ribbet(self):
        issue, _ = self.run_bot('Pixel: Ribbet!')
        self.assertEqual(issue.state, 'closed')
        self.assertTrue(any('RIBBET' in c for c in issue.comments))


class TestPaint(PixelTestCase):

    def test_paint_closes_issue_and_thanks_author(self):
        issue, ok = self.paint('B2', 'red')
        self.assertTrue(ok)
        self.assertClosedWithComment(issue)
        self.assertIn('B2', issue.comments[0])
        self.assertIn('red', issue.comments[0])

    def test_paint_changes_canvas(self):
        self.paint('B2', 'white')
        before = self.canvas()
        self.paint('B2', 'red')
        self.assertNotEqual(self.canvas(), before)

    def test_every_colour_in_palette_works(self):
        for colour in PALETTE:
            with self.subTest(colour=colour):
                issue, ok = self.paint('A1', colour)
                self.assertTrue(ok, issue.comments)

    def test_corners(self):
        for pixel in ['A1', f'{COLUMNS[-1]}1', f'A{ROWS}', f'{COLUMNS[-1]}{ROWS}']:
            with self.subTest(pixel=pixel):
                issue, ok = self.paint(pixel, 'blue')
                self.assertTrue(ok, issue.comments)

    def test_different_pixels_draw_differently(self):
        self.paint('A1', 'red')
        a1 = self.canvas()
        self.tearDown()
        self.setUp()
        self.paint('B1', 'red')
        self.assertNotEqual(a1, self.canvas())

    def test_different_colours_draw_differently(self):
        self.paint('A1', 'red')
        red = self.canvas()
        self.paint('A1', 'blue')
        self.assertNotEqual(red, self.canvas())

    def test_paints_add_up(self):
        """A second paint keeps the first one instead of starting from a blank canvas"""
        self.paint('A1', 'red')
        self.paint('B1', 'blue')
        both = self.canvas()
        self.tearDown()
        self.setUp()
        self.paint('B1', 'blue')
        self.assertNotEqual(both, self.canvas())

    def test_painting_back_restores_canvas(self):
        self.paint('C3', 'white')
        before = self.canvas()
        self.paint('C3', 'red')
        self.paint('C3', 'white')
        self.assertEqual(self.canvas(), before)

    def test_same_paint_twice_is_fine(self):
        self.paint('C3', 'green')
        once = self.canvas()
        issue, ok = self.paint('C3', 'green')
        self.assertTrue(ok, issue.comments)
        self.assertEqual(self.canvas(), once)

    def test_lowercase_coordinate(self):
        issue, ok = self.paint('b2', 'red')
        self.assertTrue(ok, issue.comments)

    def test_colour_is_case_insensitive(self):
        issue, ok = self.paint('B2', 'Red')
        self.assertTrue(ok, issue.comments)

    def test_spelled_color(self):
        issue, ok = self.run_bot('Pixel: Paint B2', '### Color\n\nred')
        self.assertTrue(ok, issue.comments)

    def test_body_with_windows_line_endings(self):
        issue, ok = self.run_bot('Pixel: Paint B2', '### Colour\r\n\r\nred\r\n')
        self.assertTrue(ok, issue.comments)


class TestInvalid(PixelTestCase):

    def test_column_off_canvas(self):
        next_column = chr(ord(COLUMNS[-1]) + 1)
        self.assertRejected(*self.paint(f'{next_column}1', 'red'))

    def test_row_zero(self):
        self.assertRejected(*self.paint('A0', 'red'))

    def test_row_off_canvas(self):
        self.assertRejected(*self.paint(f'A{ROWS + 1}', 'red'))

    def test_huge_row(self):
        self.assertRejected(*self.paint('A99999999999', 'red'))

    def test_no_coordinate(self):
        self.assertRejected(*self.run_bot('Pixel: Paint ', colour_body('red')))

    def test_colour_not_in_palette(self):
        self.assertRejected(*self.paint('B2', 'turquoise'))

    def test_empty_body(self):
        self.assertRejected(*self.run_bot('Pixel: Paint B2', ''))

    def test_missing_body(self):
        self.assertRejected(*self.run_bot('Pixel: Paint B2', None))

    def test_no_response_dropdown(self):
        # What GitHub writes when a form field is left empty
        self.assertRejected(*self.run_bot('Pixel: Paint B2', '### Colour\n\n_No response_'))

    def test_unknown_command(self):
        self.assertRejected(*self.run_bot('Pixel: Do a backflip', ''))

    def test_extra_text_after_coordinate(self):
        self.assertRejected(*self.run_bot('Pixel: Paint B2 and C3', colour_body('red')))


if __name__ == '__main__':
    unittest.main()
