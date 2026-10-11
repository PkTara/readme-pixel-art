import re
import os
import sys
import ast
import json
from enum import Enum

import yaml
from github import Github

import src.markdown as markdown
import src.selftest as selftest

CANVAS_FILE = 'data/canvas.json'


class Action(Enum):
    UNKNOWN = 0
    PAINT = 1
    RIBBET = 2


def update_top_painters(user):
    """Adds the given user to the top painters file"""
    with open('data/top_painters.txt', 'r') as file:
        dictionary = ast.literal_eval(file.read())

    dictionary[user] = dictionary.get(user, 0) + 1

    with open('data/top_painters.txt', 'w') as file:
        file.write(str(dictionary))


def update_last_paints(line):
    """Adds the given line to the top of the last paints file"""
    with open('data/last_paints.txt', 'r+') as last_paints:
        content = last_paints.read()
        last_paints.seek(0, 0)
        last_paints.write(line.rstrip('\r\n') + '\n' + content)


def replace_text_between(original_text, marker, replacement_text):
    """Replace text between `marker['begin']` and `marker['end']` with `replacement`"""
    delimiter_a = marker['begin']
    delimiter_b = marker['end']

    if original_text.find(delimiter_a) == -1 or original_text.find(delimiter_b) == -1:
        return original_text

    leading_text = original_text.split(delimiter_a)[0]
    trailing_text = original_text.split(delimiter_b)[1]

    return leading_text + delimiter_a + replacement_text + delimiter_b + trailing_text


def parse_issue(title):
    """Parse issue title and return a tuple with (action, <pixel>)"""
    if title.lower() == 'pixel: ribbet!':
        return (Action.RIBBET, None)

    match_obj = re.fullmatch(r'Pixel: Paint ([A-Z])(\d+)', title.strip(), re.I)
    if match_obj is not None:
        return (Action.PAINT, (match_obj.group(1).upper(), int(match_obj.group(2))))

    return (Action.UNKNOWN, None)


def parse_colour(body, palette):
    """Read the colour picked in the issue form. Issue forms render as '### Colour\\n\\n<value>'"""
    match_obj = re.search(r'###\s*Colou?r\s*\n+\s*([^\n]+)', body or '', re.I)
    if match_obj is None:
        return None

    colour = match_obj.group(1).strip().lower()
    return colour if colour in palette else None


def load_canvas(settings):
    if os.path.exists(CANVAS_FILE):
        with open(CANVAS_FILE, 'r') as file:
            return json.load(file)

    width = settings['canvas']['width']
    height = settings['canvas']['height']
    return [[settings['canvas']['default_colour']] * width for _ in range(height)]


def save_canvas(canvas):
    with open(CANVAS_FILE, 'w') as file:
        json.dump(canvas, file, indent=1)
        file.write('\n')


def write_readme(canvas, settings):
    with open('README.md', 'r') as file:
        readme = file.read()

    readme = replace_text_between(readme, settings['markers']['canvas'], markdown.canvas_to_markdown(canvas))
    readme = replace_text_between(readme, settings['markers']['last_paints'], markdown.generate_last_paints())
    readme = replace_text_between(readme, settings['markers']['top_painters'], markdown.generate_top_painters())

    with open('README.md', 'w') as file:
        file.write(readme)


def main(issue, issue_author, repo_owner):
    action = parse_issue(issue.title)

    with open('data/settings.yaml', 'r') as settings_file:
        settings = yaml.load(settings_file, Loader=yaml.FullLoader)

    if action[0] == Action.RIBBET:
        issue.create_comment(settings['comments']['frog_ribbet'].format(author=issue_author))
        issue.edit(state='closed')
        return True, ''

    if action[0] == Action.UNKNOWN:
        issue.create_comment(settings['comments']['unknown_command'].format(author=issue_author))
        issue.edit(state='closed', labels=['Invalid'])
        return False, 'ERROR: Unknown action'

    canvas = load_canvas(settings)
    column, row = action[1]
    pixel = f'{column}{row}'
    col_idx = ord(column) - ord('A')

    if not (0 <= col_idx < len(canvas[0]) and 1 <= row <= len(canvas)):
        issue.create_comment(settings['comments']['invalid_pixel'].format(author=issue_author, pixel=pixel))
        issue.edit(state='closed', labels=['Invalid'])
        return False, 'ERROR: Pixel is outside the canvas!'

    colour = parse_colour(issue.body, settings['palette'])
    if colour is None:
        issue.create_comment(settings['comments']['invalid_colour'].format(author=issue_author))
        issue.edit(state='closed', labels=['Invalid'])
        return False, 'ERROR: Invalid colour!'

    canvas[row - 1][col_idx] = colour
    save_canvas(canvas)

    update_last_paints(f'{pixel} {colour}: {issue_author}')
    update_top_painters(issue_author)

    issue.create_comment(settings['comments']['successful_paint'].format(author=issue_author, pixel=pixel, colour=colour))
    issue.edit(state='closed', labels=['🎨 ' + colour])

    write_readme(canvas, settings)

    return True, ''


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == '--self-test':
        sys.exit(0 if selftest.run(main) else 1)

    if len(sys.argv) >= 2 and sys.argv[1] == '--render':
        # Redraw the README from the saved canvas (or a blank one) without needing an issue
        with open('data/settings.yaml', 'r') as settings_file:
            settings = yaml.load(settings_file, Loader=yaml.FullLoader)
        canvas = load_canvas(settings)
        save_canvas(canvas)
        write_readme(canvas, settings)
        sys.exit(0)

    repo = Github(os.environ['GITHUB_TOKEN']).get_repo(os.environ['GITHUB_REPOSITORY'])
    issue = repo.get_issue(number=int(os.environ['ISSUE_NUMBER']))
    issue_author = '@' + issue.user.login
    repo_owner = '@' + os.environ['REPOSITORY_OWNER']

    ret, reason = main(issue, issue_author, repo_owner)

    if ret == False:
        sys.exit(reason)
