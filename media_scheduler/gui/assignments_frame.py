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
from media_scheduler.gui import theme
from media_scheduler.utils.helpers import to_display_date


class AssignmentsFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.configure(bg=theme.current_colors()['bg'])

        table_wrap = ttk.Frame(self)
        table_wrap.pack(fill='both', expand=True, padx=12, pady=(12, 4))
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_wrap, columns=('id', 'date', 'event', 'zone', 'member', 'name'), show='headings'
        )
        for key, label, w, anchor in [
            ('id', 'ID', 40, 'center'), ('date', 'Data', 120, 'center'),
            ('event', 'Culto / Evento', 380, 'w'), ('zone', 'Posto', 90, 'center'),
            ('member', 'ID Membro', 80, 'center'), ('name', 'Voluntário Atribuído', 220, 'w'),
        ]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=w, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(table_wrap, orient='vertical', command=self.tree.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscroll=sb.set)
        self.tree.bind('<Double-1>', lambda _e: self.edit_selected())

        btns = ttk.Frame(self)
        btns.pack(fill='x', padx=12, pady=(4, 12))
        ttk.Button(btns, text='🔄 Atualizar', command=self.refresh).pack(side='left', padx=3)
        ttk.Button(btns, text='✎ Trocar Voluntário', style='Accent.TButton', command=self.edit_selected).pack(side='left', padx=3)
        ttk.Button(btns, text='＋ Nova Atribuição Manual', command=self.add_assignment).pack(
            side='left', padx=3
        )
        ttk.Button(btns, text='🗑 Eliminar', style='Danger.TButton', command=self.delete_selected).pack(
            side='left', padx=3
        )
        ttk.Button(btns, text='🗑 Eliminar Todas', style='Danger.TButton', command=self.delete_all).pack(
            side='right', padx=3
        )

        self.refresh()

    def refresh_theme(self):
        self.configure(bg=theme.current_colors()['bg'])
        theme.configure_zebra(self.tree)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        theme.configure_zebra(self.tree)
        for idx, r in enumerate(list_assignments_db()):
            zone_key = str(r['zone']).lower()
            tag_name = f"zone_{zone_key}" if zone_key in ('slide', 'luzes', 'live') else theme.row_tag(idx)
            self.tree.insert(
                '', 'end', values=(r['aid'], to_display_date(r['evdate']), r['evname'], r['zone'], r['mid'], r['mname']),
                tags=(theme.row_tag(idx), tag_name)
            )

    def _selected_values(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])['values']

    def edit_selected(self):
        vals = self._selected_values()
        if not vals:
            messagebox.showinfo('Aviso', 'Selecione uma atribuição na tabela para trocar o voluntário.')
            return

        assignment_id = int(vals[0])
        ev_date = vals[1]
        ev_name = vals[2]
        zone = vals[3]
        current_mid = int(vals[4])

        dlg = tk.Toplevel(self)
        dlg.title('Trocar Voluntário')
        dlg.configure(bg=theme.current_colors()['bg'])
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        body = ttk.Frame(dlg, padding=(16, 14, 16, 14))
        body.pack(fill='both', expand=True)

        ttk.Label(body, text=f'Evento: {to_display_date(ev_date)} | {ev_name}', font=theme.fonts()['bold']).grid(
            row=0, column=0, columnspan=2, sticky='w', pady=(0, 4)
        )
        ttk.Label(body, text=f'Posto: {zone.capitalize()}', style='Muted.TLabel').grid(
            row=1, column=0, columnspan=2, sticky='w', pady=(0, 10)
        )

        members = list_members_db()
        member_items = [f"{m['name']} (id:{m['id']})" for m in members]
        member_lookup = {f"{m['name']} (id:{m['id']})": int(m['id']) for m in members}

        ttk.Label(body, text='Voluntário:').grid(row=2, column=0, sticky='w')
        member_cb = ttk.Combobox(body, values=member_items, state='readonly', width=34)
        member_cb.grid(row=2, column=1, sticky='w', padx=(8, 0))

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
        btns.grid(row=3, column=0, columnspan=2, sticky='e', pady=(16, 0))

        def on_confirm():
            selected = member_cb.get().strip()
            if selected not in member_lookup:
                messagebox.showerror('Erro', 'Selecione um voluntário válido.', parent=dlg)
                return
            update_assignment_member(assignment_id, member_lookup[selected])
            dlg.destroy()
            self.refresh()

        ttk.Button(btns, text='Cancelar', command=dlg.destroy).pack(side='right', padx=(8, 0))
        ttk.Button(btns, text='Confirmar Troca', style='Accent.TButton', command=on_confirm).pack(side='right')

        dlg.wait_window()

    def add_assignment(self):
        dlg = tk.Toplevel(self)
        dlg.title('Nova Atribuição Manual')
        dlg.configure(bg=theme.current_colors()['bg'])
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        body = ttk.Frame(dlg, padding=(16, 14, 16, 14))
        body.pack(fill='both', expand=True)

        events = list_events_db()
        event_items = [f"{to_display_date(e['date'])} | {e['name']} (id:{e['id']})" for e in events]
        event_lookup = {f"{to_display_date(e['date'])} | {e['name']} (id:{e['id']})": int(e['id']) for e in events}

        members = list_members_db()
        member_items = [f"{m['name']} (id:{m['id']})" for m in members]
        member_lookup = {f"{m['name']} (id:{m['id']})": int(m['id']) for m in members}

        ttk.Label(body, text='Culto/Evento:').grid(row=0, column=0, sticky='w')
        event_cb = ttk.Combobox(body, values=event_items, state='readonly', width=42)
        event_cb.grid(row=0, column=1, sticky='w', padx=(8, 0), pady=(0, 6))
        if event_items:
            event_cb.current(0)

        ttk.Label(body, text='Posto (Zona):').grid(row=1, column=0, sticky='w')
        zone_cb = ttk.Combobox(body, values=['slide', 'luzes', 'live'], state='readonly', width=16)
        zone_cb.grid(row=1, column=1, sticky='w', padx=(8, 0), pady=(0, 6))
        zone_cb.current(0)

        ttk.Label(body, text='Voluntário:').grid(row=2, column=0, sticky='w')
        member_cb = ttk.Combobox(body, values=member_items, state='readonly', width=34)
        member_cb.grid(row=2, column=1, sticky='w', padx=(8, 0))
        if member_items:
            member_cb.current(0)

        btns = ttk.Frame(body)
        btns.grid(row=3, column=0, columnspan=2, sticky='e', pady=(16, 0))

        def on_confirm():
            if not event_items:
                messagebox.showerror('Erro', 'Não há eventos cadastrados.', parent=dlg)
                return
            if not member_items:
                messagebox.showerror('Erro', 'Não há voluntários cadastrados.', parent=dlg)
                return

            ev_key = event_cb.get().strip()
            zone = zone_cb.get().strip()
            mem_key = member_cb.get().strip()

            if ev_key not in event_lookup:
                messagebox.showerror('Erro', 'Selecione um evento válido.', parent=dlg)
                return
            if zone not in ('slide', 'luzes', 'live'):
                messagebox.showerror('Erro', 'Selecione um posto válido.', parent=dlg)
                return
            if mem_key not in member_lookup:
                messagebox.showerror('Erro', 'Selecione um voluntário válido.', parent=dlg)
                return

            add_assignment_manual(event_lookup[ev_key], zone, member_lookup[mem_key])
            dlg.destroy()
            self.refresh()

        ttk.Button(btns, text='Cancelar', command=dlg.destroy).pack(side='right', padx=(8, 0))
        ttk.Button(btns, text='Criar Atribuição', style='Accent.TButton', command=on_confirm).pack(side='right')

        dlg.wait_window()

    def delete_selected(self):
        vals = self._selected_values()
        if not vals:
            messagebox.showinfo('Aviso', 'Selecione uma atribuição na tabela para eliminar.')
            return
        if messagebox.askyesno('Confirmar', f'Eliminar atribuição #{vals[0]}?'):
            delete_assignment_db(vals[0])
            self.refresh()

    def delete_all(self):
        if messagebox.askyesno('Confirmar', 'Eliminar TODAS as atribuições? Esta ação não pode ser desfeita.'):
            delete_all_assignments_db()
            self.refresh()
