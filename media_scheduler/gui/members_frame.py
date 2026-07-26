"""Members management tab for CRUD, levels, stress, availability, and blackouts."""

from datetime import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from media_scheduler.db.connection import get_conn
from media_scheduler.db.members import (
    add_blackout_db,
    add_member,
    delete_all_members_db,
    delete_member_db,
    list_blackouts_for_member_db,
    list_members_db,
    set_member_availability,
    set_member_coord_level,
    set_member_max_days_per_month,
    set_member_stress,
    update_member_level,
)
from media_scheduler.gui import theme
from media_scheduler.utils.helpers import _clamp, _safe_int


class MembersFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.configure(bg=theme.current_colors()['bg'])

        form = ttk.LabelFrame(self, text='Adicionar membro', padding=(12, 10))
        form.pack(fill='x', padx=12, pady=(12, 8))

        ttk.Label(form, text='Nome').grid(row=0, column=0, sticky='w')
        self.name_e = ttk.Entry(form, width=20)
        self.name_e.grid(row=0, column=1, padx=(6, 16))

        for i, (label, attr) in enumerate([
            ('Live (0–10)', 'live_e'), ('Luzes (0–10)', 'luzes_e'),
            ('Slide (0–10)', 'slide_e'), ('Coord (0–10)', 'coord_e'),
        ]):
            col = 2 + i * 2
            ttk.Label(form, text=label).grid(row=0, column=col, sticky='w')
            entry = ttk.Entry(form, width=5)
            entry.grid(row=0, column=col + 1, padx=(6, 16))
            setattr(self, attr, entry)

        ttk.Button(form, text='＋ Add member', style='Accent.TButton', command=self.add_member).grid(
            row=0, column=10, padx=(4, 0)
        )

        table_wrap = ttk.Frame(self)
        table_wrap.pack(fill='both', expand=True, padx=12, pady=4)
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_wrap,
            columns=('id', 'name', 'live', 'luzes', 'slide', 'coord', 'stress', 'load', 'maxdays', 'avail'),
            show='headings'
        )
        colspec = [
            ('id', 'ID', 40, 'center'),
            ('name', 'Nome', 160, 'w'),
            ('live', 'Live', 55, 'center'),
            ('luzes', 'Luzes', 60, 'center'),
            ('slide', 'Slide', 60, 'center'),
            ('coord', 'Coord', 60, 'center'),
            ('stress', 'Stress', 70, 'center'),
            ('load', 'Load', 70, 'center'),
            ('maxdays', 'Max dias', 80, 'center'),
            ('avail', 'Disponibilidade', 220, 'w'),
        ]
        for key, label, w, anchor in colspec:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=w, anchor=anchor)

        self.tree.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(table_wrap, orient='vertical', command=self.tree.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscroll=sb.set)

        actions = ttk.LabelFrame(self, text='Ações', padding=(12, 10))
        actions.pack(fill='x', padx=12, pady=(4, 12))

        left = ttk.Frame(actions)
        left.pack(side='left', fill='x', expand=True)
        ttk.Button(left, text='🔄 Refresh', command=self.refresh).pack(side='left', padx=4)
        ttk.Button(left, text='📅 Disponibilidade', command=self.set_availability_selected).pack(side='left', padx=4)
        ttk.Button(left, text='⚡ Stress manual', command=self.set_stress_selected).pack(side='left', padx=4)
        ttk.Button(left, text='♻ Reset load', command=self.reset_load_selected).pack(side='left', padx=4)
        ttk.Button(left, text='✎ Editar níveis', command=self.edit_levels_selected).pack(side='left', padx=4)
        ttk.Button(left, text='🎚 Coord level', command=self.set_coord_selected).pack(side='left', padx=4)
        ttk.Button(left, text='🚫 Blackouts', command=self.set_blackouts_selected).pack(side='left', padx=4)
        ttk.Button(left, text='📆 Max dias/mês', command=self.set_max_days_selected).pack(side='left', padx=4)

        right = ttk.Frame(actions)
        right.pack(side='right')
        ttk.Button(right, text='🗑 Eliminar selecionado', style='Danger.TButton', command=self.delete_selected).pack(
            side='left', padx=4
        )
        ttk.Button(right, text='🗑 Eliminar todos', style='Danger.TButton', command=self.delete_all).pack(
            side='left', padx=4
        )

        self.refresh()

    def refresh_theme(self):
        self.configure(bg=theme.current_colors()['bg'])
        theme.configure_zebra(self.tree)

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])['values']

    def add_member(self):
        name = self.name_e.get().strip()
        if not name:
            messagebox.showerror('Error', 'Name required')
            return
        try:
            live = _clamp(_safe_int(self.live_e.get(), 0), 0, 10)
            luzes = _clamp(_safe_int(self.luzes_e.get(), 0), 0, 10)
            slide = _clamp(_safe_int(self.slide_e.get(), 0), 0, 10)
            coord = _clamp(_safe_int(self.coord_e.get(), 0), 0, 10)
        except ValueError:
            messagebox.showerror('Error', 'Levels must be integers 0..10')
            return

        add_member(name, live, luzes, slide, coord_level=coord, stress=0.0, availability='')
        for e in (self.name_e, self.live_e, self.luzes_e, self.slide_e, self.coord_e):
            e.delete(0, 'end')
        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        theme.configure_zebra(self.tree)
        for idx, r in enumerate(list_members_db()):
            self.tree.insert('', 'end', values=(
                r['id'],
                r['name'],
                int(r['live_level'] or 0),
                int(r['luzes_level'] or 0),
                int(r['slide_level'] or 0),
                int(r['coord_level'] or 0),
                float(r['stress'] or 0.0),
                float(r['load_stress'] or 0.0),
                ("" if r['max_days_per_month'] is None else int(r['max_days_per_month'])),
                r['availability'] or "",
            ), tags=(theme.row_tag(idx),))

    def delete_selected(self):
        vals = self._selected()
        if not vals:
            return
        mid, name = vals[0], vals[1]
        if messagebox.askyesno('Confirm', f'Delete member {name}?'):
            delete_member_db(mid)
            self.refresh()

    def delete_all(self):
        if messagebox.askyesno('Confirm', 'Delete ALL members? This cannot be undone.'):
            delete_all_members_db()
            self.refresh()

    def set_availability_selected(self):
        vals = self._selected()
        if not vals:
            return
        mid = vals[0]
        cur = vals[9] or ''
        ans = simpledialog.askstring(
            'Availability',
            'Dias separados por vírgula (ex: quarta,domingo ou wednesday,sunday ou 2,6). Vazio = sempre:',
            initialvalue=cur
        )
        if ans is None:
            return
        set_member_availability(mid, ans)
        self.refresh()

    def set_stress_selected(self):
        vals = self._selected()
        if not vals:
            return
        mid = vals[0]
        cur_manual = float(vals[6] or 0.0)
        ans = simpledialog.askfloat(
            'Stress (manual)',
            'Set manual stress (>=0). Ex: 0..100',
            initialvalue=cur_manual
        )
        if ans is None:
            return
        set_member_stress(mid, float(max(0.0, ans)))
        self.refresh()

    def reset_load_selected(self):
        vals = self._selected()
        if not vals:
            return
        mid, name = vals[0], vals[1]
        if not messagebox.askyesno('Confirm', f'Reset load (dynamic) for {name}?'):
            return
        with get_conn() as conn:
            conn.execute('UPDATE members SET load_stress = 0 WHERE id = ?', (mid,))
            conn.commit()
        self.refresh()

    def edit_levels_selected(self):
        vals = self._selected()
        if not vals:
            messagebox.showerror('Error', 'Select a member first')
            return
        mid = vals[0]

        new_live = simpledialog.askinteger('Live', 'Live (0..10)', initialvalue=int(vals[2]), minvalue=0, maxvalue=10)
        if new_live is None:
            return
        new_luzes = simpledialog.askinteger('Luzes', 'Luzes (0..10)', initialvalue=int(vals[3]), minvalue=0, maxvalue=10)
        if new_luzes is None:
            return
        new_slide = simpledialog.askinteger('Slide', 'Slide (0..10)', initialvalue=int(vals[4]), minvalue=0, maxvalue=10)
        if new_slide is None:
            return

        update_member_level(mid, 'live', int(new_live))
        update_member_level(mid, 'luzes', int(new_luzes))
        update_member_level(mid, 'slide', int(new_slide))
        self.refresh()

    def set_coord_selected(self):
        vals = self._selected()
        if not vals:
            return
        mid, name = vals[0], vals[1]
        cur = int(vals[5] or 0)
        ans = simpledialog.askinteger('Coord', f'Coord level for {name} (0..10)', initialvalue=cur, minvalue=0, maxvalue=10)
        if ans is None:
            return
        set_member_coord_level(mid, int(ans))
        self.refresh()

    def set_blackouts_selected(self):
        vals = self._selected()
        if not vals:
            return
        mid = vals[0]
        name = vals[1]

        existing = list_blackouts_for_member_db(mid)
        existing_str = ", ".join([r['date'] for r in existing]) if existing else ""

        ans = simpledialog.askstring(
            "Blackout dates",
            f"Datas que {name} NÃO pode (yyyy-mm-dd), separadas por vírgula.\n"
            f"Ex: 2026-02-01, 2026-02-15\n\n"
            f"Atuais: {existing_str}\n\n"
            f"Deixe vazio para limpar todas.",
            initialvalue=existing_str
        )
        if ans is None:
            return

        dates = [d.strip() for d in (ans or "").split(",") if d.strip()]
        for ds in dates:
            try:
                datetime.strptime(ds, "%Y-%m-%d")
            except Exception:
                messagebox.showerror("Error", f"Data inválida: {ds} (use yyyy-mm-dd)")
                return

        with get_conn() as conn:
            conn.execute("DELETE FROM member_blackouts WHERE member_id = ?", (mid,))
            conn.commit()

        for ds in dates:
            add_blackout_db(mid, ds)

        messagebox.showinfo("OK", f"Blackouts atualizados para {name}.")
        self.refresh()

    def set_max_days_selected(self):
        vals = self._selected()
        if not vals:
            return
        mid, name = vals[0], vals[1]

        with get_conn() as conn:
            r = conn.execute("SELECT max_days_per_month FROM members WHERE id = ?", (mid,)).fetchone()
            cur = r["max_days_per_month"]

        ans = simpledialog.askstring(
            "Max dias por mês",
            f"Limite de DIAS por mês para {name}.\n"
            f"- vazio = sem limite\n"
            f"- 1 = no máximo 1 dia/mês\n"
            f"- 2 = no máximo 2 dias/mês\n",
            initialvalue="" if cur is None else str(cur)
        )
        if ans is None:
            return

        ans = ans.strip()
        if ans == "":
            set_member_max_days_per_month(mid, None)
        else:
            try:
                v = int(ans)
                if v < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Digite um número inteiro >= 0, ou deixe vazio para sem limite.")
                return
            set_member_max_days_per_month(mid, v)

        messagebox.showinfo("OK", f"Limite mensal atualizado para {name}.")
        self.refresh()
