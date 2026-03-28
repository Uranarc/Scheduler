"""Main Tk root window and notebook tab assembly for the application."""

import tkinter as tk
from tkinter import ttk

from media_scheduler.gui.assignments_frame import AssignmentsFrame
from media_scheduler.gui.dashboard_frame import DashboardFrame
from media_scheduler.gui.events_frame import EventsFrame
from media_scheduler.gui.generate_frame import GenerateFrame
from media_scheduler.gui.members_frame import MembersFrame


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Media Scheduler')
        self.geometry('980x650')
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self._build()

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True)
        self.members_frame = MembersFrame(nb)
        self.events_frame = EventsFrame(nb)
        self.generate_frame = GenerateFrame(nb)
        self.assignments_frame = AssignmentsFrame(nb)
        self.dashboard_frame = DashboardFrame(nb)
        nb.add(self.members_frame, text='Members')
        nb.add(self.events_frame, text='Events')
        nb.add(self.generate_frame, text='Generate')
        nb.add(self.assignments_frame, text='Assignments')
        nb.add(self.dashboard_frame, text='Dashboard')

