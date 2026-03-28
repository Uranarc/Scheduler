"""Events management tab for manual event CRUD and fixed-event generation."""

from datetime import date, datetime
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from media_scheduler.db.events import (
    add_event_db,
    delete_all_events_db,
    delete_event_db,
    generate_fixed_events_for_month,
    list_events_db,
)
from media_scheduler.gui.date_picker import pick_date_dialog
from media_scheduler.utils.helpers import _safe_int


class EventsFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        frm = ttk.Frame(self)
        frm.pack(fill='x', padx=10, pady=8)

        ttk.Label(frm, text='Name').grid(row=0, column=0)
        self.name_e = ttk.Entry(frm, width=30)
        self.name_e.grid(row=0, column=1)

        ttk.Label(frm, text='Date yyyy-mm-dd').grid(row=0, column=2)
        self.date_e = ttk.Entry(frm, width=12)
        self.date_e.grid(row=0, column=3)
        ttk.Button(frm, text='Pick', command=self.pick_event_date).grid(row=0, column=4, padx=(4, 8))

        ttk.Label(frm, text='Importance').grid(row=0, column=5)
        self.imp_e = ttk.Entry(frm, width=5)
        self.imp_e.grid(row=0, column=6)

        ttk.Button(frm, text='Add event', command=self.add_event).grid(row=0, column=7, padx=6)
        ttk.Button(frm, text='Generate fixed events for month', command=self.generate_fixed_events_dialog).grid(row=0, column=8, padx=6)

        self.tree = ttk.Treeview(self, columns=('id', 'name', 'date', 'importance'), show='headings')
        for h, w in [('id', 40), ('name', 420), ('date', 120), ('importance', 80)]:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=w)
        self.tree.pack(fill='both', expand=True, padx=10, pady=6)

        btns = ttk.Frame(self)
        btns.pack(fill='x', padx=10)
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left', padx=4)
        ttk.Button(btns, text='Delete selected', command=self.delete_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Delete all', command=self.delete_all).pack(side='left', padx=4)

        self.refresh()

    def add_event(self):
        name = self.name_e.get().strip()
        date_s = self.date_e.get().strip()

        try:
            datetime.strptime(date_s, '%Y-%m-%d')
        except Exception:
            messagebox.showerror('Error', 'Date must be yyyy-mm-dd')
            return

        try:
            imp = _safe_int(self.imp_e.get(), 1)
        except ValueError:
            messagebox.showerror('Error', 'Importance must be an integer')
            return

        add_event_db(name, date_s, imp)
        self.name_e.delete(0, 'end')
        self.date_e.delete(0, 'end')
        self.imp_e.delete(0, 'end')
        self.refresh()

    def pick_event_date(self):
        chosen = pick_date_dialog(self, self.date_e.get().strip(), title='Select event date')
        if chosen:
            self.date_e.delete(0, 'end')
            self.date_e.insert(0, chosen)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in list_events_db():
            self.tree.insert('', 'end', values=(r['id'], r['name'], r['date'], r['importance']))

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        if messagebox.askyesno('Confirm', f'Delete event {vals[1]} on {vals[2]}?'):
            delete_event_db(vals[0])
            self.refresh()

    def delete_all(self):
        if messagebox.askyesno('Confirm', 'Delete ALL events? This also removes related assignments and coordinators.'):
            delete_all_events_db()
            self.refresh()

    def generate_fixed_events_dialog(self):
        today = date.today()
        m = simpledialog.askinteger('Month', 'Month (1-12):', initialvalue=today.month, minvalue=1, maxvalue=12)
        if m is None:
            return
        y = simpledialog.askinteger('Year', 'Year (e.g. 2026):', initialvalue=today.year, minvalue=1900, maxvalue=3000)
        if y is None:
            return

        created = generate_fixed_events_for_month(y, m)
        self.refresh()
        messagebox.showinfo('Done', f'Created {len(created)} fixed events for {m}/{y} (skipped existing dates).')


