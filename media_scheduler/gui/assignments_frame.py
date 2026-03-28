"""Assignments tab for listing, editing, adding, and deleting zone-member assignments."""

import tkinter as tk
from tkinter import messagebox, ttk

from media_scheduler.db.assignments import (
    add_assignment_manual,
    delete_all_assignments_db,
    delete_assignment_db,
    list_assignments_db,
    update_assignment_member,
)
from media_scheduler.db.events import list_events_db
from media_scheduler.db.members import list_members_db


class AssignmentsFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.tree = ttk.Treeview(self, columns=('id', 'date', 'event', 'zone', 'member', 'name'), show='headings')
        for h, w in [('id', 40), ('date', 120), ('event', 420), ('zone', 80), ('member', 80), ('name', 200)]:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=w)
        self.tree.pack(fill='both', expand=True, padx=10, pady=8)

        btns = ttk.Frame(self)
        btns.pack(fill='x', padx=10)
        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left', padx=4)
        ttk.Button(btns, text='Edit selected', command=self.edit_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Add assignment', command=self.add_assignment).pack(side='left', padx=4)
        ttk.Button(btns, text='Delete selected', command=self.delete_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Delete all', command=self.delete_all).pack(side='left', padx=4)

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for r in list_assignments_db():
            self.tree.insert('', 'end', values=(r['aid'], r['evdate'], r['evname'], r['zone'], r['mid'], r['mname']))

    def _selected_values(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])['values']

    def edit_selected(self):
        vals = self._selected_values()
        if not vals:
            return

        assignment_id = int(vals[0])
        ev_date = vals[1]
        ev_name = vals[2]
        zone = vals[3]
        current_mid = int(vals[4])

        dlg = tk.Toplevel(self)
        dlg.title('Edit assignment')
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        body = ttk.Frame(dlg)
        body.pack(fill='both', expand=True, padx=12, pady=12)

        ttk.Label(body, text=f'Event: {ev_date} | {ev_name}').grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 6))
        ttk.Label(body, text=f'Zone: {zone}').grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 8))

        members = list_members_db()
        member_items = [f"{m['name']} (id:{m['id']})" for m in members]
        member_lookup = {f"{m['name']} (id:{m['id']})": int(m['id']) for m in members}

        ttk.Label(body, text='Member').grid(row=2, column=0, sticky='w')
        member_cb = ttk.Combobox(body, values=member_items, state='readonly', width=38)
        member_cb.grid(row=2, column=1, sticky='w', padx=(6, 0))

        current_key = None
        for m in members:
            if int(m['id']) == current_mid:
                current_key = f"{m['name']} (id:{m['id']})"
                break
        if current_key:
            member_cb.set(current_key)
        elif member_items:
            member_cb.current(0)

        btns = ttk.Frame(body)
        btns.grid(row=3, column=0, columnspan=2, sticky='e', pady=(12, 0))

        def on_confirm():
            selected = member_cb.get().strip()
            if selected not in member_lookup:
                messagebox.showerror('Error', 'Select a valid member.', parent=dlg)
                return
            update_assignment_member(assignment_id, member_lookup[selected])
            dlg.destroy()
            self.refresh()

        ttk.Button(btns, text='Cancel', command=dlg.destroy).pack(side='right', padx=(8, 0))
        ttk.Button(btns, text='Confirm', command=on_confirm).pack(side='right')

        dlg.wait_window()

    def add_assignment(self):
        dlg = tk.Toplevel(self)
        dlg.title('Add assignment')
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        body = ttk.Frame(dlg)
        body.pack(fill='both', expand=True, padx=12, pady=12)

        events = list_events_db()
        event_items = [f"{e['date']} | {e['name']} (id:{e['id']})" for e in events]
        event_lookup = {f"{e['date']} | {e['name']} (id:{e['id']})": int(e['id']) for e in events}

        members = list_members_db()
        member_items = [f"{m['name']} (id:{m['id']})" for m in members]
        member_lookup = {f"{m['name']} (id:{m['id']})": int(m['id']) for m in members}

        ttk.Label(body, text='Event').grid(row=0, column=0, sticky='w')
        event_cb = ttk.Combobox(body, values=event_items, state='readonly', width=48)
        event_cb.grid(row=0, column=1, sticky='w', padx=(6, 0), pady=(0, 6))
        if event_items:
            event_cb.current(0)

        ttk.Label(body, text='Zone').grid(row=1, column=0, sticky='w')
        zone_cb = ttk.Combobox(body, values=['slide', 'luzes', 'live'], state='readonly', width=16)
        zone_cb.grid(row=1, column=1, sticky='w', padx=(6, 0), pady=(0, 6))
        zone_cb.current(0)

        ttk.Label(body, text='Member').grid(row=2, column=0, sticky='w')
        member_cb = ttk.Combobox(body, values=member_items, state='readonly', width=38)
        member_cb.grid(row=2, column=1, sticky='w', padx=(6, 0))
        if member_items:
            member_cb.current(0)

        btns = ttk.Frame(body)
        btns.grid(row=3, column=0, columnspan=2, sticky='e', pady=(12, 0))

        def on_confirm():
            if not event_items:
                messagebox.showerror('Error', 'No events available.', parent=dlg)
                return
            if not member_items:
                messagebox.showerror('Error', 'No members available.', parent=dlg)
                return

            ev_key = event_cb.get().strip()
            zone = zone_cb.get().strip()
            mem_key = member_cb.get().strip()

            if ev_key not in event_lookup:
                messagebox.showerror('Error', 'Select a valid event.', parent=dlg)
                return
            if zone not in ('slide', 'luzes', 'live'):
                messagebox.showerror('Error', 'Select a valid zone.', parent=dlg)
                return
            if mem_key not in member_lookup:
                messagebox.showerror('Error', 'Select a valid member.', parent=dlg)
                return

            add_assignment_manual(event_lookup[ev_key], zone, member_lookup[mem_key])
            dlg.destroy()
            self.refresh()

        ttk.Button(btns, text='Cancel', command=dlg.destroy).pack(side='right', padx=(8, 0))
        ttk.Button(btns, text='Confirm', command=on_confirm).pack(side='right')

        dlg.wait_window()

    def delete_selected(self):
        vals = self._selected_values()
        if not vals:
            return
        if messagebox.askyesno('Confirm', f'Delete assignment id {vals[0]}?'):
            delete_assignment_db(vals[0])
            self.refresh()

    def delete_all(self):
        if messagebox.askyesno('Confirm', 'Delete ALL assignments? This cannot be undone.'):
            delete_all_assignments_db()
            self.refresh()

