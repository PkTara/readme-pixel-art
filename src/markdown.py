from urllib.parse import urlencode
import os
import ast
import string
import html

import yaml

with open('data/settings.yaml', 'r') as settings_file:
    settings = yaml.load(settings_file, Loader=yaml.FullLoader)


def create_link(text, link):
    return f"[{text}]({link})"

def create_paint_link(pixel):
    params = {
        'template': settings['issues']['paint']['template'],
        'title': settings['issues']['paint']['title'].format(pixel=pixel),
    }

    return settings['issues']['link'].format(
        repo=os.environ["GITHUB_REPOSITORY"],
        params=urlencode(params))

def column_names(width):
    return string.ascii_uppercase[:width]

def generate_top_painters():
    with open("data/top_painters.txt", 'r') as file:
        dictionary = ast.literal_eval(file.read())

    markdown = "\n"
    markdown += "| Pixels painted |  User  |\n"
    markdown += "| :------------: | :----- |\n"

    max_entries = settings['misc']['max_top_painters']
    for key,val in sorted(dictionary.items(), key=lambda x: x[1], reverse=True)[:max_entries]:
        markdown += "| {} | {} |\n".format(val, create_link(key, "https://github.com/" + key[1:]))

    return markdown + "\n"

def generate_last_paints():
    markdown = "\n"
    markdown += "| Pixel | Colour | Author |\n"
    markdown += "| :---: | :----: | :----- |\n"

    with open("data/last_paints.txt", 'r') as file:
        lines = [line.rstrip() for line in file.readlines() if line.strip()]

    for line in lines[:settings['misc']['max_last_paints']]:
        # Format: "<pixel> <colour>: <@author>"
        paint, author = line.split(':', 1)
        pixel, colour = paint.split()
        author = author.strip()

        markdown += "| `{}` | <img src=\"img/pixels/{}.svg\" width=12px> {} | {} |\n".format(
            pixel, colour, colour, create_link(author, "https://github.com/" + author[1:]))

    return markdown + "\n"

def canvas_to_markdown(canvas):
    # Plain linked images rather than a table: GitHub pads every table cell,
    # which makes a 16x16 canvas too wide to fit half a laptop screen
    columns = column_names(len(canvas[0]))
    size = settings['canvas']['pixel_size']

    markdown = "<p align=\"center\">\n"

    for row_idx, row in enumerate(canvas):
        row_name = str(row_idx + 1)

        for col_idx, colour in enumerate(row):
            pixel = columns[col_idx] + row_name
            markdown += "<a href=\"{}\"><img src=\"img/pixels/{}.svg\" width={} height={} alt=\"{}\" title=\"{}\"></a>".format(
                html.escape(create_paint_link(pixel)), colour, size, size, pixel, pixel)

        markdown += "<br>\n"

    return markdown + "</p>\n"
