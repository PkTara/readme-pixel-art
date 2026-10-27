"""Runs the pixel test cases in tests/*.yml against main(). Nothing here talks to GitHub.

Each .yml file is one scenario: a list of issues opened one after another on a
fresh copy of the repo (in a temporary folder, so your real README.md and
data/ are never touched). Each issue is fed to main() as a mock issue.

Fields for each issue:
  author                 who opened it, e.g. '@player1'
  title                  the issue title, e.g. 'Pixel: Paint B2'
  colour                 picked colour, sent as the issue form body "### Colour\\n\\n<colour>"
  body                   raw issue body instead of `colour` (null for no body)
  is_invalid             the bot should refuse it (default: false)
  is_ribbet              the bot should reply RIBBET (default: false)
  canvas                 'changed' or 'unchanged' compared to the previous issue
  canvas_same_as         canvas must equal the one after issue N (counting from 1)
  canvas_differs_from    canvas must differ from the one after issue N

Every issue must be closed with exactly one comment that mentions the author.
A paint must return success and its comment must mention the pixel and colour.
An invalid issue must return failure and leave the canvas unchanged.

This assumes main(issue, issue_author, repo_owner) returns (ok, reason) and
that the canvas is drawn in README.md between CANVAS_BEGIN and CANVAS_END.
"""

import os
import re
import glob
import shutil
import tempfile
import traceback

import yaml

import src.mockGithub as mockGithub

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(REPO_ROOT, 'tests')

CANVAS_BEGIN = '<!-- BEGIN CANVAS -->'
CANVAS_END = '<!-- END CANVAS -->'


def read_canvas():
    """The part of README.md between the canvas markers, or None if they're missing"""
    with open('README.md') as file:
        readme = file.read()
    if CANVAS_BEGIN not in readme or CANVAS_END not in readme:
        return None
    return readme.split(CANVAS_BEGIN, 1)[1].split(CANVAS_END, 1)[0]


def check_step(step, issue, ok, previous, canvases):
    """Return a list of everything that went wrong with this issue (empty if it passed)"""
    errors = []
    author = step['author']
    canvas = read_canvas()

    if issue.state != 'closed':
        errors.append('issue should be closed')
    if len(issue.comments) != 1:
        errors.append(f'expected exactly one comment, got {issue.comments}')
    comment = issue.comments[0] if issue.comments else ''
    if author not in comment:
        errors.append('comment should mention the author')

    if step.get('is_ribbet'):
        if 'RIBBET' not in comment:
            errors.append('comment should say RIBBET')
    elif step.get('is_invalid'):
        if ok:
            errors.append('main() should report failure')
        if canvas != previous:
            errors.append('canvas should not change')
    else:
        if not ok:
            errors.append(f'main() should report success, comment was: {comment!r}')
        pixel = re.search(r'([A-Z])(\d+)\s*$', step['title'], re.I)
        if pixel and (pixel.group(1) + pixel.group(2)).upper() not in comment.upper():
            errors.append('comment should mention the pixel')
        if 'colour' in step and step['colour'].lower() not in comment.lower():
            errors.append('comment should mention the colour')

    checks_canvas = any(key in step for key in ('canvas', 'canvas_same_as', 'canvas_differs_from'))
    if checks_canvas and canvas is None:
        errors.append(f'README.md has no {CANVAS_BEGIN} ... {CANVAS_END} section')
    elif step.get('canvas') == 'changed' and canvas == previous:
        errors.append('canvas should change')
    elif step.get('canvas') == 'unchanged' and canvas != previous:
        errors.append('canvas should not change')
    if 'canvas_same_as' in step and canvas != canvases[step['canvas_same_as']]:
        errors.append(f"canvas should match the one after issue {step['canvas_same_as']}")
    if 'canvas_differs_from' in step and canvas == canvases[step['canvas_differs_from']]:
        errors.append(f"canvas should differ from the one after issue {step['canvas_differs_from']}")

    return errors


def run_scenario(path, main_fn):
    """Play every issue in the scenario. Returns (name, [(step, errors), ...])"""
    with open(path) as file:
        scenario = yaml.safe_load(file)

    owner = scenario['owner']
    results = []

    old_cwd = os.getcwd()
    old_repository = os.environ.get('GITHUB_REPOSITORY')
    tmp = tempfile.mkdtemp(prefix='pixel-test-')
    try:
        repo = os.path.join(tmp, 'repo')
        shutil.copytree(REPO_ROOT, repo,
                        ignore=shutil.ignore_patterns('.git', '.venv', 'tests', '__pycache__'))
        os.chdir(repo)
        os.environ['GITHUB_REPOSITORY'] = owner.lstrip('@') + '/readme-pixel-art'

        canvases = {}  # issue number -> canvas after it
        previous = read_canvas()

        for number, step in enumerate(scenario['paints'], start=1):
            body = step['body'] if 'body' in step else f"### Colour\n\n{step.get('colour', '')}"
            issue = mockGithub.Issue(step['title'], body, step['author'])

            try:
                result = main_fn(issue, step['author'], owner)
                ok = result[0] if isinstance(result, tuple) else result
                errors = check_step(step, issue, ok, previous, canvases)
            except Exception:
                errors = ['crashed:\n' + traceback.format_exc()]

            results.append((step, errors))
            canvases[number] = previous = read_canvas()
    finally:
        os.chdir(old_cwd)
        if old_repository is None:
            os.environ.pop('GITHUB_REPOSITORY', None)
        else:
            os.environ['GITHUB_REPOSITORY'] = old_repository
        shutil.rmtree(tmp)

    return scenario['name'], results


def scenario_files():
    return sorted(glob.glob(os.path.join(TESTS_DIR, '*.yml')))


def run(main_fn):
    """Run every scenario and print the results. Returns the number of failed issues"""
    passed = 0
    failed = 0

    for path in scenario_files():
        name, results = run_scenario(path, main_fn)
        print('\u001b[0m\u001b[1m\u001b[37m  ' + name)

        for step, errors in results:
            label = '{} by {}'.format(step['title'], step['author'])
            if not errors:
                print('\u001b[0m    \u001b[1m\u001b[32m✓\u001b[0m\u001b[37m {}\u001b[0m'.format(label))
                passed += 1
            else:
                print('\u001b[0m    \u001b[1m\u001b[31m✗\u001b[0m\u001b[37m {}\u001b[1m →\u001b[31m {}\u001b[0m'.format(label, '; '.join(errors)))
                failed += 1

    total = passed + failed

    print()
    print(f'\u001b[1m\u001b[33m    {total} total', end='')
    print(f'\u001b[1m\u001b[32m   {passed} passed', end='')
    print(f'\u001b[1m\u001b[31m   {failed} failed\u001b[0m')

    return failed
