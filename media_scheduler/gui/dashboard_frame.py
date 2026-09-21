"""Dashboard tab with monthly per-member assignment and load summary metrics."""

import tkinter as tk
from tkinter import ttk

from media_scheduler.db.assignments import get_load_summary
from media_scheduler.gui import theme
from media_scheduler.utils.helpers import PT_MONTHS, _next_month_reference


class DashboardFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        self.configure(bg=theme.current_colors()['bg'])

        top = ttk.LabelFrame(self, text='Período de análise', padding=(12, 10))
        top.pack(fill='x', padx=12, pady=(12, 8))

        next_year, next_month = _next_month_reference()

        ttk.Label(top, text='Mês').pack(side='left')
        month_labels = [f"{m:02d} - {PT_MONTHS[m]}" for m in range(1, 13)]
        self.month_str_var = tk.StringVar(value=month_labels[next_month - 1])
        self.month_cb = ttk.Combobox(
            top, values=month_labels, textvariable=self.month_str_var, state='readonly', width=16
        )
        self.month_cb.pack(side='left', padx=(6, 16))

        ttk.Label(top, text='Ano').pack(side='left')
        year_values = [str(y) for y in range(next_year - 5, next_year + 6)]
        self.year_cb = ttk.Combobox(top, values=year_values, state='readonly', width=7)
        self.year_cb.set(str(next_year))
        self.year_cb.pack(side='left', padx=(6, 16))

        ttk.Button(top, text='🔄 Atualizar', style='Accent.TButton', command=self.refresh).pack(side='left')

        ttk.Label(
            self, text='●  a vermelho: membros acima do limite mensal de dias', style='Muted.TLabel'
        ).pack(anchor='w', padx=12, pady=(0, 4))

        table_wrap = ttk.Frame(self)
        table_wrap.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        table_wrap.rowconfigure(0, weight=1)
        table_wrap.columnconfigure(0, weight=1)

        cols = (
            'name', 'slide_count', 'luzes_count', 'live_count', 'total_days',
            'load_stress', 'manual_stress', 'max_days', 'days_remaining'
        )
        self.tree = ttk.Treeview(table_wrap, columns=cols, show='headings')

        spec = [
            ('name', 'Nome', 180, 'w'),
            ('slide_count', 'Slide', 95, 'center'),
            ('luzes_count', 'Luzes', 95, 'center'),
            ('live_count', 'Live', 90, 'center'),
            ('total_days', 'Total dias', 90, 'center'),
            ('load_stress', 'Carga dinâmica', 105, 'center'),
            ('manual_stress', 'Stress manual', 105, 'center'),
            ('max_days', 'Máx dias', 80, 'center'),
            ('days_remaining', 'Dias restantes', 110, 'center'),
        ]
        for h, label, w, anchor in spec:
            self.tree.heading(h, text=label)
            self.tree.column(h, width=w, anchor=anchor)

        self.tree.grid(row=0, column=0, sticky='nsew')
        sb = ttk.Scrollbar(table_wrap, orient='vertical', command=self.tree.yview)
        sb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscroll=sb.set)

        self.refresh()

    def refresh_theme(self):
        self.configure(bg=theme.current_colors()['bg'])
        theme.configure_zebra(self.tree, extra_tags={
            'over_limit': {'foreground': theme.current_colors()['danger']},
        })

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        theme.configure_zebra(self.tree, extra_tags={
            'over_limit': {'foreground': theme.current_colors()['danger']},
        })

        try:
            month_val = self.month_str_var.get().split(' - ')[0]
            month = int(month_val)
            year = int(self.year_cb.get())
        except (ValueError, IndexError):
            return

        rows = get_load_summary(year, month)
        for idx, r in enumerate(rows):
            max_days = r['max_days']
            if max_days is None:
                max_days_text = '—'
                days_remaining_text = '—'
            else:
                max_days_text = str(max_days)
                rem = int(r['days_remaining'] or 0)
                days_remaining_text = str(rem if rem > 0 else 0)

            tags = [theme.row_tag(idx)]
            if r.get('over_limit'):
                tags.append('over_limit')

            self.tree.insert('', 'end', values=(
                r['name'],
                r['slide_count'],
                r['luzes_count'],
                r['live_count'],
                r['total_days'],
                f"{float(r['load_stress'] or 0.0):.2f}",
                f"{float(r['manual_stress'] or 0.0):.2f}",
                max_days_text,
                days_remaining_text,
            ), tags=tuple(tags))
