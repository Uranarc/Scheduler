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
from media_scheduler.utils.helpers import _clamp, _safe_int


class MembersFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        frm = ttk.Frame(self)
        frm.pack(fill='x', padx=10, pady=8)

        ttk.Label(frm, text='Name').grid(row=0, column=0)
        self.name_e = ttk.Entry(frm, width=18)
        self.name_e.grid(row=0, column=1)

        ttk.Label(frm, text='Live (0–10)').grid(row=0, column=2)
        self.live_e = ttk.Entry(frm, width=5)
        self.live_e.grid(row=0, column=3)

        ttk.Label(frm, text='Luzes (0–10)').grid(row=0, column=4)
        self.luzes_e = ttk.Entry(frm, width=5)
        self.luzes_e.grid(row=0, column=5)

        ttk.Label(frm, text='Slide (0–10)').grid(row=0, column=6)
        self.slide_e = ttk.Entry(frm, width=5)
        self.slide_e.grid(row=0, column=7)

        ttk.Label(frm, text='Coord (0–10)').grid(row=0, column=8)
        self.coord_e = ttk.Entry(frm, width=5)
        self.coord_e.grid(row=0, column=9)

        ttk.Button(frm, text='Add member', command=self.add_member).grid(row=0, column=10, padx=6)

        midfrm = ttk.Frame(self)
        midfrm.pack(fill='both', expand=True, padx=10, pady=8)

        self.tree = ttk.Treeview(
            midfrm,
            columns=('id', 'name', 'live', 'luzes', 'slide', 'coord', 'stress', 'load', 'maxdays', 'avail'),
            show='headings'
        )
        colspec = [
            ('id', 40),
            ('name', 160),
            ('live', 55),
            ('luzes', 60),
            ('slide', 60),
            ('coord', 60),
            ('stress', 70),
            ('load', 70),
            ('maxdays', 80),
            ('avail', 200),
        ]
        for h, w in colspec:
            self.tree.heading(h, text=h)
            self.tree.column(h, width=w)

        self.tree.pack(side='left', fill='both', expand=True)
        sb = ttk.Scrollbar(midfrm, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscroll=sb.set)

        btns = ttk.Frame(self)
        btns.pack(fill='x', padx=10)

        ttk.Button(btns, text='Refresh', command=self.refresh).pack(side='left', padx=4)
        ttk.Button(btns, text='Delete selected', command=self.delete_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Delete all', command=self.delete_all).pack(side='left', padx=4)
        ttk.Button(btns, text='Set availability', command=self.set_availability_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Set stress (manual)', command=self.set_stress_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Reset load', command=self.reset_load_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Edit levels', command=self.edit_levels_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Set coord level', command=self.set_coord_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Blackout dates', command=self.set_blackouts_selected).pack(side='left', padx=4)
        ttk.Button(btns, text='Max dias/mês', command=self.set_max_days_selected).pack(side='left', padx=4)

        self.refresh()

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
        for r in list_members_db():
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
            ))

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


