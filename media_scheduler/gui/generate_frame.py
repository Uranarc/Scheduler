"""Schedule generation tab: controls, progressive disclosure of parameters, 1-click clipboard copy, and preview."""

import calendar
from datetime import date
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from media_scheduler.db.assignments import (
    list_assignments_db,
    list_coordinators_in_range,
    update_assignment_member,
)
from media_scheduler.db.members import list_members_db
from media_scheduler.export import export_assignments_csv
from media_scheduler.gui import theme
from media_scheduler.gui.date_picker import pick_date_dialog
from media_scheduler.scheduler.algorithm import generate_schedule_db
from media_scheduler.utils.formatting import format_month_message
from media_scheduler.utils.helpers import (
    PT_MONTHS,
    _next_month_reference,
    _safe_float,
    _safe_int,
    parse_date_input,
    to_db_date,
    to_display_date,
)


class GenerateFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.last_start = None
        self.last_end = None
        self.last_missing = []
        self._advanced_visible = False
        self._build()

    def _build(self):
        self.configure(bg=theme.current_colors()['bg'])

        # --- Main Controls Card ---
        params = ttk.LabelFrame(self, text='Geração Automática de Escala', padding=(14, 12))
        params.pack(fill='x', padx=12, pady=(12, 8))

        top_row = ttk.Frame(params)
        top_row.pack(fill='x', pady=(0, 6))

        ttk.Label(top_row, text='Início:').pack(side='left')
        self.start_e = ttk.Entry(top_row, width=13)
        self.start_e.pack(side='left', padx=(6, 2))
        ttk.Button(top_row, text='📅', width=3, command=self.pick_start_date).pack(side='left', padx=(0, 14))

        ttk.Label(top_row, text='Fim:').pack(side='left')
        self.end_e = ttk.Entry(top_row, width=13)
        self.end_e.pack(side='left', padx=(6, 2))
        ttk.Button(top_row, text='📅', width=3, command=self.pick_end_date).pack(side='left', padx=(0, 14))

        # Quick shortcuts
        ttk.Button(top_row, text='Este Mês', command=self._set_current_month).pack(side='left', padx=(0, 4))
        ttk.Button(top_row, text='Próximo Mês', command=self._set_next_month).pack(side='left', padx=(0, 16))

        # Primary actions
        ttk.Button(top_row, text='▶ Gerar Escala', style='Accent.TButton', command=self.generate).pack(
            side='left', padx=(0, 8)
        )
        ttk.Button(top_row, text='⬇ Exportar CSV', command=self.export_csv).pack(side='left', padx=(0, 8))

        # Advanced options toggle button
        self.adv_btn = ttk.Button(
            top_row, text='⚙ Opções Avançadas ▾', command=self._toggle_advanced
        )
        self.adv_btn.pack(side='right')

        # Advanced options collapsible panel (Hidden by default)
        self.adv_frame = ttk.Frame(params)
        
        ttk.Separator(self.adv_frame).pack(fill='x', pady=(6, 8))
        adv_grid = ttk.Frame(self.adv_frame)
        adv_grid.pack(fill='x')

        ttk.Label(adv_grid, text='Cansaço por culto (0–2):').grid(row=0, column=0, sticky='w')
        self.si_e = ttk.Entry(adv_grid, width=5)
        self.si_e.insert(0, '1')
        self.si_e.grid(row=0, column=1, sticky='w', padx=(6, 16))

        ttk.Label(adv_grid, text='Priorizar descanso (0–3):').grid(row=0, column=2, sticky='w')
        self.sw_e = ttk.Entry(adv_grid, width=5)
        self.sw_e.insert(0, '1')
        self.sw_e.grid(row=0, column=3, sticky='w', padx=(6, 16))

        ttk.Label(adv_grid, text='Evitar repetição (0–1):').grid(row=0, column=4, sticky='w')
        self.rw_e = ttk.Entry(adv_grid, width=5)
        self.rw_e.insert(0, '0.3')
        self.rw_e.grid(row=0, column=5, sticky='w', padx=(6, 16))

        ttk.Label(adv_grid, text='Descanso mínimo (dias):').grid(row=0, column=6, sticky='w')
        self.cd_e = ttk.Entry(adv_grid, width=5)
        self.cd_e.insert(0, '0')
        self.cd_e.grid(row=0, column=7, sticky='w', padx=(6, 0))

        # Pre-populate next month by default
        self._set_next_month()

        # --- Middle Split: Table and Preview ---
        paned = ttk.PanedWindow(self, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=12, pady=(0, 12))

        # Left pane: editable assignments table
        table_section = ttk.Frame(paned)
        paned.add(table_section, weight=5)

        header_row = ttk.Frame(table_section)
        header_row.pack(fill='x', pady=(0, 4))
        ttk.Label(header_row, text='Atribuições Geradas', style='Heading.TLabel').pack(side='left')
        ttk.Label(header_row, text='  (duplo clique para trocar membro)', style='Muted.TLabel').pack(side='left')
        ttk.Button(header_row, text='✎ Editar', command=self.edit_selected_assignment).pack(side='right')

        table_frm = ttk.Frame(table_section)
        table_frm.pack(fill='both', expand=True)
        table_frm.rowconfigure(0, weight=1)
        table_frm.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frm, columns=('aid', 'date', 'event', 'zone', 'member'), show='headings'
        )
        for h, label, w in [
            ('aid', '', 0), ('date', 'Data', 100), ('event', 'Evento', 240),
            ('zone', 'Posto', 75), ('member', 'Voluntário', 140),
        ]:
            self.tree.heading(h, text=label)
            self.tree.column(h, width=w, stretch=(h != 'aid'))
        self.tree.column('aid', width=0, stretch=False)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(table_frm, orient='vertical', command=self.tree.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscroll=sb.set)
        self.tree.bind('<Double-1>', lambda _e: self.edit_selected_assignment())

        # Right pane: WhatsApp message preview + Copy Button
        preview_section = ttk.Frame(paned)
        paned.add(preview_section, weight=4)

        preview_header = ttk.Frame(preview_section)
        preview_header.pack(fill='x', pady=(0, 4))
        ttk.Label(preview_header, text='Mensagem WhatsApp', style='Heading.TLabel').pack(side='left')
        
        self.copy_btn = ttk.Button(
            preview_header, text='📋 Copiar Mensagem', style='Success.TButton', command=self.copy_to_clipboard
        )
        self.copy_btn.pack(side='right')

        self.status_lbl = ttk.Label(preview_header, text='', style='Success.TLabel')
        self.status_lbl.pack(side='right', padx=8)

        text_wrap = ttk.Frame(preview_section, style='Surface.TFrame')
        text_wrap.pack(fill='both', expand=True)

        c = theme.current_colors()
        f = theme.fonts()
        self.output = tk.Text(
            text_wrap, height=16, wrap='word', relief='flat', borderwidth=0,
            bg=c['surface'], fg=c['fg'], insertbackground=c['fg'],
            selectbackground=c['select_bg'], selectforeground=c['fg'],
            font=f['mono'], padx=10, pady=8,
        )
        self.output.pack(side='left', fill='both', expand=True)
        out_sb = ttk.Scrollbar(text_wrap, orient='vertical', command=self.output.yview)
        out_sb.pack(side='right', fill='y')
        self.output.configure(yscrollcommand=out_sb.set, state='disabled')

    def _toggle_advanced(self):
        self._advanced_visible = not self._advanced_visible
        if self._advanced_visible:
            self.adv_frame.pack(fill='x', pady=(4, 0))
            self.adv_btn.configure(text='⚙ Opções Avançadas ▴')
        else:
            self.adv_frame.pack_forget()
            self.adv_btn.configure(text='⚙ Opções Avançadas ▾')

    def _set_current_month(self):
        today = date.today()
        _, ndays = calendar.monthrange(today.year, today.month)
        s = date(today.year, today.month, 1)
        e = date(today.year, today.month, ndays)
        self.start_e.delete(0, 'end')
        self.start_e.insert(0, to_display_date(s))
        self.end_e.delete(0, 'end')
        self.end_e.insert(0, to_display_date(e))

    def _set_next_month(self):
        ny, nm = _next_month_reference()
        _, ndays = calendar.monthrange(ny, nm)
        s = date(ny, nm, 1)
        e = date(ny, nm, ndays)
        self.start_e.delete(0, 'end')
        self.start_e.insert(0, to_display_date(s))
        self.end_e.delete(0, 'end')
        self.end_e.insert(0, to_display_date(e))

    def refresh_theme(self):
        self.configure(bg=theme.current_colors()['bg'])
        theme.configure_zebra(self.tree)
        c = theme.current_colors()
        self.output.configure(
            bg=c['surface'], fg=c['fg'], insertbackground=c['fg'],
            selectbackground=c['select_bg'], selectforeground=c['fg'],
        )

    def pick_start_date(self):
        chosen = pick_date_dialog(self, self.start_e.get().strip(), title='Selecionar data de início')
        if chosen:
            self.start_e.delete(0, 'end')
            self.start_e.insert(0, chosen)

    def pick_end_date(self):
        chosen = pick_date_dialog(self, self.end_e.get().strip(), title='Selecionar data de fim')
        if chosen:
            self.end_e.delete(0, 'end')
            self.end_e.insert(0, chosen)

    def copy_to_clipboard(self):
        text = self.output.get('1.0', 'end-1c').strip()
        if not text or text.startswith('Nenhuma atribuição gerada'):
            messagebox.showwarning('Aviso', 'Não há texto de mensagem para copiar.')
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_lbl.configure(text='✓ Copiado!')
        self.after(2500, lambda: self.status_lbl.configure(text=''))

    def generate(self):
        s_raw = self.start_e.get().strip()
        e_raw = self.end_e.get().strip()

        sdate = parse_date_input(s_raw)
        edate = parse_date_input(e_raw)

        if not sdate or not edate:
            messagebox.showerror('Erro', 'Datas inválidas. Use o formato dd-mm-aaaa ou selecione no calendário 📅.')
            return

        if sdate > edate:
            messagebox.showerror('Erro', 'A data de início deve ser anterior ou igual à data de fim.')
            return

        try:
            si = _safe_float(self.si_e.get(), 1.0)
            sw = _safe_float(self.sw_e.get(), 1.0)
            rw = _safe_float(self.rw_e.get(), 0.3)
            cd = _safe_int(self.cd_e.get(), 0)
        except ValueError:
            messagebox.showerror('Erro', 'Os campos de cansaço, pesos e descanso devem ser numéricos.')
            return

        s_iso = to_db_date(sdate)
        e_iso = to_db_date(edate)

        res = generate_schedule_db(
            s_iso, e_iso,
            stress_increase=si,
            stress_penalty=sw,
            recent_penalty=rw,
            cooldown_days=cd,
            clear_existing_in_range=True
        )

        self.last_start = s_iso
        self.last_end = e_iso
        self.last_missing = res.get('missing', [])

        self._refresh_table_and_preview()

        rows = res.get('assignments', [])
        msg = f'{len(rows)} atribuições criadas com sucesso.'
        if self.last_missing:
            msg += f' Em falta (sem voluntário disponível): {len(self.last_missing)}.'
        messagebox.showinfo('Concluído', msg)

    def _current_rows(self):
        """Fetch assignments for the last generated range straight from the DB."""
        if not self.last_start or not self.last_end:
            return []
        return list(list_assignments_db(self.last_start, self.last_end))

    def _refresh_table_and_preview(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        theme.configure_zebra(self.tree)
        db_rows = self._current_rows()
        for idx, r in enumerate(db_rows):
            zone_key = str(r['zone']).lower()
            tag_name = f"zone_{zone_key}" if zone_key in ('slide', 'luzes', 'live') else theme.row_tag(idx)
            self.tree.insert(
                '', 'end', values=(r['aid'], to_display_date(r['evdate']), r['evname'], r['zone'], r['mname']),
                tags=(theme.row_tag(idx), tag_name)
            )

        rows = [(r['evid'], r['evdate'], r['evname'], r['zone'], r['mid'], r['mname']) for r in db_rows]

        self.output.configure(state='normal')
        self.output.delete('1.0', 'end')

        if not rows and not self.last_missing:
            self.output.insert('end', 'Nenhuma atribuição gerada (não há eventos no período selecionado?)\n')
            self.output.configure(state='disabled')
            return

        sdate = parse_date_input(self.last_start)
        edate = parse_date_input(self.last_end)
        if sdate and edate and sdate.month == edate.month:
            month_label = PT_MONTHS.get(sdate.month, "este mês").lower()
        else:
            month_label = "este período"

        coords = list_coordinators_in_range(self.last_start, self.last_end)
        msg_text = format_month_message(rows, coords, month_label)
        self.output.insert('end', msg_text)

        if self.last_missing:
            self.output.insert('end', '\nEM FALTA (nenhum membro disponível encontrado):\n')
            for (eid, ds, nm, zone) in self.last_missing:
                self.output.insert('end', f'  {to_display_date(ds)} | {nm} | posto {zone}\n')

        self.output.configure(state='disabled')

    def _selected_assignment(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])['values']

    def edit_selected_assignment(self):
        vals = self._selected_assignment()
        if not vals:
            messagebox.showinfo('Aviso', 'Selecione primeiro uma atribuição na tabela.')
            return

        assignment_id = int(vals[0])
        ev_date, ev_name, zone, current_name = vals[1], vals[2], vals[3], vals[4]

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
        member_items = [m['name'] for m in members]
        member_lookup = {m['name']: int(m['id']) for m in members}

        ttk.Label(body, text='Novo voluntário:').grid(row=2, column=0, sticky='w')
        member_cb = ttk.Combobox(body, values=member_items, state='readonly', width=28)
        member_cb.grid(row=2, column=1, sticky='w', padx=(8, 0))
        if current_name in member_items:
            member_cb.set(current_name)
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
            self._refresh_table_and_preview()

        ttk.Button(btns, text='Cancelar', command=dlg.destroy).pack(side='right', padx=(8, 0))
        ttk.Button(btns, text='Confirmar Troca', style='Accent.TButton', command=on_confirm).pack(side='right')

        dlg.wait_window()

    def export_csv(self):
        db_rows = self._current_rows()
        if not db_rows:
            messagebox.showerror('Erro', 'Não existem atribuições geradas para exportar.')
            return
        rows = [(r['evid'], r['evdate'], r['evname'], r['zone'], r['mid'], r['mname']) for r in db_rows]
        path = filedialog.asksaveasfilename(
            title='Exportar escala em CSV',
            defaultextension='.csv',
            filetypes=[('Ficheiro CSV', '*.csv')]
        )
        if not path:
            return
        export_assignments_csv(path, rows)
        messagebox.showinfo('Guardado', f'Escala exportada para {path}')
