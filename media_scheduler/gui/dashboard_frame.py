"""Dashboard tab with monthly per-member assignment and load summary metrics."""

from datetime import date
import tkinter as tk
from tkinter import ttk

from media_scheduler.db.assignments import get_load_summary


class DashboardFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=8)

        today = date.today()

        ttk.Label(top, text='Month').pack(side='left')
        self.month_cb = ttk.Combobox(top, values=[str(i) for i in range(1, 13)], state='readonly', width=5)
        self.month_cb.set(str(today.month))
        self.month_cb.pack(side='left', padx=(4, 10))

        ttk.Label(top, text='Year').pack(side='left')
        year_values = [str(y) for y in range(today.year - 5, today.year + 6)]
        self.year_cb = ttk.Combobox(top, values=year_values, state='readonly', width=7)
        self.year_cb.set(str(today.year))
        self.year_cb.pack(side='left', padx=(4, 10))

        ttk.Button(top, text='Refresh', command=self.refresh).pack(side='left')

        cols = (
            'name', 'slide_count', 'luzes_count', 'live_count', 'total_days',
            'load_stress', 'manual_stress', 'max_days', 'days_remaining'
        )
        self.tree = ttk.Treeview(self, columns=cols, show='headings')

        spec = [
            ('name', 180),
            ('slide_count', 95),
            ('luzes_count', 95),
            ('live_count', 90),
            ('total_days', 90),
            ('load_stress', 90),
            ('manual_stress', 95),
            ('max_days', 80),
            ('days_remaining', 110),
        ]
        for h, w in spec:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=w, anchor='center')
        self.tree.column('name', anchor='w')

        self.tree.tag_configure('over_limit', foreground='red')

        self.tree.pack(fill='both', expand=True, padx=10, pady=(0, 8))

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        try:
            month = int(self.month_cb.get())
            year = int(self.year_cb.get())
        except ValueError:
            return

        rows = get_load_summary(year, month)
        for r in rows:
            max_days = r['max_days']
            if max_days is None:
                max_days_text = '—'
                days_remaining_text = '—'
            else:
                max_days_text = str(max_days)
                rem = int(r['days_remaining'] or 0)
                days_remaining_text = str(rem if rem > 0 else 0)

            tags = ('over_limit',) if r.get('over_limit') else ()

            self.tree.insert('', 'end', values=(
                r['name'],
                r['slide_count'],
                r['luzes_count'],
                r['live_count'],
                r['total_days'],
                r['load_stress'],
                r['manual_stress'],
                max_days_text,
                days_remaining_text,
            ), tags=tags)

