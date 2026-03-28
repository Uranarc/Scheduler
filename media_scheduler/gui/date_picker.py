"""Calendar-style date picker dialog used by event and generation screens."""

import calendar
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk


class DatePickerDialog(tk.Toplevel):
    def __init__(self, parent, initial_date: date | None = None, title: str = "Select date"):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        initial = initial_date or date.today()
        self.result: str | None = None
        self.year_var = tk.IntVar(value=initial.year)
        self.month_var = tk.IntVar(value=initial.month)

        top = ttk.Frame(self)
        top.pack(fill='x', padx=8, pady=8)

        years = [str(y) for y in range(initial.year - 10, initial.year + 11)]
        ttk.Label(top, text='Year').pack(side='left')
        self.year_cb = ttk.Combobox(top, width=6, state='readonly', values=years, textvariable=self.year_var)
        self.year_cb.pack(side='left', padx=(4, 10))

        ttk.Label(top, text='Month').pack(side='left')
        months = [str(m) for m in range(1, 13)]
        self.month_cb = ttk.Combobox(top, width=4, state='readonly', values=months, textvariable=self.month_var)
        self.month_cb.pack(side='left', padx=4)

        self.days_frame = ttk.Frame(self)
        self.days_frame.pack(padx=8, pady=(0, 8))

        bottom = ttk.Frame(self)
        bottom.pack(fill='x', padx=8, pady=(0, 8))
        ttk.Button(bottom, text='Today', command=self._set_today).pack(side='left')
        ttk.Button(bottom, text='Cancel', command=self._cancel).pack(side='right')

        self.year_cb.bind('<<ComboboxSelected>>', lambda _e: self._render_days())
        self.month_cb.bind('<<ComboboxSelected>>', lambda _e: self._render_days())
        self.bind('<Escape>', lambda _e: self._cancel())

        self._render_days()
        self.wait_visibility()
        self.focus_set()

    def _render_days(self):
        for w in self.days_frame.winfo_children():
            w.destroy()

        for i, wd in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
            ttk.Label(self.days_frame, text=wd, width=4, anchor='center').grid(row=0, column=i, padx=1, pady=1)

        y = int(self.year_var.get())
        m = int(self.month_var.get())
        first_wd, ndays = calendar.monthrange(y, m)

        row = 1
        col = first_wd
        for d in range(1, ndays + 1):
            ttk.Button(
                self.days_frame,
                text=str(d),
                width=4,
                command=lambda day=d: self._pick(day)
            ).grid(row=row, column=col, padx=1, pady=1)
            col += 1
            if col > 6:
                col = 0
                row += 1

    def _pick(self, day: int):
        picked = date(int(self.year_var.get()), int(self.month_var.get()), int(day))
        self.result = picked.isoformat()
        self.destroy()

    def _set_today(self):
        self.result = date.today().isoformat()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def pick_date_dialog(parent, current_iso: str = '', title: str = 'Select date') -> str | None:
    initial = date.today()
    if current_iso:
        try:
            initial = datetime.strptime(current_iso, '%Y-%m-%d').date()
        except Exception:
            pass

    dlg = DatePickerDialog(parent, initial_date=initial, title=title)
    parent.wait_window(dlg)
    return dlg.result

