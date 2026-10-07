"""Numbered, searchable terminal choices shared by the live application."""
from rich.text import Text

from . import terminal


class Back(Exception):
    """Return to the containing menu without dispatching anything."""


def choose(console, title, items, label, read, *, explanation='', multiple=False,
           details=None, page_size=8, actions=None):
    if not items:
        raise ValueError('No available '+title.lower()+'.')
    labels = [str(label(item)) for item in items]
    filtered, page = list(range(len(items))), 0
    while True:
        console.print('\n'+terminal.clean(title), style='bold cyan')
        if explanation:
            console.print(terminal.clean(explanation), style='dim')
        pages = max(1, (len(filtered)+page_size-1)//page_size)
        page = min(page, pages-1)
        visible = filtered[page*page_size:(page+1)*page_size]
        for index, original in enumerate(visible, 1):
            lines = labels[original].splitlines()
            heading = Text(f'  {index}  ', style='cyan')
            heading.append(terminal.clean(lines[0]), style='bold')
            console.print(heading)
            for line in lines[1:]:
                console.print('     '+terminal.clean(line), style='dim')
        if not visible:
            console.print('No matching options. Enter / to clear the search.')
        if len(items)>page_size:
            console.print(f'Page {page+1}/{pages} · {len(filtered)} options', style='dim')
        controls = 'q Back'
        if len(items)>page_size:
            controls += ' · n next · p previous · /text search · / clear'
        if details:
            controls += ' · d NUMBER Details / files'
        for key, (caption, _) in (actions or {}).items():
            controls += f' · {key} {caption}'
        console.print(controls, style='dim')
        answer = read('Selection'+(' (comma-separated)' if multiple else '')+' [1]: ').strip()
        if answer.lower() in (actions or {}):
            actions[answer.lower()][1]()
            continue
        if answer.lower() in ('q', 'b', 'back'):
            raise Back
        if answer.lower() in ('n', 'p'):
            page = (page+(1 if answer.lower()=='n' else -1)) % pages
            continue
        if answer.startswith('/'):
            query = answer[1:].casefold()
            filtered = [i for i, value in enumerate(labels) if query in value.casefold()]
            page = 0
            continue
        if details and answer.lower().startswith('d '):
            try:
                index = int(answer[2:])-1
                if not 0 <= index < len(visible):
                    raise ValueError
                details(items[visible[index]])
            except ValueError:
                console.print('Use d followed by a number on this page.')
            continue
        try:
            indices = [int(part.strip())-1 for part in (answer or '1').split(',')]
            if (not multiple and len(indices)!=1 or len(set(indices))!=len(indices)
                    or not all(0<=i<len(visible) for i in indices)):
                raise ValueError
            values = [items[visible[i]] for i in indices]
            return values if multiple else values[0]
        except ValueError:
            console.print('Enter '+('distinct numbers' if multiple else 'one number')+' from this page.')
