import os
import re
import json
import shutil
import tempfile

import yaml

import src.mockGithub as mockGithub

# Files the bot modifies; backed up before the tests and restored afterwards
STATE_FILES = ['README.md', 'data/canvas.json', 'data/last_paints.txt', 'data/top_painters.txt']


def comment_regex(template, **kwargs):
    escaped = re.escape(template).replace('\\{', '{').replace('\\}', '}')
    return escaped.format(**kwargs)


def get_test_data(settings, step):
    expect = step['expect']
    comments = settings['comments']

    if expect == 'paint':
        return ['🎨 ' + step['colour']], [comment_regex(comments['successful_paint'], author='@.+', pixel='.+', colour='.+')]
    if expect == 'ribbet':
        return [], [comment_regex(comments['frog_ribbet'], author='@.+')]
    if expect == 'invalid_pixel':
        return ['Invalid'], [comment_regex(comments['invalid_pixel'], author='@.+', pixel='.+')]
    if expect == 'invalid_colour':
        return ['Invalid'], [comment_regex(comments['invalid_colour'], author='@.+')]
    if expect == 'unknown':
        return ['Invalid'], [comment_regex(comments['unknown_command'], author='@.+')]

    raise ValueError(f'Unknown expectation: {expect}')


def reset_state():
    if os.path.exists('data/canvas.json'):
        os.remove('data/canvas.json')
    with open('data/last_paints.txt', 'w') as file:
        file.write('')
    with open('data/top_painters.txt', 'w') as file:
        file.write('{}')


def run_test_case(filename, main_fn):
    passed = 0
    failed = 0

    with open(filename, 'r') as test_file:
        test_data = yaml.load(test_file, Loader=yaml.FullLoader)

    with open('data/settings.yaml', 'r') as settings_file:
        settings = yaml.load(settings_file, Loader=yaml.FullLoader)

    print('\u001b[0m\u001b[1m\u001b[37m  ' + test_data['name'])
    reset_state()

    for step in test_data['steps']:
        labels, comments = get_test_data(settings, step)

        body = step.get('body')
        if body is None and 'colour' in step:
            body = '### Colour\n\n' + step['colour']

        issue = mockGithub.Issue(step['title'], body or '')
        issue.expect_labels(labels)
        issue.expect_comments(comments)

        repo_owner = test_data['owner']
        os.environ['GITHUB_REPOSITORY'] = repo_owner[1:] + '/readme-pixel-art'

        main_fn(issue, step['author'], repo_owner)

        result, reason = issue.expectations_fulfilled()

        if result and 'pixel' in step:
            with open('data/canvas.json') as file:
                canvas = json.load(file)
            column, row = step['pixel'][0], int(step['pixel'][1:])
            actual = canvas[row - 1][ord(column) - ord('A')]
            if actual != step['colour']:
                result, reason = False, f'Pixel {step["pixel"]} is {actual}, expected {step["colour"]}'

        if result == True:
            print('\u001b[0m    \u001b[1m\u001b[32m✓\u001b[0m\u001b[37m {} by {}\u001b[0m'.format(step['title'], step['author']))
            passed += 1
        else:
            print('\u001b[0m    \u001b[1m\u001b[31m✗\u001b[0m\u001b[37m {} by {}\u001b[1m →\u001b[31m {}\u001b[0m'.format(step['title'], step['author'], reason))
            failed += 1

    return passed, failed


def run(main_fn):
    passed = 0
    failed = 0

    backup_dir = tempfile.mkdtemp()
    for path in STATE_FILES:
        if os.path.exists(path):
            shutil.copy(path, os.path.join(backup_dir, path.replace('/', '_')))

    try:
        for f in sorted(f for f in os.listdir('tests/') if re.match('.+\\.yml', f)):
            passed_tmp, failed_tmp = run_test_case('tests/' + f, main_fn)
            passed += passed_tmp
            failed += failed_tmp
    finally:
        for path in STATE_FILES:
            backup = os.path.join(backup_dir, path.replace('/', '_'))
            if os.path.exists(backup):
                shutil.copy(backup, path)
            elif os.path.exists(path):
                os.remove(path)
        shutil.rmtree(backup_dir)

    total = passed + failed

    print()
    print(f'\u001b[1m\u001b[33m    {total} total', end='')
    print(f'\u001b[1m\u001b[32m   {passed} passed', end='')
    print(f'\u001b[1m\u001b[31m   {failed} failed')

    return failed == 0
