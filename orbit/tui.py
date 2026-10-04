"""orbit TUI -- three panes: projects, file tree, preview.

The only module that imports anything third-party. If textual breaks, the
index and the CLI keep working.
"""

import os
import shlex
import subprocess
import time

from rich.markdown import Markdown
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from rich.style import Style
from textual import work
from textual.theme import Theme
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.events import MouseDown, MouseMove, MouseUp
from textual.widgets import (DataTable, Footer, Header, Input, Static, TabbedContent,
                             TabPane, TextArea, Tree)
from textual.widgets.text_area import TextAreaTheme

from . import config as C
from . import db as D
from . import jump
from . import sessions as S
from . import sideprojects as SP
from . import ladder as L

THEME_ORDER = list(C.THEMES) + list(C.BUILTIN)


def ago(ts):
    if not ts:
        return "never"
    d = int(time.time()) - int(ts)
    if d < 90:
        return "%ds" % d
    if d < 5400:
        return "%dm" % (d // 60)
    if d < 172800:
        return "%dh" % (d // 3600)
    return "%dd" % (d // 86400)


def human(n):
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return "%d%s" % (n, unit)
        n /= 1024.0
    return "%.0fT" % n


# TextArea ships 15 tree-sitter grammars; everything else renders unhighlighted.
LANGS = {
    "py": "python", "js": "javascript", "jsx": "javascript",
    "ts": "javascript", "tsx": "javascript", "mjs": "javascript",
    "cjs": "javascript", "json": "json", "jsonl": "json",
    "sh": "bash", "bash": "bash", "zsh": "bash", "fish": "bash",
    "yaml": "yaml", "yml": "yaml", "toml": "toml", "sql": "sql",
    "md": "markdown", "mdx": "markdown", "markdown": "markdown",
    "html": "html", "htm": "html", "xml": "xml", "plist": "xml",
    "css": "css", "scss": "css", "rs": "rust", "go": "go", "java": "java",
}

# ---------------------------------------------------------------- palettes
# All black-grounded. (name, bg, surface, panel, fg, primary, accent, warning,
# comment, string, keyword, number, function)
PALETTES = [
    ("void",   "#000000", "#000000", "#0d1117", "#c9d1d9", "#2f81f7", "#39d0d8",
     "#d29922", "#484f58", "#7ee787", "#ff7b72", "#79c0ff", "#d2a8ff"),
    ("ember",  "#000000", "#070504", "#170f0a", "#e6d5c3", "#ff8c42", "#ffb627",
     "#ff5964", "#5c4a3d", "#c3d47c", "#ff8c42", "#ffd166", "#f4a261"),
    ("matrix", "#000000", "#000000", "#0a1a0a", "#b8f5b8", "#00ff41", "#39ff14",
     "#ffd700", "#2d4a2d", "#7fff7f", "#00ff41", "#adff2f", "#00e5ff"),
    ("ice",    "#000000", "#03060a", "#0a1420", "#cfe3f5", "#5aa9e6", "#7fdbff",
     "#ffb703", "#3d5570", "#9ae6b4", "#7fdbff", "#a5b4fc", "#c4b5fd"),
    ("mono",   "#000000", "#000000", "#141414", "#d0d0d0", "#8a8a8a", "#ffffff",
     "#bfbfbf", "#4a4a4a", "#a8a8a8", "#e8e8e8", "#c0c0c0", "#f0f0f0"),
]


def build_themes():
    """One Textual theme plus one matching code theme per palette.

    The built-in code themes (monokai, dracula) all carry their own grey
    background, which would sit as a visible rectangle on a black app.
    """
    app_themes, code_themes = {}, {}
    for (name, bg, surface, panel, fg, primary, accent, warning,
         comment, string, keyword, number, function) in PALETTES:
        app_themes[name] = Theme(
            name=name, dark=True,
            background=bg, surface=surface, panel=panel, foreground=fg,
            primary=primary, secondary=accent, accent=accent,
            warning=warning, error="#ff6b6b", success=string,
            variables={
                "block-cursor-background": accent,
                "block-cursor-foreground": bg,
                "border": panel,
                "scrollbar": panel,
                "scrollbar-hover": accent,
                "scrollbar-active": accent,
                "footer-key-foreground": accent,
                "input-selection-background": accent + " 35%",
            })
        code_themes[name] = TextAreaTheme(
            name=name,
            base_style=Style(color=fg, bgcolor=bg),
            gutter_style=Style(color=comment, bgcolor=bg),
            cursor_style=Style(color=bg, bgcolor=accent),
            cursor_line_gutter_style=Style(color=accent, bgcolor=bg),
            bracket_matching_style=Style(bgcolor=panel, bold=True),
            selection_style=Style(bgcolor=panel),
            syntax_styles={
                "comment": Style(color=comment, italic=True),
                "string": Style(color=string),
                "string.documentation": Style(color=comment, italic=True),
                "keyword": Style(color=keyword, bold=True),
                "keyword.function": Style(color=keyword, bold=True),
                "keyword.operator": Style(color=keyword),
                "conditional": Style(color=keyword, bold=True),
                "include": Style(color=keyword),
                "exception": Style(color=keyword),
                "number": Style(color=number),
                "float": Style(color=number),
                "boolean": Style(color=number),
                "constant.builtin": Style(color=number),
                "function": Style(color=function, bold=True),
                "function.call": Style(color=function),
                "method": Style(color=function, bold=True),
                "method.call": Style(color=function),
                "class": Style(color=accent, bold=True),
                "type": Style(color=accent),
                "variable": Style(color=fg),
                "operator": Style(color=primary),
                "punctuation.bracket": Style(color=comment),
                "punctuation.delimiter": Style(color=comment),
                "json.label": Style(color=accent, bold=True),
                "heading": Style(color=accent, bold=True),
                "link": Style(color=primary, underline=True),
                "inline_code": Style(color=string),
                "tag": Style(color=keyword),
                # the remaining token types tree-sitter emits; without these
                # they fall back to monokai's palette and a stray orange
                # shows up inside an otherwise green or amber theme
                "keyword.return": Style(color=keyword, bold=True),
                "repeat": Style(color=keyword, bold=True),
                "type.builtin": Style(color=accent),
                "type.class": Style(color=accent, bold=True),
                "variable.builtin": Style(color=primary, italic=True),
                "punctuation.special": Style(color=primary),
                "heading.marker": Style(color=comment),
                "list.marker": Style(color=primary),
                "link.label": Style(color=primary),
                "link.uri": Style(color=string, underline=True),
                "json.null": Style(color=number),
                "css.property": Style(color=accent),
                "yaml.field": Style(color=accent, bold=True),
                "toml.type": Style(color=accent),
                "toml.datetime": Style(color=number),
                "regex.operator": Style(color=keyword),
                "regex.punctuation.bracket": Style(color=comment),
                "html.end_tag_error": Style(color="#ff6b6b", underline=True),
                "bold": Style(bold=True),
                "italic": Style(italic=True),
                "strikethrough": Style(strike=True),
            })
    return app_themes, code_themes


ASK_MODEL = "sonnet"
ASK_TIMEOUT = 90          # seconds; a hung call must not freeze the pane
ASK_MAX_CHARS = 12000     # whole-file fallback cap

MIN_PANE = 14          # columns; below this a tree is unreadable
MAX_PANE = 90
MIN_PREVIEW = 24       # the preview must never be pushed off-screen


def language_for(path):
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return LANGS.get(ext)


def build_prompt(host, repo, path, code, lo=None, hi=None):
    """What gets sent to sonnet. Explicit about provenance so the answer can
    talk about the real file rather than a nameless snippet."""
    where = "%s:%s/%s" % (host, repo, path)
    if lo is not None:
        where += " lines %d-%d" % (lo, hi)
    return (
        "Explain this code. Say what it does, why it exists, and anything "
        "surprising or risky about it. Be concrete and brief -- a short "
        "paragraph plus a few bullets. No preamble.\n\n"
        "From %s:\n\n```\n%s\n```" % (where, code))


def clamp_pane(width, other_w, screen_w):
    """Pane width that keeps both trees usable and the preview on-screen.
    Pure arithmetic, so it is testable without a terminal."""
    room = screen_w - other_w - 2 - MIN_PREVIEW        # 2 = the two dividers
    return max(MIN_PANE, min(MAX_PANE, room, int(width)))


class Divider(Static):
    """A one-column grab handle that resizes the pane to its left.

    Textual 8 ships no splitter, so this is the whole implementation: capture
    the mouse on press, translate x into a width, clamp, done.
    """

    def __init__(self, target):
        super().__init__("\u2502", classes="divider")
        self.target = target          # id of the pane this divider resizes
        self._drag = False

    def on_mouse_down(self, ev: MouseDown):
        self._drag = True
        self.capture_mouse()
        self.add_class("dragging")

    def on_mouse_up(self, ev: MouseUp):
        self._drag = False
        self.release_mouse()
        self.remove_class("dragging")
        self.app.save_widths()

    def on_mouse_move(self, ev: MouseMove):
        if not self._drag:
            return
        pane = self.app.query_one("#" + self.target)
        # screen_x is absolute; the pane starts at its own region.x
        self.app.set_pane_width(self.target, ev.screen_x - pane.region.x)


class SearchScreen(ModalScreen):
    """Names and contents in one list. Enter jumps the trees to the hit."""

    BINDINGS = [Binding("escape", "dismiss_none", "close")]

    def __init__(self, db, content=False):
        super().__init__()
        self.db = db
        self.content = content
        self._last = ""

    def compose(self):
        yield Input(placeholder="search contents…" if self.content
                    else "search file names…", id="q")
        yield DataTable(id="hits", cursor_type="row")

    def on_mount(self):
        t = self.query_one("#hits", DataTable)
        t.add_columns("host", "repo", "path", "match")
        self.query_one("#q", Input).focus()

    def action_dismiss_none(self):
        self.dismiss(None)

    def on_input_changed(self, ev):
        self.set_timer(0.15, self._search)

    def _search(self):
        q = self.query_one("#q", Input).value.strip()
        if q == self._last:
            return
        self._last = q
        t = self.query_one("#hits", DataTable)
        t.clear()
        self.rows = []
        if len(q) < 2:
            return
        try:
            hits = (D.find_content(self.db, q, limit=60) if self.content
                    else D.find_names(self.db, q, limit=60))
        except Exception as e:                       # bad FTS5 syntax, mid-type
            t.add_row("", "", "", Text(str(e)[:60], style="red"))
            return
        for r in hits:
            # Text, not str: a str cell is read as markup, and FTS5 marks the
            # match as [word], which markup would swallow
            snip = Text(" ".join(r["snip"].split())[:80] if self.content else "")
            snip.highlight_regex(r"\[[^\]]*\]", "bold yellow")
            t.add_row(r["host"], Text(r["repo"][:22]), Text(r["path"][-52:]), snip)
            self.rows.append(r)

    def on_input_submitted(self):
        self.query_one("#hits", DataTable).focus()

    def on_data_table_row_selected(self, ev):
        if 0 <= ev.cursor_row < len(self.rows):
            self.dismiss(self.rows[ev.cursor_row])


class Prompt(ModalScreen):
    """One line of input. Enter returns it, esc returns None."""

    BINDINGS = [Binding("escape", "dismiss_none", "cancel")]

    def __init__(self, label, value=""):
        super().__init__()
        self.label, self.value = label, value

    def compose(self):
        yield Static(self.label, id="plabel")
        yield Input(self.value, id="pinput")

    def on_mount(self):
        self.query_one("#pinput", Input).focus()

    def action_dismiss_none(self):
        self.dismiss(None)

    def on_input_submitted(self, ev):
        self.dismiss(ev.value.strip())


COLS = 3          # tiles per row on the sessions wall
TILE_LINES = 12   # screen lines a tile shows (its height minus the border)


class Tile(Static, can_focus=True):
    """One live Claude session: the bottom of its real Terminal screen,
    refreshed every 2 s. Enter goes there, m types a reply into it."""

    BINDINGS = [
        Binding("enter", "go", "go there"),
        Binding("m", "reply", "message it"),
        Binding("d", "changes", "changes"),
        Binding("left", "move(-1)", show=False),
        Binding("right", "move(1)", show=False),
        Binding("up", "move(-%d)" % COLS, show=False),
        Binding("down", "move(%d)" % COLS, show=False),
    ]

    def __init__(self, sid):
        super().__init__("", id="tile-" + sid, classes="tile")
        self.sid = sid

    def on_focus(self):
        self.app.tile_focused(self.sid)

    def action_go(self):
        self.app.jump_selected()

    def action_reply(self):
        self.app.reply_to(self.sid)

    def action_changes(self):
        self.app.toggle_changes()

    def action_move(self, delta):
        self.app.move_tile(self, delta)


class CardTable(DataTable):
    """Keys only mean something while a card list has focus."""

    BINDINGS = [
        Binding("n", "card('new')", "new"),
        Binding("e", "card('edit')", "next action"),
        Binding("k", "card('keep')", "keep suggestion"),
        Binding("l", "card('link')", "link folder"),
        Binding("p", "card('park')", "park/unpark"),
        Binding("z", "card('shelf')", "show parked"),
        Binding("enter", "card('open')", "open"),
    ]

    def action_card(self, what):
        self.app.card_action(self, what)


class Editor(TextArea):
    """Your code. A multi-line paste marks the stage "pasted" (not blocked)."""

    def _on_paste(self, event):
        # Textual also runs TextArea._on_paste (it walks the MRO), which inserts it
        if "\n" in event.text:
            self.app.ladder_pasted()


class LadderPane(Vertical):
    """Ctrl keys reach this even while you type; letters never do."""

    BINDINGS = [
        Binding("ctrl+s", "ladder('run')", "save + check"),
        Binding("ctrl+g", "ladder('hint')", "hint"),
        Binding("ctrl+r", "ladder('review')", "review"),
        Binding("ctrl+n", "ladder('next')", "next stage"),
    ]

    def action_ladder(self, what):
        getattr(self.app, "ladder_" + what)()


STATE_GLYPH = {  # (glyph, style) per inbox kind or pulse state
    "needs_you": ("●", "bold magenta"), "finished": ("✓", "bold green"),
    "busy": ("◐", "yellow"), "error": ("✗", "red"), "idle": ("·", "dim"),
}


def diff_text(d):
    t = Text()
    for line in d.splitlines():
        style = ("bold" if line.startswith(("---", "+++")) else
                 "cyan" if line.startswith("@@") else
                 "green" if line.startswith("+") else
                 "red" if line.startswith("-") else "")
        t.append(line + "\n", style=style)
    return t


class Orbit(App):
    CSS = """
    Screen { layers: base; background: $background; }
    Header { background: $panel; color: $accent; }
    Footer { background: $panel; }
    #projects { width: 34; }
    #files    { width: 44; }
    #previewbox { width: 1fr; min-width: 10; }
    #codehead { height: 1; padding: 0 1; background: $panel; }
    #code { height: 1fr; border: none; padding: 0 1; }
    #answerbox {
        height: auto; max-height: 60%; display: none;
        border-top: solid $accent; background: $surface;
    }
    #answerbox.open { display: block; }
    #answerhead { height: 1; padding: 0 1; background: $panel; color: $accent; }
    #answer { padding: 0 1; height: auto; }
    .divider {
        width: 1; height: 100%;
        color: $panel-lighten-2; background: $surface;
    }
    .divider:hover  { color: $accent; background: $panel; }
    .divider.dragging { color: $accent; background: $accent 20%; }
    #status { height: 1; padding: 0 1; background: $panel; }
    SearchScreen { align: center middle; }
    SearchScreen > Input { width: 90%; margin: 1 0 0 0; }
    SearchScreen > DataTable { width: 90%; height: 24; }
    Prompt { align: center middle; }
    Prompt > Static { width: 80%; padding: 0 1; background: $panel; color: $accent; }
    Prompt > Input { width: 80%; }
    #tabs, #tabs > ContentSwitcher, TabPane { height: 1fr; padding: 0; }
    #wallbox { width: 1fr; }
    #wall { grid-size: 3; grid-rows: 14; grid-gutter: 0 1; height: auto; }
    .tile { height: 14; padding: 0 1; border: round $panel-lighten-2; }
    .tile.done { border: round green; }
    .tile.needs { border: round magenta; }
    .tile:focus { border: heavy $accent; }
    .tile.done:focus { border: heavy green; }
    .tile.needs:focus { border: heavy magenta; }
    #sessright { width: 1fr; border-left: solid $panel; display: none; }
    #sessright.open { display: block; }
    #changed { height: auto; max-height: 12; }
    #diffhead, #parkedhead { height: 1; padding: 0 1; background: $panel; }
    #diff { padding: 0 1; }
    #cards { height: auto; max-height: 60%; }
    #parked { height: auto; display: none; }
    #parked.open { display: block; }
    #lessonbox { width: 1fr; padding: 0 1; border-right: solid $panel; }
    #climb { padding: 1 0; color: $text-muted; }
    #workbox { width: 1fr; }
    #codehead2 { height: 1; padding: 0 1; background: $panel; }
    #kv { height: 1fr; border: none; }
    #resultbox { height: auto; max-height: 45%; border-top: solid $panel; }
    #result { padding: 0 1; }
    #result.pass { color: $success; }
    #result.fail { color: $error; }
    """

    BINDINGS = [
        Binding("f", "flatten", "flat/themes"),
        Binding("left_square_bracket", "narrow", "narrower"),
        Binding("right_square_bracket", "widen", "wider"),
        Binding("backslash", "reset_widths", "reset panes"),
        Binding("slash", "search_names", "find name"),
        Binding("s", "search_content", "find text"),
        Binding("c", "claude", "claude here"),
        Binding("t", "shell", "shell here"),
        Binding("y", "copy", "copy path"),
        Binding("o", "reveal", "reveal"),
        Binding("a", "ask", "explain (sonnet)"),
        Binding("A", "escalate", "open in claude"),
        Binding("escape", "close_answer", "close answer", show=False),
        Binding("g", "gaps", "gh gaps"),
        Binding("R", "refresh", "refresh"),
        Binding("T", "cycle_theme", "theme"),
        Binding("i", "inbox", "next waiting"),
        Binding("n", "new_session", "new claude"),
        Binding("1", "tab('t-files')", "files", show=False),
        Binding("2", "tab('t-sessions')", "sessions", show=False),
        Binding("3", "tab('t-side')", "side projects", show=False),
        Binding("4", "tab('t-ladder')", "ladder", show=False),
        Binding("q", "quit", "quit"),
    ]

    def __init__(self):
        super().__init__()
        self.db = D.connect()
        self.flat = False
        self.want = {"projects": 34, "files": 44}   # intent, before clamping
        self.repo = None          # current repo row
        self.sub = ""             # current subdirectory within it
        self.file_id = None
        self.file_path = ""       # repo-relative path of the previewed file
        self.last_ask = None      # (prompt, lo, hi) for escalation
        self._app_themes, self._code_themes = build_themes()
        self._theme_names = [n for n, *_ in PALETTES]
        self._ask_timer = None
        self._ask_t0 = 0.0
        self.rows = []            # live sessions, newest poll
        self._kinds = None        # sid -> inbox kind at the last poll; None = first poll
        self._sess_sel = None     # sid of the selected tile
        self.tiles = {}           # sid -> Tile, first-seen order: tiles never reshuffle
        self.screens = {}         # tty -> visible Terminal text, newest read
        self._screens_read = False
        self._expect_cwd = None   # a session orbit just started; its tile gets focus
        self._changed = []
        self.cards = SP.load()
        try:
            self.my_tty = os.ttyname(0)
        except OSError:
            self.my_tty = None

    # ------------------------------------------------------------ layout

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static("", id="status")
        with TabbedContent(id="tabs", initial="t-files"):
            with TabPane("1 files", id="t-files"):
                with Horizontal():
                    yield Tree("projects", id="projects")
                    yield Divider("projects")
                    yield Tree("files", id="files")
                    yield Divider("files")
                    with Vertical(id="previewbox"):
                        yield Static("", id="codehead")
                        yield TextArea("", read_only=True, show_line_numbers=True,
                                       soft_wrap=False, id="code")
                        with Vertical(id="answerbox"):
                            yield Static("", id="answerhead")
                            with VerticalScroll():
                                yield Static("", id="answer")
            with TabPane("2 sessions", id="t-sessions"):
                with Horizontal():
                    with VerticalScroll(id="wallbox"):
                        yield Grid(id="wall")
                    with Vertical(id="sessright"):
                        yield DataTable(id="changed", cursor_type="row")
                        yield Static("", id="diffhead")
                        with VerticalScroll():
                            yield Static("", id="diff")
            with TabPane("3 side projects", id="t-side"):
                yield CardTable(id="cards", cursor_type="row")
                yield Static("", id="parkedhead")
                yield CardTable(id="parked", cursor_type="row")
            with TabPane("4 ladder", id="t-ladder"):
                with LadderPane():
                    with Horizontal():
                        with VerticalScroll(id="lessonbox"):
                            yield Static("", id="climb")
                            yield Static("", id="lesson")
                        with Vertical(id="workbox"):
                            yield Static("", id="codehead2")
                            yield Editor.code_editor("", language="python", id="kv")
                            with VerticalScroll(id="resultbox"):
                                yield Static("", id="result")
        yield Footer()

    def on_mount(self):
        self.title = "orbit"
        ta = self.query_one("#code", TextArea)
        for name, th in self._app_themes.items():
            self.register_theme(th)
            ta.register_theme(self._code_themes[name])
        self.apply_theme(D.get_meta(self.db, "theme", self._theme_names[0]))
        self.restore_widths()
        self.load_projects()
        self.refresh_status()
        self.set_interval(30, self.refresh_status)
        self.query_one("#changed", DataTable).add_columns("changed by Claude", "")
        for t in ("#cards", "#parked"):
            self.query_one(t, DataTable).add_columns(
                "", "project", "next action", "touched", "folder")
        self.poll_sessions()
        self.set_interval(2, self.poll_sessions)
        self.ladder_load()

    # ------------------------------------------------------------- theme

    def apply_theme(self, name):
        if name not in self._app_themes:
            name = self._theme_names[0]
        self.theme = name
        self.query_one("#code", TextArea).theme = name
        D.set_meta(self.db, "theme", name)
        self.db.commit()
        return name

    def action_cycle_theme(self):
        cur = self.theme if self.theme in self._theme_names else self._theme_names[0]
        nxt = self._theme_names[(self._theme_names.index(cur) + 1)
                                % len(self._theme_names)]
        self.apply_theme(nxt)
        self.notify("theme: %s" % nxt, timeout=2)

    # -------------------------------------------------------- pane widths

    def set_pane_width(self, pane_id, width, remember=True):
        """Clamp for display; remember what was asked for.

        Storing the clamped value instead would mean that opening orbit once
        in a small terminal permanently shrinks the layout, with no way back
        when the window grows again.
        """
        if remember:
            self.want[pane_id] = max(MIN_PANE, min(MAX_PANE, int(width)))
        other = "files" if pane_id == "projects" else "projects"
        shown = clamp_pane(width, self.want.get(other, 0),
                           self.size.width or 160)
        self.query_one("#" + pane_id).styles.width = shown
        return shown

    def apply_widths(self):
        """Re-clamp both panes against the current terminal size."""
        for pane in ("projects", "files"):
            self.set_pane_width(pane, self.want[pane], remember=False)

    def on_resize(self, _=None):
        """Intent is untouched, so growing the window restores the widths you
        actually chose."""
        self.apply_widths()

    def restore_widths(self):
        for pane, default in (("projects", 34), ("files", 44)):
            self.want[pane] = int(D.get_meta(self.db, "w_" + pane, default))
        self.apply_widths()

    def save_widths(self):
        for pane in ("projects", "files"):
            D.set_meta(self.db, "w_" + pane, self.want[pane])
        self.db.commit()

    def _focused_pane(self):
        """Which pane the resize keys act on. The preview is elastic, so
        focusing it means you want the pane feeding it to move."""
        node = self.focused
        while node is not None:
            if getattr(node, "id", None) in ("projects", "files"):
                return node.id
            node = node.parent
        return "files"

    def _nudge(self, delta):
        pane = self._focused_pane()
        self.set_pane_width(pane, self.want[pane] + delta)
        self.save_widths()

    def action_widen(self):
        self._nudge(4)

    def action_narrow(self):
        self._nudge(-4)

    def action_reset_widths(self):
        self.set_pane_width("projects", 34)
        self.set_pane_width("files", 44)
        self.save_widths()

    # ------------------------------------------------------------ status

    def refresh_status(self):
        c = D.counts(self.db)
        bits = ["%d repos" % c["repos"], "%d files" % c["files"]]
        for host in C.ALL_HOSTS:
            err = D.get_meta(self.db, host + "_error", "")
            bits.append("%s %s%s" % (host, ago(D.get_meta(self.db, host + "_as_of")),
                                     " ERR" if err else ""))
        if C.GITHUB:
            bits.append("gh " + ago(D.get_meta(self.db, "gh_as_of")))
        self.query_one("#status", Static).update(
            Text(" · ".join(bits), style="dim"))

    # ---------------------------------------------------------- projects

    def load_projects(self):
        tree = self.query_one("#projects", Tree)
        tree.clear()
        tree.root.expand()
        rows = D.repos(self.db, flat=True)      # always newest-first
        if self.flat:
            tree.root.label = "all · last touched"
            for r in rows:
                tree.root.add_leaf(self._repo_label(r, show_theme=True),
                                   data=("repo", r))
        else:
            tree.root.label = "projects"
            groups = {}
            for r in rows:
                groups.setdefault(r["theme"], []).append(r)
            order = ([t for t in THEME_ORDER if t in groups]
                     + sorted(k for k in groups if k not in THEME_ORDER))
            for theme in order:
                node = tree.root.add("%s  (%d)" % (theme, len(groups[theme])),
                                     data=("theme", theme))
                if theme not in ("THIRD-PARTY",):
                    node.expand()
                for r in groups[theme]:
                    node.add_leaf(self._repo_label(r), data=("repo", r))

    def _repo_label(self, r, show_theme=False):
        t = Text()
        if show_theme:
            t.append("%-11s " % r["theme"][:11], style="dim")
        t.append(r["name"][:22])
        t.append("  %s" % ago(r["mtime"]), style="dim cyan")
        t.append("  %s" % r["host"][:8], style="dim")
        if not r["remote"]:
            t.append(" *", style="yellow")
        return t

    # ------------------------------------------------------------- files

    def load_files(self, repo_row):
        self.repo = repo_row
        self.sub = ""
        tree = self.query_one("#files", Tree)
        tree.clear()
        tree.root.label = repo_row["name"]
        tree.root.data = ("dir", "")
        self._expand_dir(tree.root, "")
        tree.root.expand()

    def _expand_dir(self, node, prefix):
        dirs, files = D.children(self.db, self.repo["id"], prefix)
        for d in dirs:
            n = node.add(Text(d + "/"), data=("dir", prefix + d + "/"))  # [id]/ is a real name
            n.data = ("dir", prefix + d + "/")
        for f in files:
            t = Text(f["path"][len(prefix):])
            t.append("  %s" % human(f["size"]), style="dim")
            if not f["body_mtime"]:
                t.append(" ·", style="dim yellow")
            node.add_leaf(t, data=("file", f["id"], f["path"], f["size"]))

    def on_tree_node_expanded(self, ev):
        data = ev.node.data
        if not data or data[0] != "dir" or ev.node.children:
            return
        if self.repo is None:
            return
        self._expand_dir(ev.node, data[1])

    def on_tree_node_highlighted(self, ev):
        data = ev.node.data
        if not data:
            return
        if data[0] == "repo":
            self.load_files(data[1])
        elif data[0] == "dir":
            self.sub = data[1].rstrip("/")
            self.file_id = None
        elif data[0] == "file":
            self.sub = os.path.dirname(data[2])
            self.file_id = data[1]
            self.show_preview(data[1], data[2], data[3])

    # ----------------------------------------------------------- preview

    def _set_code(self, text, language=None):
        ta = self.query_one("#code", TextArea)
        ta.language = language          # set first: avoids re-highlighting twice
        ta.text = text
        ta.move_cursor((0, 0))

    def _set_codehead(self, label, note="", note_style="dim"):
        """Name the file and say plainly that it cannot be edited. A TextArea
        looks editable; without this the pane invites a worry it does not
        deserve."""
        t = Text()
        t.append(label, style="bold")
        if note:
            t.append("  " + note, style=note_style)
        self.query_one("#codehead", Static).update(t)

    def show_preview(self, file_id, path, size):
        self.file_path = path
        self._set_codehead(
            "%s:%s/%s" % (self.repo["host"], self.repo["name"], path),
            "%s · READ-ONLY (orbit never writes files)" % human(size))
        text = D.body_of(self.db, file_id)
        if text is None:
            self._set_codehead("%s" % path, "no body indexed")
            self._set_code("%s\n\n%s - no body indexed\n"
                           "(binary, over 400 KB, or not pulled yet)"
                           % (path, human(size)), None)
            return
        self._set_code(text, language_for(path))

    # ------------------------------------------------------------ actions

    def action_flatten(self):
        self.flat = not self.flat
        self.load_projects()

    def action_search_names(self):
        self.push_screen(SearchScreen(self.db, content=False), self._jump_to)

    def action_search_content(self):
        self.push_screen(SearchScreen(self.db, content=True), self._jump_to)

    def _jump_to(self, hit):
        if not hit:
            return
        rows = self.db.execute(
            "SELECT * FROM repo WHERE host=? AND path=?",
            (hit["host"], hit["repo_path"])).fetchone()
        if rows is None:
            return
        self.load_files(rows)
        self.file_id = hit["id"]
        row = self.db.execute("SELECT size FROM file WHERE id=?",
                              (hit["id"],)).fetchone()
        self.show_preview(hit["id"], hit["path"], row["size"] if row else 0)
        self.sub = os.path.dirname(hit["path"])
        self.notify("%s/%s" % (hit["repo"], hit["path"]), timeout=4)

    def _target(self):
        if self.repo is None:
            self.notify("select a project first", severity="warning")
            return None
        return self.repo["host"], self.repo["path"], self.sub

    def action_claude(self):
        t = self._target()
        if not t:
            return
        if t[0] != C.LOCAL:
            with self.suspend():
                jump.run(jump.claude(*t))
        else:                        # new window: orbit keeps polling, jump works
            jump.claude_window(jump.abs_dir(*t))

    def action_shell(self):
        t = self._target()
        if t:
            with self.suspend():
                jump.run(jump.shell(*t))

    def action_copy(self):
        t = self._target()
        if not t:
            return
        p = jump.abs_dir(*t)
        if t[0] != C.LOCAL:
            p = jump.remote_path(t[0], p)
        jump.copy_path(p)
        self.notify("copied " + p, timeout=3)

    def action_reveal(self):
        t = self._target()
        if not t:
            return
        if jump.reveal(*t):
            self.notify("revealed in Finder", timeout=2)
        else:
            self.notify("path on another Mac — copied instead", timeout=3)

    def on_key(self, ev):
        """Explain the silence when someone types into the preview."""
        if (self.focused is not None
                and getattr(self.focused, "id", None) == "code"
                and len(getattr(ev, "character", "") or "") == 1
                and (ev.character.isprintable())):
            self.notify("preview is read-only — press A to edit in a Claude "
                        "session", timeout=3)

    # --------------------------------------------------------------- ask

    def _selection(self):
        """(code, lo, hi) -- the highlighted lines, else the whole file.

        Returns line numbers 1-based so the prompt and the escalation can
        name the same range the user can see in the gutter.
        """
        ta = self.query_one("#code", TextArea)
        sel = ta.selected_text
        if sel.strip():
            (r1, _), (r2, _) = sorted([ta.selection.start, ta.selection.end])
            return sel, r1 + 1, r2 + 1
        text = ta.text
        if len(text) > ASK_MAX_CHARS:
            text = text[:ASK_MAX_CHARS] + "\n... (truncated)"
        return text, None, None

    def _show_answer(self, head, body, style=""):
        if body:                       # a real answer ends the waiting tick
            self._stop_waiting()
        self.query_one("#answerbox").add_class("open")
        self.query_one("#answerhead", Static).update(head)
        w = self.query_one("#answer", Static)
        w.update(Markdown(body) if style == "md" else Text(body, style=style))

    def action_close_answer(self):
        self._stop_waiting()
        self.query_one("#answerbox").remove_class("open")

    def action_ask(self):
        if not self.file_id or not self.file_path:
            self.notify("select a file first", severity="warning")
            return
        code, lo, hi = self._selection()
        if not code.strip():
            self.notify("nothing to explain", severity="warning")
            return
        prompt = build_prompt(self.repo["host"], self.repo["name"],
                              self.file_path, code, lo, hi)
        self.last_ask = (prompt, lo, hi)
        span = ("lines %d-%d" % (lo, hi)) if lo else "whole file"
        self._start_waiting(span)
        self._run_ask(prompt, span)

    def _start_waiting(self, span):
        """A headless call takes ~20-30s. Without a moving number it reads as
        a hang, so tick the header once a second until the answer lands."""
        self._ask_t0 = time.time()
        self._show_answer("asking %s about %s ..." % (ASK_MODEL, span), "", "dim")
        self._stop_waiting()
        self._ask_timer = self.set_interval(
            1.0, lambda: self.query_one("#answerhead", Static).update(
                Text("asking %s about %s ...  %ds"
                     % (ASK_MODEL, span, int(time.time() - self._ask_t0)),
                     style="dim")))

    def _stop_waiting(self):
        if self._ask_timer is not None:
            self._ask_timer.stop()
            self._app_themes, self._code_themes = build_themes()
        self._theme_names = [n for n, *_ in PALETTES]
        self._ask_timer = None

    @work(thread=True, exclusive=True)
    def _run_ask(self, prompt, span):
        """Headless sonnet call on a worker thread.

        This is the one feature that needs the network. It fails fast and
        says so rather than hanging the pane -- everything else in orbit
        still works with the Wi-Fi off.
        """
        try:
            p = subprocess.run(
                ["claude", "-p", "--model", ASK_MODEL, prompt],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=ASK_TIMEOUT)
            out = (p.stdout or b"").decode("utf-8", "replace").strip()
            err = (p.stderr or b"").decode("utf-8", "replace").strip()
            if p.returncode != 0 or not out:
                raise RuntimeError(err[:300] or "claude exited %d" % p.returncode)
        except subprocess.TimeoutExpired:
            self.call_from_thread(
                self._show_answer, "timed out after %ds" % ASK_TIMEOUT,
                "No answer. Everything else in orbit works offline; this "
                "does not.", "red")
            return
        except Exception as e:                       # noqa: BLE001
            self.call_from_thread(
                self._show_answer, "ask failed",
                "%s\n\nOffline? This is the only feature that needs the "
                "network." % e, "red")
            return
        self.call_from_thread(
            self._show_answer,
            "%s - %s   (A to continue in a real session, esc to close)"
            % (ASK_MODEL, span), out, "md")

    def action_escalate(self):
        """Hand the whole thing to a real Claude session on the right host.

        Sends a short pointer, not the code: the session runs where the file
        lives and can read it itself, which keeps the ssh quoting sane.
        """
        if self.repo is None:
            self.notify("select a project first", severity="warning")
            return
        host, repo_path = self.repo["host"], self.repo["path"]
        if self.file_path and self.last_ask:
            _, lo, hi = self.last_ask
            span = (" lines %d-%d" % (lo, hi)) if lo else ""
            seed = ("Explain %s%s -- what it does, why it exists, and anything "
                    "risky about it." % (self.file_path, span))
        elif self.file_path:
            seed = "Walk me through %s." % self.file_path
        else:
            seed = ""
        d = jump.abs_dir(host, repo_path, self.sub)
        if host == C.LOCAL:
            jump.claude_window(d, seed)
            return
        with self.suspend():
            inner = "exec claude " + shlex.quote(seed) if seed else "exec claude"
            subprocess.call(jump.remote_cmd(host, d, inner))

    def action_gaps(self):
        self.file_path = ""
        self._set_codehead("github gaps", "read-only report")
        missing, never = D.gaps(self.db)
        t = Text()
        t.append("ON GITHUB, NOT CLONED (%d)\n\n" % len(missing), style="bold")
        for g in missing:
            t.append("  %-34s %-8s %s\n"
                     % (g["name"][:34], "private" if g["private"] else "public",
                        (g["pushed_at"] or "")[:10]))
        t.append("\nLOCAL, NEVER PUSHED (%d)\n\n" % len(never), style="bold")
        for r in never:
            t.append("  %-34s %-9s %s\n" % (r["name"][:34], r["host"],
                                            ago(r["mtime"])))
        self._set_code(str(t), None)

    def action_refresh(self):
        self.notify("refreshing in background…", timeout=3)
        subprocess.Popen(
            [os.sys.executable, "-m", "orbit", "refresh"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ----------------------------------------------------------- sessions

    def action_tab(self, tab):
        self.query_one("#tabs", TabbedContent).active = tab
        if tab == "t-sessions":
            tile = self.tiles.get(self._sess_sel) or next(iter(self.tiles.values()), None)
            if tile:
                tile.focus()
        elif tab == "t-side":
            self.query_one("#cards").focus()
        elif tab == "t-ladder":
            self.query_one("#kv").focus()

    def poll_sessions(self):
        """Every 2s: re-read pulse, redraw, ping on anything newly waiting."""
        rows = S.load()
        kinds = {r["session_id"]: S.kind(r) for r in rows}
        fresh = self._kinds is not None and any(
            k and self._kinds.get(sid) != k for sid, k in kinds.items())
        self._track_cards(rows, kinds)
        self._kinds, self.rows = kinds, rows
        self._render_tiles()
        if self.query_one("#tabs", TabbedContent).active == "t-sessions":
            self._read_screens()
        self._render_cards()
        n = len(S.inbox(rows))
        self.sub_title = ("%d waiting on you · i jumps" % n) if n else "nothing waiting"
        if fresh:
            self._ping_unless_looking()

    @work(thread=True, exclusive=True, group="ping")
    def _ping_unless_looking(self):
        if not self.my_tty or jump.frontmost_tty() != self.my_tty:
            jump.ping()

    def _wall_rows(self):
        return [r for r in self.rows if r["tty"] != self.my_tty]

    def on_tabbed_content_tab_activated(self, ev):
        if ev.pane.id == "t-sessions":
            self._read_screens()

    @work(thread=True, exclusive=True, group="screens")
    def _read_screens(self):
        """One osascript for every tile (~0.7 s), off the UI thread."""
        sc = S.parse_screens(jump.screens([r["tty"] for r in self._wall_rows()]))
        self.call_from_thread(self._got_screens, sc)

    def _got_screens(self, sc):
        self.screens, self._screens_read = sc, True
        self._render_tiles()

    def _render_tiles(self):
        """Mount new sessions, drop dead ones, repaint the rest in place.
        Never clear-and-rebuild: that would steal focus every 2 s."""
        wall = self.query_one("#wall")
        live = {r["session_id"]: r for r in self._wall_rows()}
        for sid in [x for x in self.tiles if x not in live]:
            self.tiles.pop(sid).remove()
        for sid, r in live.items():
            if sid not in self.tiles:
                self.tiles[sid] = Tile(sid)
                wall.mount(self.tiles[sid])
                if self._expect_cwd and r.get("cwd") == self._expect_cwd:
                    self._expect_cwd = None
                    self._sess_sel = sid
                    self.call_after_refresh(self.tiles[sid].focus)
            self._paint(self.tiles[sid], r)

    def _paint(self, tile, r):
        k = S.kind(r) or r.get("state", "idle")
        glyph = STATE_GLYPH.get(k, STATE_GLYPH["idle"])[0]
        wait = (" · " + ago(r["waiting_since"])) if S.kind(r) else ""
        tile.border_title = "%s %s%s" % (glyph, r.get("project", "?")[:22], wait)
        tile.border_subtitle = (r.get("title") or "")[:40]
        tile.set_class(k == "needs_you", "needs")
        tile.set_class(k == "finished", "done")
        text = self.screens.get(r["tty"])
        if text is None:
            tile.update(Text("no Terminal.app tab on %s (kitty or tmux?)" % r["tty"]
                             if self._screens_read else "reading screen…", style="dim"))
            return
        # crop, never wrap: a wrapped line would push the newest output out the bottom
        w = tile.content_size.width or 60
        lines = [l[:w] for l in S.trim_footer(text)[-TILE_LINES:]]
        tile.update(Text("\n".join(lines), no_wrap=True, overflow="crop"))

    def _selected_session(self):
        sid = getattr(self.focused, "sid", None) or self._sess_sel
        return next((r for r in self.rows if r["session_id"] == sid), None)

    def tile_focused(self, sid):
        self._sess_sel = sid
        if self.query_one("#sessright").has_class("open"):
            r = self._selected_session()
            if r:
                self._show_changed(r)

    def toggle_changes(self):
        box = self.query_one("#sessright")
        box.toggle_class("open")
        r = self._selected_session()
        if box.has_class("open") and r:
            self._show_changed(r)

    def move_tile(self, tile, delta):
        order = list(self.tiles.values())
        j = order.index(tile) + delta
        if 0 <= j < len(order):
            order[j].focus()

    def reply_to(self, sid):
        r = next((x for x in self.rows if x["session_id"] == sid), None)
        if r is None:
            return
        if not S.can_reply(r, self.screens.get(r["tty"])):
            self.notify("%s needs you or shows a menu — Enter goes there"
                        % r.get("project", "?"), severity="warning", timeout=4)
            return

        def typed(text):
            if text:
                self._send(sid, text)
        self.push_screen(Prompt("message → %s   (one line · Enter sends · esc cancels)"
                                % r.get("project", "?")), typed)

    @work(thread=True, group="send")
    def _send(self, sid, text):
        """Re-read the screen right before typing: a permission prompt may have
        appeared while the message was being written."""
        r = next((x for x in self.rows if x["session_id"] == sid), None)
        if r is None:
            self.call_from_thread(self.notify, "session is gone — not sent", severity="warning")
            return
        fresh = S.parse_screens(jump.screens([r["tty"]])).get(r["tty"], "")
        if not S.can_reply(r, fresh):
            self.call_from_thread(self.notify, "not sent: %s now needs you — Enter goes there"
                                  % r.get("project", "?"), severity="warning", timeout=5)
            return
        ok = jump.send(r["tty"], text)
        self.call_from_thread(self.notify, ("sent to %s" if ok else "could not reach %s")
                              % r.get("project", "?"), timeout=3)

    def action_new_session(self):
        """Start Claude without leaving orbit: folder, optional first message,
        then a background Terminal window whose tile shows up on the wall."""
        home = os.path.expanduser("~")
        here = "~"
        if self.repo is not None and self.repo["host"] == C.LOCAL:
            here = jump.abs_dir(self.repo["host"], self.repo["path"], self.sub).replace(home, "~", 1)

        def ask_msg(d):
            def got_msg(msg):
                if msg is not None:
                    self._spawn(d, msg)
            self.push_screen(Prompt("first message for Claude in %s   (optional · Enter starts it)"
                                    % d.replace(home, "~", 1)), got_msg)

        def got_dir(v):
            if not v:
                return
            # a bare name means ~/name, not "relative to wherever orbit was started"
            d = os.path.abspath(os.path.join(home, os.path.expanduser(v)))
            if os.path.isdir(d):
                ask_msg(d)
                return
            if os.path.exists(d):
                self.notify("%s is a file, not a folder" % d, severity="warning")
                return

            def create(ok):
                if ok is None:
                    return
                try:
                    os.makedirs(d)
                except OSError as e:
                    self.notify("could not create %s: %s" % (d, e), severity="error")
                    return
                ask_msg(d)
            self.push_screen(Prompt("%s does not exist yet   (Enter creates it · esc cancels)"
                                    % d.replace(home, "~", 1)), create)
        self.push_screen(Prompt("new Claude session in folder   (this Mac only)", here), got_dir)

    @work(thread=True, group="spawn")
    def _spawn(self, d, msg):
        self._expect_cwd = d
        jump.claude_window(d, msg, background=True)
        if self.my_tty:
            time.sleep(0.4)                  # let Terminal open the window first
            jump.focus_tty(self.my_tty)      # orbit stays in front
        self.call_from_thread(self.action_tab, "t-sessions")
        self.call_from_thread(self.notify, "starting Claude in %s — its tile appears in a few seconds"
                              % os.path.basename(d) or d, timeout=4)

    def on_data_table_row_highlighted(self, ev):
        if ev.data_table.id == "changed" and self._changed and 0 <= ev.cursor_row < len(self._changed):
            self._show_diff(self._changed[ev.cursor_row])

    def _show_changed(self, r):
        t = self.query_one("#changed", DataTable)
        t.clear()
        self._changed = S.changed_files(r.get("transcript", "")) if r.get("transcript") else []
        home = os.path.expanduser("~")
        for p in self._changed:
            short = p.replace(home, "~", 1)
            t.add_row(short[-60:], "new" if not S.backup_of(r["session_id"], p) else "")
        self.query_one("#diffhead", Static).update(Text(
            "%d files changed · since Claude's first edit, your own edits included"
            % len(self._changed) if self._changed else
            "no Edit/Write changes yet (changes made through Bash don't show)", style="dim"))
        self.query_one("#diff", Static).update("")
        if self._changed:
            self._show_diff(self._changed[0])

    def _show_diff(self, path):
        d = S.diff(self._sess_sel, path)
        self.query_one("#diff", Static).update(diff_text(d) if d else Text(
            "no difference from before Claude's first edit", style="dim"))

    def _jump(self, r):
        if r["tty"] == self.my_tty:
            self.notify("that session runs in this window", timeout=3)
        elif not jump.focus_tty(r["tty"]):
            self.notify("no Terminal.app tab on %s (kitty or tmux?)" % r["tty"],
                        severity="warning")

    def action_inbox(self):
        """Select the longest-waiting session in the sessions tab; never leaves
        orbit. Pressed again, it steps to the next one. Enter goes there."""
        ids = [r["session_id"] for r in S.inbox(self.rows)]
        if not ids:
            self.notify("nothing is waiting on you", timeout=2)
            return
        on_tab = self.query_one("#tabs", TabbedContent).active == "t-sessions"
        cur = self._sess_sel
        nxt = ids[(ids.index(cur) + 1) % len(ids)] if on_tab and cur in ids else ids[0]
        self._sess_sel = nxt
        self.action_tab("t-sessions")
        self.notify("%d/%d waiting · Enter goes there · i for next"
                    % (ids.index(nxt) + 1, len(ids)), timeout=3)

    def jump_selected(self):
        r = self._selected_session()
        if r:
            self._jump(r)

    # ------------------------------------------------------ side projects

    def _track_cards(self, rows, kinds):
        """Live sessions keep a card's 'touched' fresh; a session in its folder
        that just finished leaves its recap as a suggested next action."""
        dirty = False
        for c in self.cards:
            for r in rows:
                if not SP.owns(c, r.get("cwd")):
                    continue
                c["touched"] = max(c["touched"], r.get("last_event_at", 0))
                just_done = (self._kinds is not None and kinds.get(r["session_id"]) == "finished"
                             and self._kinds.get(r["session_id"]) != "finished")
                tip = r.get("summary") or r.get("title") or ""
                if just_done and tip and tip != c.get("suggest"):
                    c["suggest"], dirty = tip, True
        if dirty:
            SP.save(self.cards)

    def _card_touched(self, c):
        """Newest of: card activity, the folder itself, the index's view of it."""
        ts = c["touched"]
        f = c.get("folder")
        if f:
            try:
                ts = max(ts, int(os.path.getmtime(f)))
            except OSError:
                pass
            for r in D.repos(self.db, flat=True):
                if r["host"] == C.LOCAL and jump.abs_dir(C.LOCAL, r["path"]) == f.rstrip("/"):
                    ts = max(ts, int(r["mtime"] or 0))
        return ts

    def _render_cards(self):
        home = os.path.expanduser("~")
        for tid, active in (("#cards", True), ("#parked", False)):
            t = self.query_one(tid, DataTable)
            keep = t.cursor_row
            t.clear()
            for c in sorted((c for c in self.cards if c["active"] == active),
                            key=lambda c: -self._card_touched(c)):
                live = [r for r in self.rows if SP.owns(c, r.get("cwd"))]
                k = next((S.kind(r) for r in live if S.kind(r)), None)
                dot = (Text(*STATE_GLYPH[k]) if k else
                       Text("◐", style="yellow") if live else Text(" "))
                nxt = Text(c["next"] or "—", style="" if c["next"] else "dim")
                if c.get("suggest") and c["suggest"] != c["next"]:
                    nxt.append("   k keeps: " + c["suggest"][:50], style="dim italic cyan")
                t.add_row(dot, c["name"][:22], nxt, ago(self._card_touched(c)),
                          (c["folder"] or "idea, no folder").replace(home, "~", 1)[-30:],
                          key=c["id"])
            if t.row_count:
                t.move_cursor(row=min(keep, t.row_count - 1))
        parked = sum(not c["active"] for c in self.cards)
        shelf = self.query_one("#parked").has_class("open")
        self.query_one("#parkedhead", Static).update(Text(
            "parked (%d) · z %s" % (parked, "hides" if shelf else "shows"), style="dim"))

    def _card_at(self, table):
        if not table.row_count:
            return None
        cid = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key.value
        return next((c for c in self.cards if c["id"] == cid), None)

    def card_action(self, table, what):
        c = self._card_at(table)
        done = lambda: (SP.save(self.cards), self._render_cards())
        if what == "new":
            def made(name):
                if name:
                    SP.add(self.cards, name)
                    done()
            self.push_screen(Prompt("new side project — a name is enough"), made)
        elif what == "shelf":
            self.query_one("#parked").toggle_class("open")
            self._render_cards()
        elif c is None:
            self.notify("no card here — n makes one", timeout=2)
        elif what == "edit":
            def edited(v):
                if v is not None:
                    c["next"] = v
                    done()
            self.push_screen(Prompt("next action for %s" % c["name"], c["next"]), edited)
        elif what == "keep":
            if c.get("suggest"):
                c["next"] = c["suggest"]
                done()
        elif what == "link":
            def linked(v):
                if not v:
                    return
                p = os.path.abspath(os.path.expanduser(v))
                if not os.path.isdir(p):
                    self.notify("no such folder: " + p, severity="warning")
                    return
                c["folder"] = p
                done()
            self.push_screen(Prompt("folder for %s" % c["name"], c["folder"] or "~/"), linked)
        elif what == "park":
            if c["active"]:
                SP.park(self.cards, c["id"])
            else:
                before = {x["id"] for x in self.cards if x["active"]}
                SP.activate(self.cards, c["id"])
                bumped = [x["name"] for x in self.cards
                          if x["id"] in before and not x["active"]]
                if bumped:
                    self.notify("parked %s to make room" % bumped[0], timeout=3)
            done()
        elif what == "open":
            live = [r for r in self.rows if SP.owns(c, r.get("cwd"))]
            if live:
                self._jump(S.inbox(live)[0] if S.inbox(live) else live[0])
            elif c["folder"]:
                jump.claude_window(c["folder"])
            else:
                self.notify("idea only — l links a folder first", timeout=3)

    # ------------------------------------------------------------- ladder
    # self.unit is the unit on screen; finishing one opens the next.

    def ladder_load(self, unit=None):
        self._hint = 0
        self.lp = L.load()
        self.UNIT = unit or L.current_unit(self.lp)
        self.stage = L.current(self.lp, self.UNIT)
        path = L.code_path(self.UNIT)
        if not os.path.exists(path):
            os.makedirs(L.WORK, exist_ok=True)
            with open(path, "w") as f:
                f.write("# %s.py -- every line typed by you.\n\n" % self.UNIT)
        ed = self.query_one("#kv", TextArea)
        with open(path) as f:
            ed.load_text(f.read())
        ed.move_cursor(ed.document.end)
        self._ladder_show()

    def _ladder_show(self, result=None, ok=None):
        n, md, _ = L.stages(self.UNIT)[self.stage - 1]
        with open(md) as f:
            self._lesson = f.read()
        self.query_one("#lesson", Static).update(Markdown(self._lesson))
        days = self.lp.get("days", [])
        self.query_one("#climb", Static).update(Text(
            "UNIT %d · %s   🔥 %d-day streak\n\n%s" % (
                self._unit_no() + 1, L.ORDER[self._unit_no()][1],
                L.streak(days), L.ladder_text(self.lp, self.UNIT))))
        self.query_one("#codehead2", Static).update(Text(
            " ~/ladder/%s.py   stage %d/%d   ctrl+s check · ctrl+g hint · ctrl+r review · "
            "ctrl+n next · esc leave editor" % (self.UNIT, n, len(L.stages(self.UNIT))),
            style="bold"))
        r = self.query_one("#result", Static)
        r.set_class(ok is True, "pass")
        r.set_class(ok is False, "fail")
        r.update(Text(result if result is not None else
                      "ctrl+s runs the check for this stage. Stuck? ctrl+g gives a small "
                      "hint; press it again for a bigger one."))

    def on_text_area_changed(self, event):
        if event.text_area.id == "kv":            # autosave: nothing you type is lost
            with open(L.code_path(self.UNIT), "w") as f:
                f.write(event.text_area.text)

    def ladder_pasted(self):
        L.mark_pasted(self.lp, self.UNIT, self.stage)
        L.save(self.lp)
        self.notify("pasted: this stage will count as 'pasted', not 'unaided'",
                    severity="warning")

    def ladder_run(self):
        self.query_one("#result", Static).update(Text("checking ...", style="dim"))
        self._ladder_check(self.query_one("#kv", TextArea).text, self.stage)

    @work(thread=True, exclusive=True, group="ladder")
    def _ladder_check(self, code, n):
        ok, msg = L.run(code, L.stages(self.UNIT)[n - 1][2], self.UNIT)
        self.call_from_thread(self._ladder_checked, n, ok, msg)

    def _ladder_checked(self, n, ok, msg):
        self._last_result = msg
        if not ok:
            self._ladder_show(msg, False)
            return
        grade = L.mark_passed(self.lp, self.UNIT, n)
        L.save(self.lp)
        last = n == len(L.stages(self.UNIT))
        more = self._unit_no() + 1 < len(L.ORDER)
        self._ladder_show("✓ stage %d passed (%s). %s" % (
            n, grade,
            "ctrl+r for an interviewer's review, ctrl+n for the next requirement." if not last else
            "UNIT DONE. ctrl+n opens unit %d: %s." % (self._unit_no() + 2, L.ORDER[self._unit_no() + 1][1])
            if more else "Every written unit is done. Tell Claude: write the %s unit." % L.NEXT_UP),
            True)

    def _unit_no(self):
        return [u for u, _ in L.ORDER].index(self.UNIT)

    def ladder_next(self):
        if str(self.stage) not in self.lp.get(self.UNIT, {}).get("passed", {}):
            self.notify("pass this stage first (ctrl+s)", severity="warning")
            return
        if self.stage == len(L.stages(self.UNIT)):
            if self._unit_no() + 1 < len(L.ORDER):
                self.ladder_load(L.ORDER[self._unit_no() + 1][0])
                self.query_one("#lessonbox").scroll_home(animate=False)
            return
        if self.stage < len(L.stages(self.UNIT)):
            self.stage += 1
            self._hint = 0
            self._last_result = ""
            self._ladder_show()
            self.query_one("#lessonbox").scroll_home(animate=False)

    def ladder_hint(self):
        """One press = one step more help. 1-3 ask Claude, 4+ reveal a line."""
        self._hint += 1
        code = self.query_one("#kv", TextArea).text
        r = self.query_one("#result", Static)
        if self._hint in L.HINT_LEVELS:
            name = L.HINT_LEVELS[self._hint][0]
            r.update(Text("hint %d/4 (%s) ..." % (self._hint, name), style="dim"))
            self._ladder_hint(self._hint, L.hint_prompt(
                self._hint, self._lesson, self.UNIT, code,
                getattr(self, "_last_result", "")))
            return
        with open(L.solution_path(self.UNIT, self.stage)) as f:
            miss = L.next_missing_line(f.read(), code)
        if miss is None:
            r.update(Text("hint 4 (reveal): you already have every line of the reference "
                          "answer. The bug is in the order or a detail: ctrl+s and read "
                          "the message, or ctrl+r for a review."))
            return
        L.unit_state(self.lp, self.UNIT)["shown"].append(self.stage)
        L.save(self.lp)
        no, line = miss
        r.update(Text("hint 4 (reveal) — the next line you are missing, around line %d of "
                      "the answer. Type it yourself; this stage now counts as 'shown'.\n\n"
                      "    %s" % (no, line)))

    @work(thread=True, exclusive=True, group="ladder-review")
    def _ladder_hint(self, level, prompt):
        name = L.HINT_LEVELS[level][0]
        try:
            p = subprocess.run(
                ["claude", "-p", "--safe-mode", "--tools", "", "--model", ASK_MODEL, prompt],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=ASK_TIMEOUT)
            out = (p.stdout or b"").decode("utf-8", "replace").strip()
            if p.returncode != 0 or not out:
                out = "hint failed: " + ((p.stderr or b"").decode("utf-8", "replace")[:300]
                                         or "claude exited %d" % p.returncode)
            elif L.leaks_code(out, blanks_ok=(level == 3)):
                out = "that hint gave too much away, so it was withheld. ctrl+g again."
                self._hint = level - 1
        except subprocess.TimeoutExpired:
            out = "hint timed out after %ds (offline?)" % ASK_TIMEOUT
            self._hint = level - 1
        more = "ctrl+g again for a bigger hint." if level < 4 else ""
        self.call_from_thread(lambda: self.query_one("#result", Static).update(
            Text("hint %d/4 (%s):\n%s\n\n%s" % (level, name, out.replace("```python", "").replace("```", ""), more))))

    def ladder_review(self):
        code = self.query_one("#kv", TextArea).text
        self.query_one("#result", Static).update(
            Text("the interviewer is reading your code ...", style="dim"))
        self._ladder_review(L.review_prompt(
            self._lesson, self.UNIT, code,
            getattr(self, "_last_result", "") or "not run yet"))

    @work(thread=True, exclusive=True, group="ladder-review")
    def _ladder_review(self, prompt):
        try:
            p = subprocess.run(
                ["claude", "-p", "--safe-mode", "--tools", "", "--model", ASK_MODEL, prompt],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=ASK_TIMEOUT)
            out = (p.stdout or b"").decode("utf-8", "replace").strip()
            if p.returncode != 0 or not out:
                out = "review failed: " + ((p.stderr or b"").decode("utf-8", "replace")[:300]
                                           or "claude exited %d" % p.returncode)
            elif L.leaks_code(out):
                out = "review withheld: the interviewer wrote code. ctrl+r to ask again."
        except subprocess.TimeoutExpired:
            out = "review timed out after %ds (offline?)" % ASK_TIMEOUT
        self.call_from_thread(
            lambda: self.query_one("#result", Static).update(Text("interviewer:\n" + out)))


def run_tui():
    Orbit().run()
    return 0

