"""Events management tab for manual event CRUD and fixed-event generation."""

from datetime import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from media_scheduler.db.events import (
    add_event_db,
    delete_all_events_db,
    delete_event_db,
    delete_events_for_month,
    generate_fixed_events_for_month,
    list_events_db,
)
from media_scheduler.gui import theme
from media_scheduler.gui.date_picker import pick_date_dialog
from media_scheduler.utils.helpers import _next_month_reference, _safe_int


class EventsFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.configure(bg=theme.current_colors()['bg'])

        form = ttk.LabelFrame(self, text='Adicionar evento', padding=(12, 10))
        form.pack(fill='x', padx=12, pady=(12, 8))

        ttk.Label(form, text='Nome').grid(row=0, column=0, sticky='w')
        self.name_e = ttk.Entry(form, width=28)
        self.name_e.grid(row=0, column=1, padx=(6, 16))

        ttk.Label(form, text='Data yyyy-mm-dd').grid(row=0, column=2, sticky='w')
        self.date_e = ttk.Entry(form, width=12)
        self.date_e.grid(row=0, column=3, padx=(6, 4))
        ttk.Button(form, text='📅', width=3, command=self.pick_event_date).grid(row=0, column=4, padx=(0, 16))

        ttk.Label(form, text='Importância').grid(row=0, column=5, sticky='w')
        self.imp_e = ttk.Entry(form, width=5)
        self.imp_e.grid(row=0, column=6, padx=(6, 16))

        ttk.Button(form, text='＋ Add event', style='Accent.TButton', command=self.add_event).grid(
            row=0, column=7, padx=(0, 8)
        )
        ttk.Button(form, text='⚙ Gerar eventos fixos do mês', command=self.generate_fixed_events_dialog).grid(
            row=0, column=8, padx=(0, 8)
        )
        ttk.Button(form, text='🗑 Eliminar eventos do mês', style='Danger.TButton',
                   command=self.delete_events_month_dialog).grid(row=0, column=9)

        table_wrap = ttk.Frame(self)
        table_wrap.pack(fill='both', expand=True, padx=12, pady=4)
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_wrap, columns=('id', 'name', 'date', 'importance'), show='headings')
        for key, label, w, anchor in [
            ('id', 'ID', 40, 'center'), ('name', 'Nome', 420, 'w'),
            ('date', 'Data', 120, 'center'), ('importance', 'Importância', 100, 'center'),
        ]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=w, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(table_wrap, orient='vertical', command=self.tree.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscroll=sb.set)

        btns = ttk.Frame(self)
        btns.pack(fill='x', padx=12, pady=(4, 12))
        ttk.Button(btns, text='🔄 Refresh', command=self.refresh).pack(side='left', padx=4)
        ttk.Button(btns, text='🗑 Eliminar selecionado', style='Danger.TButton', command=self.delete_selected).pack(
            side='left', padx=4
        )
        ttk.Button(btns, text='🗑 Eliminar todos', style='Danger.TButton', command=self.delete_all).pack(
            side='left', padx=4
        )

        self.refresh()

    def refresh_theme(self):
        self.configure(bg=theme.current_colors()['bg'])
        theme.configure_zebra(self.tree)

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
        theme.configure_zebra(self.tree)
        for idx, r in enumerate(list_events_db()):
            self.tree.insert(
                '', 'end', values=(r['id'], r['name'], r['date'], r['importance']),
                tags=(theme.row_tag(idx),)
            )

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        if messagebox.askyesno('Confirm', f'Delete event {vals[1]} on {vals[2]}?'):
            delete_event_db(int(vals[0]))
            self.refresh()

    def delete_all(self):
        if messagebox.askyesno('Confirm', 'Delete ALL events? This also removes related assignments and coordinators.'):
            delete_all_events_db()
            self.refresh()

    def generate_fixed_events_dialog(self):
        next_year, next_month = _next_month_reference()
        m = simpledialog.askinteger('Month', 'Month (1-12):', initialvalue=next_month, minvalue=1, maxvalue=12)
        if m is None:
            return
        y = simpledialog.askinteger('Year', 'Year (e.g. 2026):', initialvalue=next_year, minvalue=1900, maxvalue=3000)
        if y is None:
            return

        created = generate_fixed_events_for_month(y, m)
        self.refresh()
        messagebox.showinfo('Done', f'Created {len(created)} fixed events for {m}/{y} (skipped existing dates).')

    def delete_events_month_dialog(self):
        next_year, next_month = _next_month_reference()
        m = simpledialog.askinteger('Month', 'Month (1-12):', initialvalue=next_month, minvalue=1, maxvalue=12)
        if m is None:
            return
        y = simpledialog.askinteger('Year', 'Year (e.g. 2026):', initialvalue=next_year, minvalue=1900, maxvalue=3000)
        if y is None:
            return

        if not messagebox.askyesno('Confirm', f'Delete all events for {m}/{y}? This also removes related assignments and coordinators.'):
            return

        deleted = delete_events_for_month(y, m)
        self.refresh()
        messagebox.showinfo('Done', f'Deleted {deleted} events for {m}/{y}.')
