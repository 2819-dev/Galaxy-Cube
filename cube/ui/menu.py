"""Menus and simple screens (spec §9). Turn the knob to move, press to pick."""

BACK = "< Back"
CLOSE = "close"   # an action returns this to close all menus and go to the home screen


class Item:
    def __init__(self, label, action=None, submenu=None):
        self.label = label
        self.action = action      # async function, may return CLOSE
        self.submenu = submenu    # function returning (title, [Item, ...])


async def run_menu(app, title, build):
    """Show a menu. `build` returns the items, so labels can change (for example "Brightness: High")."""
    selected = 0
    while True:
        items = build()
        labels = [BACK] + [item.label for item in items]
        selected = min(selected, len(labels) - 1)
        app.screen.menu(title, labels, selected)
        event = await app.next_event()
        if event == "up":
            selected = max(0, selected - 1)
        elif event == "down":
            selected = min(len(labels) - 1, selected + 1)
        elif event == "press":
            if selected == 0:
                return None
            item = items[selected - 1]
            if item.submenu:
                sub_title, _ = item.submenu()
                result = await run_menu(app, sub_title, lambda: item.submenu()[1])
            else:
                result = await item.action()
            if result == CLOSE:
                return CLOSE


async def info(app, title, lines):
    """Show some text until the knob is pressed."""
    while True:
        footer = ["Press to go back"] if len(lines) < 5 else []
        app.screen.text(list(lines) + footer, title=title)
        if await app.next_event() == "press":
            return


async def confirm(app, question):
    """Yes/No question. Returns True for Yes."""
    selected = 0
    while True:
        app.screen.menu(question, ["No", "Yes"], selected)
        event = await app.next_event()
        if event in ("up", "down"):
            selected = 1 - selected
        elif event == "press":
            return selected == 1
