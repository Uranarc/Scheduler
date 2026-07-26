"""Central theme definitions and ttk style application for light/dark modes.

Every visual constant (colors, fonts, paddings) used across the app's frames
lives here so switching modes or retouching the palette only ever means
editing this one file.
"""

import tkinter.font as tkfont
from tkinter import ttk

try:
    import darkdetect
except ImportError:  # pragma: no cover - optional dependency
    darkdetect = None


LIGHT = {
    'bg': '#f5f6f8',
    'surface': '#ffffff',
    'fg': '#1b1f23',
    'muted_fg': '#5f6672',
    'accent': '#3b6fe0',
    'accent_active': '#2f5cc0',
    'accent_fg': '#ffffff',
    'danger': '#d33d3d',
    'danger_active': '#b83232',
    'danger_fg': '#ffffff',
    'border': '#d8dce1',
    'select_bg': '#e3edff',
    'row_alt': '#f1f3f6',
    'header_bg': '#ebeef2',
    'entry_bg': '#ffffff',
    'disabled_fg': '#a7adb5',
}

DARK = {
    'bg': '#1c1f26',
    'surface': '#252932',
    'fg': '#e7e9ec',
    'muted_fg': '#9aa1ac',
    'accent': '#5b93ff',
    'accent_active': '#78a5ff',
    'accent_fg': '#0b1220',
    'danger': '#ff6b6b',
    'danger_active': '#ff8585',
    'danger_fg': '#1a0000',
    'border': '#3a3f4b',
    'select_bg': '#32415c',
    'row_alt': '#292d37',
    'header_bg': '#2b303b',
    'entry_bg': '#2b303b',
    'disabled_fg': '#5f6672',
}

_current_mode = 'light'


def detect_system_mode() -> str:
    """Best-effort OS theme detection; falls back to 'light' if unknown."""
    if darkdetect is not None:
        try:
            detected = darkdetect.theme()
            if detected:
                return detected.lower()
        except Exception:
            pass
    return 'light'


def colors_for(mode: str) -> dict:
    return DARK if mode == 'dark' else LIGHT


def current_colors() -> dict:
    return colors_for(_current_mode)


def get_current_mode() -> str:
    return _current_mode


def _pick_font_family() -> str:
    available = set(tkfont.families())
    for candidate in ('Segoe UI', 'SF Pro Text', 'Helvetica Neue', 'Helvetica', 'Arial'):
        if candidate in available:
            return candidate
    return 'TkDefaultFont'


def fonts() -> dict:
    family = _pick_font_family()
    return {
        'base': (family, 10),
        'bold': (family, 10, 'bold'),
        'title': (family, 15, 'bold'),
        'mono': ('Consolas' if 'Consolas' in set(tkfont.families()) else family, 10),
    }


def configure_zebra(tree, extra_tags=None):
    """(Re)configure alternating-row tags on a Treeview using current colors."""
    c = current_colors()
    tree.tag_configure('evenrow', background=c['surface'], foreground=c['fg'])
    tree.tag_configure('oddrow', background=c['row_alt'], foreground=c['fg'])
    if extra_tags:
        for tag, kwargs in extra_tags.items():
            tree.tag_configure(tag, **kwargs)


def row_tag(index: int) -> str:
    return 'evenrow' if index % 2 == 0 else 'oddrow'


