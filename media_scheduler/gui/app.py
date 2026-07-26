"""Main Tk root window, top bar (with theme toggle), and notebook tab assembly."""

import tkinter as tk
from tkinter import ttk

from media_scheduler.gui import theme
from media_scheduler.gui.assignments_frame import AssignmentsFrame
from media_scheduler.gui.dashboard_frame import DashboardFrame
from media_scheduler.gui.events_frame import EventsFrame
from media_scheduler.gui.generate_frame import GenerateFrame
from media_scheduler.gui.members_frame import MembersFrame


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Media Scheduler')
        self.geometry('1120x720')
        self.minsize(920, 580)

        self.mode = theme.detect_system_mode()
        theme.apply_theme(self, self.mode)

        self._frames = []
        self._build()

    def _build(self):
        topbar = ttk.Frame(self, padding=(16, 12, 16, 8))
        topbar.pack(fill='x')

        ttk.Label(topbar, text='Media Scheduler', style='Title.TLabel').pack(side='left')
        ttk.Label(topbar, text='  gestão de equipa e escalas', style='Muted.TLabel').pack(side='left')

        self.theme_btn = ttk.Button(
            topbar, text=self._theme_label(), style='Toggle.TButton',
            command=self.toggle_theme, width=12,
        )
        self.theme_btn.pack(side='right')

        body = ttk.Frame(self, padding=(16, 0, 16, 16))
        body.pack(fill='both', expand=True)

        self.notebook = ttk.Notebook(body)
        self.notebook.pack(fill='both', expand=True)

        self.members_frame = MembersFrame(self.notebook)
        self.events_frame = EventsFrame(self.notebook)
        self.generate_frame = GenerateFrame(self.notebook)
        self.assignments_frame = AssignmentsFrame(self.notebook)
        self.dashboard_frame = DashboardFrame(self.notebook)

        self._frames = [
            self.members_frame, self.events_frame, self.generate_frame,
            self.assignments_frame, self.dashboard_frame,
        ]

        self.notebook.add(self.members_frame, text='  👥 Members  ')
        self.notebook.add(self.events_frame, text='  🗓 Events  ')
        self.notebook.add(self.generate_frame, text='  ⚙ Generate  ')
        self.notebook.add(self.assignments_frame, text='  📋 Assignments  ')
        self.notebook.add(self.dashboard_frame, text='  📊 Dashboard  ')

    def _theme_label(self):
        return '☀  Claro' if self.mode == 'dark' else '🌙  Escuro'

    def toggle_theme(self):
        self.mode = 'dark' if self.mode == 'light' else 'light'
        theme.apply_theme(self, self.mode)
        self.theme_btn.configure(text=self._theme_label())
        for frame in self._frames:
            refresh = getattr(frame, 'refresh_theme', None)
            if callable(refresh):
                refresh()
