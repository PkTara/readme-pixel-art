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

palette = {
    'w' : {"name": "white", "hex" : "#ffffff"},
    'r' : {"name": "red", "hex" : "#ff0000"},
    'g' : {"name": "green", "hex" : "#00ff00"},
    'b' : {"name": "blue", "hex" : "#0000ff"},
    'n' : {"name": "black", "hex" : "#000000"},
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


def parse_issue(issue):
    title = issue.title
    body = issue.body

    """Parse issue title and return a tuple with (action, <move>)"""
    if title.lower() == 'pixel: ribbet!':
        return (Action.RIBBET, None)

    if 'pixel: paint' in title.lower():
        to_paint_coords = re.search('Pixel: Paint ([A-H][1-8])', title, re.I).group(1)
        to_paint_color = re.search(r'###\s*Colou?r\s*\n+\s*(\S+)', body or '', re.I).group(1)

        return (
            Action.PAINT, {
            "coord" : to_paint_coords.lower(),
            "color" : to_paint_color
            }
            )



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
        issue.create_comment(settings['comments']['paint_square'].format(
            author=issue_author,
            square = action[1]["coord"],
            color = action[1]["color"]
             ))
        issue.edit(state='closed')

        return True


    if action[0] == Action.NEW_GAME:
        if os.path.exists('drawings/current.txt') and issue_author != repo_owner:
            issue.create_comment(settings['comments']['invalid_new_game'].format(author=issue_author))
            issue.edit(state='closed')
            return False, 'ERROR: A current drawing is in progress. Only the repo owner can start a new game'

        issue.create_comment(settings['comments']['successful_new_game'].format(author=issue_author))
        issue.edit(state='closed')

        with open('data/last_moves.txt', 'w') as last_moves:
            last_moves.write('Start game: ' + issue_author)


    elif False and action[0] == Action.MOVE:
        if not os.path.exists('games/current.pgn'):
            return False, 'ERROR: There is no game in progress! Start a new game first'

        if action[1][:2] == action[1][2:]:
            issue.create_comment(settings['comments']['invalid_move'].format(author=issue_author, move=action[1]))
            issue.edit(state='closed', labels=['Invalid'])
            return False, 'ERROR: Move is invalid!'

        

        issue_labels = ['⚔️ Capture!'] # if gameboard.is_capture(move) else []
        issue_labels += ['White' ] #if gameboard.turn == chess.WHITE else 'Black']

        issue.create_comment(settings['comments']['successful_move'].format(author=issue_author, move=action[1]))
        issue.edit(state='closed', labels=issue_labels)



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