def apply_theme(root, mode: str) -> dict:
    """Configure every ttk style for the given mode and return its palette."""
    global _current_mode
    _current_mode = mode

    c = colors_for(mode)
    f = fonts()
    base_font, bold_font, title_font = f['base'], f['bold'], f['title']

    style = ttk.Style(root)
    style.theme_use('clam')

    root.configure(bg=c['bg'])

    style.configure('.', background=c['bg'], foreground=c['fg'], font=base_font)
    style.configure('TFrame', background=c['bg'])
    style.configure('Surface.TFrame', background=c['surface'])

    style.configure('TLabel', background=c['bg'], foreground=c['fg'], font=base_font)
    style.configure('Muted.TLabel', background=c['bg'], foreground=c['muted_fg'], font=base_font)
    style.configure('Title.TLabel', background=c['bg'], foreground=c['fg'], font=title_font)
    style.configure('Heading.TLabel', background=c['bg'], foreground=c['fg'], font=bold_font)

    style.configure(
        'TLabelframe', background=c['bg'], foreground=c['fg'],
        bordercolor=c['border'], relief='solid', borderwidth=1,
    )
    style.configure('TLabelframe.Label', background=c['bg'], foreground=c['muted_fg'], font=bold_font)

    style.configure(
        'TButton', background=c['surface'], foreground=c['fg'],
        bordercolor=c['border'], focuscolor=c['accent'],
        padding=(10, 6), font=base_font, relief='flat',
    )
    style.map(
        'TButton',
        background=[('active', c['header_bg']), ('disabled', c['bg'])],
        foreground=[('disabled', c['disabled_fg'])],
    )

    style.configure(
        'Accent.TButton', background=c['accent'], foreground=c['accent_fg'],
        bordercolor=c['accent'], padding=(10, 6), font=bold_font, relief='flat',
    )
    style.map(
        'Accent.TButton',
        background=[('active', c['accent_active']), ('disabled', c['border'])],
        foreground=[('disabled', c['disabled_fg'])],
    )

    style.configure(
        'Danger.TButton', background=c['surface'], foreground=c['danger'],
        bordercolor=c['danger'], padding=(10, 6), font=base_font, relief='flat',
    )
    style.map(
        'Danger.TButton',
        background=[('active', c['danger']), ('disabled', c['bg'])],
        foreground=[('active', c['danger_fg']), ('disabled', c['disabled_fg'])],
    )

    style.configure(
        'Toggle.TButton', background=c['bg'], foreground=c['fg'],
        bordercolor=c['border'], padding=(6, 4), font=base_font, relief='flat',
    )
    style.map('Toggle.TButton', background=[('active', c['header_bg'])])

    style.configure(
        'TEntry', fieldbackground=c['entry_bg'], foreground=c['fg'],
        bordercolor=c['border'], insertcolor=c['fg'], padding=5,
    )
    style.map(
        'TEntry',
        fieldbackground=[('disabled', c['bg'])],
        bordercolor=[('focus', c['accent'])],
    )

    style.configure(
        'TCombobox', fieldbackground=c['entry_bg'], background=c['surface'],
        foreground=c['fg'], arrowcolor=c['muted_fg'], bordercolor=c['border'], padding=5,
    )
    style.map(
        'TCombobox',
        fieldbackground=[('readonly', c['entry_bg'])],
        foreground=[('disabled', c['disabled_fg'])],
        bordercolor=[('focus', c['accent'])],
    )
    root.option_add('*TCombobox*Listbox.background', c['surface'])
    root.option_add('*TCombobox*Listbox.foreground', c['fg'])
    root.option_add('*TCombobox*Listbox.selectBackground', c['select_bg'])
    root.option_add('*TCombobox*Listbox.selectForeground', c['fg'])
    root.option_add('*TCombobox*Listbox.font', base_font)

    style.configure(
        'TNotebook', background=c['bg'], bordercolor=c['border'], tabmargins=(4, 6, 4, 0),
    )
    style.configure(
        'TNotebook.Tab', background=c['header_bg'], foreground=c['muted_fg'],
        padding=(16, 9), font=base_font,
    )
    style.map(
        'TNotebook.Tab',
        background=[('selected', c['surface'])],
        foreground=[('selected', c['fg'])],
        expand=[('selected', (1, 1, 1, 0))],
    )

    style.configure(
        'Treeview', background=c['surface'], fieldbackground=c['surface'],
        foreground=c['fg'], bordercolor=c['border'], rowheight=26,
        font=base_font, borderwidth=0,
    )
    style.configure(
        'Treeview.Heading', background=c['header_bg'], foreground=c['muted_fg'],
        font=bold_font, relief='flat', padding=(6, 6),
    )
    style.map('Treeview.Heading', background=[('active', c['header_bg'])])
    style.map(
        'Treeview',
        background=[('selected', c['select_bg'])],
        foreground=[('selected', c['fg'])],
    )
    style.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])

    style.configure('TScrollbar', background=c['header_bg'], troughcolor=c['bg'],
                     bordercolor=c['border'], arrowcolor=c['muted_fg'])
    style.configure('Vertical.TScrollbar', background=c['header_bg'])
    style.configure('Horizontal.TScrollbar', background=c['header_bg'])

    style.configure('TCheckbutton', background=c['bg'], foreground=c['fg'], font=base_font)
    style.configure('TRadiobutton', background=c['bg'], foreground=c['fg'], font=base_font)
    style.configure('TSeparator', background=c['border'])

    return c
