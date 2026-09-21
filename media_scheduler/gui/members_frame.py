"""Members management tab with unified modal editor, availability checkboxes, and interactive blackout calendar."""

import tkinter as tk
from tkinter import messagebox, ttk

from media_scheduler.db.connection import get_conn
from media_scheduler.db.members import (
    add_blackout_db,
    add_member,
    delete_all_members_db,
    delete_member_db,
    list_blackouts_for_member_db,
    list_members_db,
    update_member_full,
)
from media_scheduler.gui import theme
from media_scheduler.gui.date_picker import pick_multi_dates_dialog
from media_scheduler.scheduler.availability import _parse_availability_csv
from media_scheduler.utils.helpers import (
    PT_WEEKDAYS_SHORT,
    _clamp,
    _safe_float,
    _safe_int,
    normalize_availability_display,
)


class MemberEditModal(tk.Toplevel):
    """Unified modal dialog to edit all member parameters at once."""
    def __init__(self, parent, member_data: dict, on_save_callback):
        super().__init__(parent)
        self.member_id = member_data['id']
        self.on_save = on_save_callback
        self.title(f"Editar Membro: {member_data['name']}")
        self.configure(bg=theme.current_colors()['bg'])
        self.geometry('540x580')
        self.minsize(500, 540)
        self.transient(parent)
        self.grab_set()

        self._build(member_data)
        self.wait_visibility()
        self.focus_set()

    def _build(self, m: dict):
        c = theme.current_colors()
        container = ttk.Frame(self, padding=(18, 14, 18, 14))
        container.pack(fill='both', expand=True)

        # 1. Informações Básicas
        info_grp = ttk.LabelFrame(container, text='Informações Pessoais', padding=(12, 8))
        info_grp.pack(fill='x', pady=(0, 10))

        ttk.Label(info_grp, text='Nome:').grid(row=0, column=0, sticky='w', pady=4)
        self.name_var = tk.StringVar(value=m.get('name', ''))
        self.name_e = ttk.Entry(info_grp, textvariable=self.name_var, width=28)
        self.name_e.grid(row=0, column=1, sticky='w', padx=(8, 16), pady=4)

        ttk.Label(info_grp, text='WhatsApp:').grid(row=0, column=2, sticky='w', pady=4)
        self.phone_var = tk.StringVar(value=m.get('phone', '') or '')
        self.phone_e = ttk.Entry(info_grp, textvariable=self.phone_var, width=18)
        self.phone_e.grid(row=0, column=3, sticky='w', padx=(8, 0), pady=4)

        # 2. Níveis de Habilidade (0-10)
        skills_grp = ttk.LabelFrame(container, text='Níveis de Habilidade (0 = Inapto / Não escala, 10 = Especialista)', padding=(12, 8))
        skills_grp.pack(fill='x', pady=(0, 10))

        self.skills_vars = {}
        for idx, (zone, label) in enumerate([
            ('live', 'Live (Transmissão)'),
            ('luzes', 'Mesa de Luzes'),
            ('slide', 'Apresentação (Slide)'),
            ('coord', 'Liderança / Coordenação'),
        ]):
            initial_val = int(m.get(f"{zone}_level", 0) or 0)
            self.skills_vars[zone] = tk.IntVar(value=initial_val)

            row = idx
            ttk.Label(skills_grp, text=f"{label}:", width=24).grid(row=row, column=0, sticky='w', pady=3)

            val_lbl = ttk.Label(skills_grp, text=str(initial_val), width=3, font=theme.fonts()['bold'])
            val_lbl.grid(row=row, column=2, padx=(8, 0))

            scale = ttk.Scale(
                skills_grp, from_=0, to=10, variable=self.skills_vars[zone],
                command=lambda v, lbl=val_lbl, var=self.skills_vars[zone]: (
                    var.set(int(float(v))),
                    lbl.configure(text=str(int(float(v))))
                )
            )
            scale.grid(row=row, column=1, sticky='ew', padx=8, pady=3)
            skills_grp.columnconfigure(1, weight=1)

        # 3. Disponibilidade Semanal (Checkboxes)
        avail_grp = ttk.LabelFrame(container, text='Disponibilidade Semanal', padding=(12, 8))
        avail_grp.pack(fill='x', pady=(0, 10))

        current_avail_set = _parse_availability_csv(m.get('availability', '') or '')
        # If empty, default is all days
        if not (m.get('availability', '') or '').strip():
            current_avail_set = set(range(7))

        self.weekday_vars = {}
        chk_frm = ttk.Frame(avail_grp)
        chk_frm.pack(fill='x', pady=(0, 6))

        for wd_idx in range(7):
            name_short = PT_WEEKDAYS_SHORT[wd_idx]
            var = tk.BooleanVar(value=(wd_idx in current_avail_set))
            self.weekday_vars[wd_idx] = var
            chk = ttk.Checkbutton(chk_frm, text=name_short, variable=var)
            chk.pack(side='left', padx=6)

        btn_bar = ttk.Frame(avail_grp)
        btn_bar.pack(fill='x')
        ttk.Button(btn_bar, text='Todos os dias', command=self._select_all_days).pack(side='left', padx=(0, 6))
        ttk.Button(btn_bar, text='Limpar dias', command=self._clear_all_days).pack(side='left')

        # 4. Limites e Indisponibilidades
        limits_grp = ttk.LabelFrame(container, text='Restrições e Carga', padding=(12, 8))
        limits_grp.pack(fill='x', pady=(0, 12))

        ttk.Label(limits_grp, text='Máx. cultos por mês:').grid(row=0, column=0, sticky='w', pady=4)
        cur_max = "" if m.get('max_days_per_month') is None else str(m.get('max_days_per_month'))
        self.max_days_var = tk.StringVar(value=cur_max)
        max_e = ttk.Entry(limits_grp, textvariable=self.max_days_var, width=6)
        max_e.grid(row=0, column=1, sticky='w', padx=(6, 16))
        ttk.Label(limits_grp, text='(vazio = sem limite)', style='Muted.TLabel').grid(row=0, column=2, sticky='w')

        ttk.Label(limits_grp, text='Stress Manual:').grid(row=1, column=0, sticky='w', pady=4)
        self.stress_var = tk.StringVar(value=str(float(m.get('stress', 0.0) or 0.0)))
        stress_e = ttk.Entry(limits_grp, textvariable=self.stress_var, width=6)
        stress_e.grid(row=1, column=1, sticky='w', padx=(6, 16))
        ttk.Label(limits_grp, text='(pontos fixos de cansaço)', style='Muted.TLabel').grid(row=1, column=2, sticky='w')

        # Blackouts button inside modal
        ttk.Button(
            limits_grp, text='🚫 Gerir Datas de Ausência (Blackouts)...',
            command=self._open_blackouts_calendar
        ).grid(row=2, column=0, columnspan=3, sticky='w', pady=(8, 2))

        # Bottom actions
        bot = ttk.Frame(container)
        bot.pack(fill='x', side='bottom')

        ttk.Button(bot, text='Cancelar', command=self.destroy).pack(side='right', padx=(8, 0))
        ttk.Button(bot, text='💾 Guardar Alterações', style='Accent.TButton', command=self._save).pack(side='right')

    def _select_all_days(self):
        for v in self.weekday_vars.values():
            v.set(True)

    def _clear_all_days(self):
        for v in self.weekday_vars.values():
            v.set(False)

    def _open_blackouts_calendar(self):
        existing = list_blackouts_for_member_db(self.member_id)
        current_isos = [r['date'] for r in existing]
        name = self.name_var.get().strip() or "Membro"
        chosen = pick_multi_dates_dialog(self, current_isos, title=f"Ausências: {name}")
        if chosen is not None:
            with get_conn() as conn:
                conn.execute("DELETE FROM member_blackouts WHERE member_id = ?", (self.member_id,))
                conn.commit()
            for ds_iso in chosen:
                add_blackout_db(self.member_id, ds_iso)
            messagebox.showinfo("Sucesso", f"Datas de ausência atualizadas ({len(chosen)} selecionadas).", parent=self)

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror('Erro', 'O nome do membro é obrigatório.', parent=self)
            return

        phone = self.phone_var.get().strip()
        live = int(self.skills_vars['live'].get())
        luzes = int(self.skills_vars['luzes'].get())
        slide = int(self.skills_vars['slide'].get())
        coord = int(self.skills_vars['coord'].get())

        # Availability
        active_days = [wd for wd, var in self.weekday_vars.items() if var.get()]
        if len(active_days) == 7 or len(active_days) == 0:
            avail_str = ""  # Sempre disponível
        else:
            avail_str = ",".join(str(wd) for wd in sorted(active_days))

        # Max days
        max_days_raw = self.max_days_var.get().strip()
        if not max_days_raw:
            max_days = None
        else:
            try:
                max_days = int(max_days_raw)
                if max_days < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror('Erro', 'Máximo de cultos deve ser um número inteiro >= 0 (ou vazio).', parent=self)
                return

        # Stress
        try:
            stress = max(0.0, _safe_float(self.stress_var.get(), 0.0))
        except ValueError:
            messagebox.showerror('Erro', 'Stress manual deve ser um número válido >= 0.', parent=self)
            return

        update_member_full(
            self.member_id, name, phone, live, luzes, slide, coord, stress, max_days, avail_str
        )
        self.destroy()
        if self.on_save:
            self.on_save()


class MembersFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.configure(bg=theme.current_colors()['bg'])

        # Top Quick Add Form
        form = ttk.LabelFrame(self, text='Adicionar Novo Membro', padding=(12, 10))
        form.pack(fill='x', padx=12, pady=(12, 8))

        ttk.Label(form, text='Nome:').grid(row=0, column=0, sticky='w')
        self.name_e = ttk.Entry(form, width=18)
        self.name_e.grid(row=0, column=1, padx=(4, 12))

        ttk.Label(form, text='WhatsApp:').grid(row=0, column=2, sticky='w')
        self.phone_e = ttk.Entry(form, width=14)
        self.phone_e.grid(row=0, column=3, padx=(4, 12))

        for i, (label, attr) in enumerate([
            ('Live (0-10)', 'live_e'), ('Luzes (0-10)', 'luzes_e'),
            ('Slide (0-10)', 'slide_e'), ('Coord (0-10)', 'coord_e'),
        ]):
            col = 4 + i * 2
            ttk.Label(form, text=label).grid(row=0, column=col, sticky='w')
            entry = ttk.Entry(form, width=4)
            entry.grid(row=0, column=col + 1, padx=(4, 10))
            setattr(self, attr, entry)

        ttk.Button(form, text='＋ Adicionar', style='Accent.TButton', command=self.add_member).grid(
            row=0, column=12, padx=(6, 0)
        )

        # Table section
        table_wrap = ttk.Frame(self)
        table_wrap.pack(fill='both', expand=True, padx=12, pady=4)
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_wrap,
            columns=('id', 'name', 'phone', 'live', 'luzes', 'slide', 'coord', 'stress', 'load', 'maxdays', 'avail'),
            show='headings'
        )
        colspec = [
            ('id', 'ID', 40, 'center'),
            ('name', 'Nome', 140, 'w'),
            ('phone', 'WhatsApp', 110, 'w'),
            ('live', 'Live', 55, 'center'),
            ('luzes', 'Luzes', 60, 'center'),
            ('slide', 'Slide', 60, 'center'),
            ('coord', 'Coord', 60, 'center'),
            ('stress', 'Stress', 70, 'center'),
            ('load', 'Carga', 70, 'center'),
            ('maxdays', 'Máx dias', 80, 'center'),
            ('avail', 'Disponibilidade Semanal', 200, 'w'),
        ]
        for key, label, w, anchor in colspec:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=w, anchor=anchor)

        self.tree.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(table_wrap, orient='vertical', command=self.tree.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscroll=sb.set)
        self.tree.bind('<Double-1>', lambda _e: self.edit_selected())

        # Action Buttons Toolbar
        actions = ttk.Frame(self)
        actions.pack(fill='x', padx=12, pady=(4, 12))

        left = ttk.Frame(actions)
        left.pack(side='left', fill='x', expand=True)
        ttk.Button(left, text='🔄 Atualizar', command=self.refresh).pack(side='left', padx=3)
        ttk.Button(left, text='✎ Editar Membro Completo', style='Accent.TButton', command=self.edit_selected).pack(side='left', padx=3)
        ttk.Button(left, text='🚫 Gerir Ausências (Blackouts)', command=self.set_blackouts_selected).pack(side='left', padx=3)

        right = ttk.Frame(actions)
        right.pack(side='right')
        ttk.Button(right, text='🗑 Eliminar', style='Danger.TButton', command=self.delete_selected).pack(
            side='left', padx=3
        )
        ttk.Button(right, text='🗑 Eliminar Todos', style='Danger.TButton', command=self.delete_all).pack(
            side='left', padx=3
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
            messagebox.showerror('Erro', 'O nome do membro é obrigatório.')
            return
        try:
            live = _clamp(_safe_int(self.live_e.get(), 0), 0, 10)
            luzes = _clamp(_safe_int(self.luzes_e.get(), 0), 0, 10)
            slide = _clamp(_safe_int(self.slide_e.get(), 0), 0, 10)
            coord = _clamp(_safe_int(self.coord_e.get(), 0), 0, 10)
        except ValueError:
            messagebox.showerror('Erro', 'Os níveis de habilidade devem ser números inteiros de 0 a 10.')
            return

        phone = self.phone_e.get().strip()
        add_member(name, live, luzes, slide, coord_level=coord, stress=0.0, availability='', phone=phone)
        for e in (self.name_e, self.phone_e, self.live_e, self.luzes_e, self.slide_e, self.coord_e):
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
                r['phone'] or "",
                int(r['live_level'] or 0),
                int(r['luzes_level'] or 0),
                int(r['slide_level'] or 0),
                int(r['coord_level'] or 0),
                f"{float(r['stress'] or 0.0):.2f}",
                f"{float(r['load_stress'] or 0.0):.2f}",
                ("" if r['max_days_per_month'] is None else int(r['max_days_per_month'])),
                normalize_availability_display(r['availability'] or ""),
            ), tags=(theme.row_tag(idx),))

    def edit_selected(self):
        vals = self._selected()
        if not vals:
            messagebox.showinfo('Aviso', 'Selecione um membro da tabela para editar.')
            return
        mid = int(vals[0])

        with get_conn() as conn:
            m = conn.execute("SELECT * FROM members WHERE id = ?", (mid,)).fetchone()

        if m:
            MemberEditModal(self, dict(m), on_save_callback=self.refresh)

    def delete_selected(self):
        vals = self._selected()
        if not vals:
            return
        mid, name = vals[0], vals[1]
        if messagebox.askyesno('Confirmar', f'Eliminar o membro "{name}"?'):
            delete_member_db(mid)
            self.refresh()

    def delete_all(self):
        if messagebox.askyesno('Confirmar', 'Eliminar TODOS os membros? Esta ação não pode ser desfeita.'):
            delete_all_members_db()
            self.refresh()

    def set_blackouts_selected(self):
        vals = self._selected()
        if not vals:
            messagebox.showinfo('Aviso', 'Selecione um membro da tabela primeiro.')
            return
        mid = int(vals[0])
        name = vals[1]

        existing = list_blackouts_for_member_db(mid)
        current_isos = [r['date'] for r in existing]

        chosen = pick_multi_dates_dialog(self, current_isos, title=f"Ausências: {name}")
        if chosen is not None:
            with get_conn() as conn:
                conn.execute("DELETE FROM member_blackouts WHERE member_id = ?", (mid,))
                conn.commit()
            for ds_iso in chosen:
                add_blackout_db(mid, ds_iso)
            messagebox.showinfo("Sucesso", f"Datas de ausência atualizadas para {name}.")
            self.refresh()
