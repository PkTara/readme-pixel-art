import re
import os
import sys
import ast
from enum import Enum
from datetime import datetime

import yaml
from github import Github

import src.markdown as markdown
import src.selftest as selftest


class Action(Enum):
    UNKNOWN = 0
    PAINT = 1
    RIBBET = 2
    NEW_CANVAS = 3

palette = {
    'w': {"name": "white",  "hex": "#ffffff"},
    'n': {"name": "black",  "hex": "#000000"},
    'a': {"name": "grey",   "hex": "#9e9e9e"},
    'r': {"name": "red",    "hex": "#e53935"},
    'o': {"name": "orange", "hex": "#fb8c00"},
    'y': {"name": "yellow", "hex": "#fdd835"},
    'g': {"name": "green",  "hex": "#43a047"},
    'c': {"name": "cyan",   "hex": "#00acc1"},
    'b': {"name": "blue",   "hex": "#1e88e5"},
    'p': {"name": "purple", "hex": "#8e24aa"},
    'k': {"name": "pink",   "hex": "#f06292"},
    'u': {"name": "brown",  "hex": "#6d4c41"},
}

palette_inv = {color["name"] : code for code, color in palette.items() }



def replace_text_between(original_text, marker, replacement_text):
    """Replace text between `marker['begin']` and `marker['end']` with `replacement`"""
    delimiter_a = marker['begin']
    delimiter_b = marker['end']

    if original_text.find(delimiter_a) == -1 or original_text.find(delimiter_b) == -1:
        return original_text

    leading_text = original_text.split(delimiter_a)[0]
    trailing_text = original_text.split(delimiter_b)[1]

    return leading_text + delimiter_a + replacement_text + delimiter_b + trailing_text

def update_board():
    with open('drawings/current.txt', 'r') as canvas_file:
        canvas = canvas_file.read().splitlines()
        square_md = "<img src=./img/{color}.svg>"

        output = ""
        for row in canvas:
            for char  in row:
                output += square_md.format(color=palette[char])
            output += "\n"

    with open("README.md", "r") as readme:
        with open('data/settings.yaml', 'r') as settings_file:
            settings = yaml.load(settings_file, Loader=yaml.FullLoader)

        readme_contents = readme.read()
        new_readme = replace_text_between(readme_contents, settings["markers"]["board"], output)

    with open("README.md", "w") as readme:
        readme.write(new_readme)


def parse_issue(issue):
    title = issue.title
    body = issue.body

    """Parse issue title and return a tuple with (action, <move>)"""
    if title.lower() == 'pixel: ribbet!':
        return (Action.RIBBET, None)

    if 'pixel: paint' in title.lower():
        match = re.search('Pixel: Paint ([A-H][1-8])', title, re.I)
        to_paint_coords = match.group(1).lower() if match else None

        match = re.search(r'###\s*Colou?r\s*\n+\s*(\S+)', body or '', re.I)
        to_paint_color = match.group(1).lower() if match else None


        return (
            Action.PAINT, {
            "coord" : to_paint_coords,
            "color" : to_paint_color
            }
            )

    if 'pixel: new canvas' in title.lower():
        return (Action.NEW_CANVAS, None)


    return (Action.UNKNOWN, None)


def main(issue, issue_author, repo_owner):
    action = parse_issue(issue)


    with open('data/settings.yaml', 'r') as settings_file:
        settings = yaml.load(settings_file, Loader=yaml.FullLoader)

    if action[0] == Action.RIBBET:
        issue.create_comment(settings['comments']['frog_ribbet'].format(author=issue_author))
        
        issue.edit(state = "closed")

        return True

    if action[0] == Action.PAINT:

        if not action[1]["coord"]:
            issue.create_comment(settings['comments']['paint_square_WRONG_COORD'].format(
            author=issue_author,
             ))
            issue.edit(state='closed')
            return False

        if not action[1]["color"]:
            issue.create_comment(settings['comments']['paint_square_WRONG_COLOR'].format(
            author=issue_author,
             ))

            issue.edit(state='closed')
            return False

        with open('drawings/current.txt', 'r+') as canvas_file:
            canvas = canvas_file.read().splitlines()
            x, y = (ord(action[1]["coord"].lower()[0]) - ord('a'), int(action[1]["coord"][1:]) )

            color = action[1]["color"]
            if color in palette_inv:
                row = list(canvas[x])
                row[y] = palette_inv[color]
                canvas[x] = "".join(row)
                print(canvas)

           

            canvas_file.seek(0)
            canvas_file.truncate()
            canvas_file.write("\n".join(canvas))

            
        update_board()

        issue.create_comment(settings['comments']['paint_square'].format(
            author=issue_author,
            square = action[1]["coord"],
            color = action[1]["color"]
             ))
        issue.edit(state='closed')

        return True


    if action[0] == Action.NEW_CANVAS:
        if os.path.exists('drawings/current.txt') and issue_author != repo_owner:
            issue.create_comment(settings['comments']['invalid_new_canvas'].format(author=issue_author))
            issue.edit(state='closed')
            return False, 'ERROR: A current drawing is in progress. Only the repo owner can start a new game'

        issue.create_comment(settings['comments']['successful_new_canvas'].format(author=issue_author))
        issue.edit(state='closed')

        with open('drawings/current.txt', 'w') as canvas:
            new_canvas = ""
            for col in range(10): # TODO: make this func args to NEW_CANVAS
                for row in range(10):
                    new_canvas += "w"
                new_canvas  += "\n"

            canvas.write(new_canvas)

        update_board()

        return True




    elif action[0] == Action.UNKNOWN:
        issue.create_comment(settings['comments']['unknown_command'].format(author=issue_author))
        issue.edit(state='closed', labels=['Invalid'])
        return False, 'ERROR: Unknown action'

    # Save game to "games/current.pgn"
   # print(game, file=open('games/current.pgn', 'w'), end='\n\n')

  

if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == '--self-test':
        selftest.run(main)
        sys.exit(0)
    else:
        repo = Github(os.environ['GITHUB_TOKEN']).get_repo(os.environ['GITHUB_REPOSITORY'])
        issue = repo.get_issue(number=int(os.environ['ISSUE_NUMBER']))
        issue_author = '@' + issue.user.login
        repo_owner = '@' + os.environ['REPOSITORY_OWNER']

    ret, reason = main(issue, issue_author, repo_owner)

    if ret == False:
        sys.exit(reason)
