"""Events management tab for manual event CRUD and fixed-event generation."""

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
from media_scheduler.utils.helpers import (
    PT_MONTHS,
    _next_month_reference,
    _safe_int,
    parse_date_input,
    to_db_date,
    to_display_date,
)


class EventsFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.configure(bg=theme.current_colors()['bg'])

        # Form to add custom event
        form = ttk.LabelFrame(self, text='Adicionar Novo Evento / Culto', padding=(12, 10))
        form.pack(fill='x', padx=12, pady=(12, 8))

        ttk.Label(form, text='Nome do Culto:').grid(row=0, column=0, sticky='w')
        self.name_e = ttk.Entry(form, width=26)
        self.name_e.grid(row=0, column=1, padx=(6, 14))

        ttk.Label(form, text='Data:').grid(row=0, column=2, sticky='w')
        self.date_e = ttk.Entry(form, width=13)
        self.date_e.grid(row=0, column=3, padx=(6, 2))
        ttk.Button(form, text='📅', width=3, command=self.pick_event_date).grid(row=0, column=4, padx=(0, 14))

        ttk.Label(form, text='Importância (1-10):').grid(row=0, column=5, sticky='w')
        self.imp_e = ttk.Entry(form, width=5)
        self.imp_e.insert(0, '8')
        self.imp_e.grid(row=0, column=6, padx=(6, 14))

        ttk.Button(form, text='＋ Adicionar Evento', style='Accent.TButton', command=self.add_event).grid(
            row=0, column=7, padx=(0, 10)
        )

        # Batch tools bar
        tools_bar = ttk.Frame(self)
        tools_bar.pack(fill='x', padx=12, pady=(0, 6))

        ttk.Button(
            tools_bar, text='⚙ Gerar Todos os Cultos Fixos do Mês...', command=self.generate_fixed_events_dialog
        ).pack(side='left', padx=(0, 6))

        ttk.Button(
            tools_bar, text='🗑 Limpar Cultos de um Mês...', style='Danger.TButton',
            command=self.delete_events_month_dialog
        ).pack(side='left')

        # Table section
        table_wrap = ttk.Frame(self)
        table_wrap.pack(fill='both', expand=True, padx=12, pady=4)
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(table_wrap, columns=('id', 'name', 'date', 'importance'), show='headings')
        for key, label, w, anchor in [
            ('id', 'ID', 40, 'center'), ('name', 'Nome do Evento', 420, 'w'),
            ('date', 'Data', 140, 'center'), ('importance', 'Importância (1-10)', 140, 'center'),
        ]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=w, anchor=anchor)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(table_wrap, orient='vertical', command=self.tree.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscroll=sb.set)

        # Actions toolbar
        btns = ttk.Frame(self)
        btns.pack(fill='x', padx=12, pady=(4, 12))
        ttk.Button(btns, text='🔄 Atualizar Lista', command=self.refresh).pack(side='left', padx=3)
        ttk.Button(btns, text='🗑 Eliminar Selecionado', style='Danger.TButton', command=self.delete_selected).pack(
            side='left', padx=3
        )
        ttk.Button(btns, text='🗑 Eliminar Todos os Eventos', style='Danger.TButton', command=self.delete_all).pack(
            side='right', padx=3
        )

        self.refresh()

    def refresh_theme(self):
        self.configure(bg=theme.current_colors()['bg'])
        theme.configure_zebra(self.tree)

    def add_event(self):
        name = self.name_e.get().strip()
        if not name:
            messagebox.showerror('Erro', 'O nome do evento é obrigatório.')
            return

        date_s = self.date_e.get().strip()
        parsed_d = parse_date_input(date_s)
        if not parsed_d:
            messagebox.showerror('Erro', 'Data inválida. Use o formato dd-mm-aaaa ou selecione no calendário 📅.')
            return

        try:
            imp = _safe_int(self.imp_e.get(), 1)
        except ValueError:
            messagebox.showerror('Erro', 'Importância deve ser um número inteiro de 1 a 10.')
            return

        add_event_db(name, to_db_date(parsed_d), imp)
        self.name_e.delete(0, 'end')
        self.date_e.delete(0, 'end')
        self.imp_e.delete(0, 'end')
        self.imp_e.insert(0, '8')
        self.refresh()

    def pick_event_date(self):
        chosen = pick_date_dialog(self, self.date_e.get().strip(), title='Selecionar data do evento')
        if chosen:
            self.date_e.delete(0, 'end')
            self.date_e.insert(0, chosen)

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        theme.configure_zebra(self.tree)
        for idx, r in enumerate(list_events_db()):
            self.tree.insert(
                '', 'end', values=(r['id'], r['name'], to_display_date(r['date']), r['importance']),
                tags=(theme.row_tag(idx),)
            )

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo('Aviso', 'Selecione um evento na tabela para eliminar.')
            return
        vals = self.tree.item(sel[0])['values']
        if messagebox.askyesno('Confirmar', f'Eliminar o evento "{vals[1]}" em {vals[2]}?'):
            delete_event_db(int(vals[0]))
            self.refresh()

    def delete_all(self):
        if messagebox.askyesno('Confirmar', 'Eliminar TODOS os eventos? Isto também removerá as atribuições de voluntários associadas.'):
            delete_all_events_db()
            self.refresh()

    def generate_fixed_events_dialog(self):
        next_year, next_month = _next_month_reference()
        m = simpledialog.askinteger('Gerar Cultos Fixos', 'Indique o Mês (1-12):', initialvalue=next_month, minvalue=1, maxvalue=12)
        if m is None:
            return
        y = simpledialog.askinteger('Gerar Cultos Fixos', 'Indique o Ano (ex: 2026):', initialvalue=next_year, minvalue=1900, maxvalue=3000)
        if y is None:
            return

        month_name = PT_MONTHS.get(m, str(m))
        created = generate_fixed_events_for_month(y, m)
        self.refresh()
        messagebox.showinfo('Concluído', f'Criados {len(created)} cultos fixos para {month_name}/{y}.\n(Cultos já existentes foram mantidos).')

    def delete_events_month_dialog(self):
        next_year, next_month = _next_month_reference()
        m = simpledialog.askinteger('Limpar Cultos do Mês', 'Indique o Mês (1-12):', initialvalue=next_month, minvalue=1, maxvalue=12)
        if m is None:
            return
        y = simpledialog.askinteger('Limpar Cultos do Mês', 'Indique o Ano (ex: 2026):', initialvalue=next_year, minvalue=1900, maxvalue=3000)
        if y is None:
            return

        month_name = PT_MONTHS.get(m, str(m))
        if not messagebox.askyesno('Confirmar', f'Eliminar todos os eventos de {month_name}/{y}? Isto também removerá as atribuições de voluntários deste mês.'):
            return

        deleted = delete_events_for_month(y, m)
        self.refresh()
        messagebox.showinfo('Concluído', f'Eliminados {deleted} eventos de {month_name}/{y}.')
