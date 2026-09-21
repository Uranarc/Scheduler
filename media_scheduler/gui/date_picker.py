"""Calendar-style date picker dialogs (single and multi-select) used across the GUI."""

import calendar
from datetime import date
import tkinter as tk
from tkinter import ttk

from media_scheduler.gui import theme
from media_scheduler.utils.helpers import (
    PT_MONTHS,
    PT_WEEKDAYS_SHORT,
    _next_month_reference_date,
    parse_date_input,
    to_db_date,
    to_display_date,
)


class DatePickerDialog(tk.Toplevel):
    """Single date selection modal."""
    def __init__(self, parent, initial_date: date | None = None, title: str = "Selecionar data"):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=theme.current_colors()['bg'])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        initial = initial_date or _next_month_reference_date()
        self.result: str | None = None
        self.year_var = tk.IntVar(value=initial.year)
        self.month_var = tk.IntVar(value=initial.month)

        top = ttk.Frame(self, padding=(10, 10, 10, 4))
        top.pack(fill='x')

        years = [str(y) for y in range(initial.year - 10, initial.year + 11)]
        ttk.Label(top, text='Ano').pack(side='left')
        self.year_cb = ttk.Combobox(top, width=6, state='readonly', values=years, textvariable=self.year_var)
        self.year_cb.pack(side='left', padx=(4, 12))

        ttk.Label(top, text='Mês').pack(side='left')
        month_labels = [f"{m:02d} - {PT_MONTHS[m]}" for m in range(1, 13)]
        self.month_str_var = tk.StringVar(value=month_labels[initial.month - 1])
        self.month_cb = ttk.Combobox(
            top, width=14, state='readonly', values=month_labels, textvariable=self.month_str_var
        )
        self.month_cb.pack(side='left', padx=4)

        self.days_frame = ttk.Frame(self, padding=(10, 4, 10, 6))
        self.days_frame.pack()

        bottom = ttk.Frame(self, padding=(10, 0, 10, 10))
        bottom.pack(fill='x')
        ttk.Button(bottom, text='● Hoje', style='Accent.TButton', command=self._set_today).pack(side='left')
        ttk.Button(bottom, text='Cancelar', command=self._cancel).pack(side='right')

        self.year_cb.bind('<<ComboboxSelected>>', lambda _e: self._render_days())
        self.month_cb.bind('<<ComboboxSelected>>', self._on_month_selected)
        self.bind('<Escape>', lambda _e: self._cancel())

        self._render_days()
        self.wait_visibility()
        self.focus_set()

    def _on_month_selected(self, _event=None):
        val = self.month_str_var.get()
        try:
            m = int(val.split(' - ')[0])
            self.month_var.set(m)
        except Exception:
            pass
        self._render_days()

    def _render_days(self):
        for w in self.days_frame.winfo_children():
            w.destroy()

        weekdays = [PT_WEEKDAYS_SHORT[i] for i in range(7)]
        for i, wd in enumerate(weekdays):
            style = 'Muted.TLabel'
            ttk.Label(self.days_frame, text=wd, width=4, anchor='center', style=style).grid(
                row=0, column=i, padx=1, pady=(0, 4)
            )

        y = int(self.year_var.get())
        m = int(self.month_var.get())
        first_wd, ndays = calendar.monthrange(y, m)
        today = date.today()

        row = 1
        col = first_wd
        for d in range(1, ndays + 1):
            is_today = (y == today.year and m == today.month and d == today.day)
            ttk.Button(
                self.days_frame,
                text=str(d),
                width=4,
                style='Accent.TButton' if is_today else 'TButton',
                command=lambda day=d: self._pick(day)
            ).grid(row=row, column=col, padx=1, pady=1)
            col += 1
            if col > 6:
                col = 0
                row += 1

    def _pick(self, day: int):
        picked = date(int(self.year_var.get()), int(self.month_var.get()), int(day))
        self.result = to_display_date(picked)
        self.destroy()

    def _set_today(self):
        self.result = to_display_date(date.today())
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


class MultiDatePickerDialog(tk.Toplevel):
    """Interactive multi-date selector (e.g. for blackout dates)."""
    def __init__(self, parent, initial_dates_iso: list[str] | None = None, title: str = "Selecionar datas"):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=theme.current_colors()['bg'])
        self.minsize(420, 480)
        self.transient(parent)
        self.grab_set()

        self.selected_dates: set[str] = set()
        if initial_dates_iso:
            for ds in initial_dates_iso:
                parsed = parse_date_input(ds)
                if parsed:
                    self.selected_dates.add(to_db_date(parsed))

        ref = _next_month_reference_date()
        if self.selected_dates:
            first_selected = parse_date_input(sorted(self.selected_dates)[0])
            if first_selected:
                ref = first_selected

        self.result: list[str] | None = None
        self.year_var = tk.IntVar(value=ref.year)
        self.month_var = tk.IntVar(value=ref.month)

        # Controls top bar
        top = ttk.Frame(self, padding=(14, 12, 14, 4))
        top.pack(fill='x')

        ttk.Button(top, text='◀', width=3, command=self._prev_month).pack(side='left', padx=(0, 6))

        years = [str(y) for y in range(ref.year - 5, ref.year + 6)]
        self.year_cb = ttk.Combobox(top, width=6, state='readonly', values=years, textvariable=self.year_var)
        self.year_cb.pack(side='left', padx=(0, 6))

        month_labels = [f"{m:02d} - {PT_MONTHS[m]}" for m in range(1, 13)]
        self.month_str_var = tk.StringVar(value=month_labels[ref.month - 1])
        self.month_cb = ttk.Combobox(
            top, width=14, state='readonly', values=month_labels, textvariable=self.month_str_var
        )
        self.month_cb.pack(side='left', padx=(0, 6))

        ttk.Button(top, text='▶', width=3, command=self._next_month).pack(side='left')

        ttk.Label(top, text='  (Clique para marcar/desmarcar)', style='Muted.TLabel').pack(side='left')

        # Calendar grid
        self.days_frame = ttk.Frame(self, padding=(14, 8, 14, 8))
        self.days_frame.pack()

        # Selected preview list
        info_frame = ttk.LabelFrame(self, text='Datas selecionadas', padding=(10, 6))
        info_frame.pack(fill='both', expand=True, padx=14, pady=4)

        self.preview_lbl = ttk.Label(info_frame, text='', wraplength=380, justify='left')
        self.preview_lbl.pack(fill='both', expand=True)

        # Bottom action buttons
        bottom = ttk.Frame(self, padding=(14, 8, 14, 12))
        bottom.pack(fill='x')

        ttk.Button(bottom, text='🗑 Limpar todas', style='Danger.TButton', command=self._clear_all).pack(side='left')
        ttk.Button(bottom, text='Cancelar', command=self._cancel).pack(side='right', padx=(8, 0))
        self.confirm_btn = ttk.Button(bottom, text='Confirmar', style='Accent.TButton', command=self._confirm)
        self.confirm_btn.pack(side='right')

        self.year_cb.bind('<<ComboboxSelected>>', lambda _e: self._render_days())
        self.month_cb.bind('<<ComboboxSelected>>', self._on_month_selected)
        self.bind('<Escape>', lambda _e: self._cancel())

        self._render_days()
        self._update_preview()
        self.wait_visibility()
        self.focus_set()

    def _prev_month(self):
        m = int(self.month_var.get()) - 1
        y = int(self.year_var.get())
        if m < 1:
            m = 12
            y -= 1
        self.year_var.set(y)
        self.month_var.set(m)
        self.month_str_var.set(f"{m:02d} - {PT_MONTHS[m]}")
        self._render_days()

    def _next_month(self):
        m = int(self.month_var.get()) + 1
        y = int(self.year_var.get())
        if m > 12:
            m = 1
            y += 1
        self.year_var.set(y)
        self.month_var.set(m)
        self.month_str_var.set(f"{m:02d} - {PT_MONTHS[m]}")
        self._render_days()

    def _on_month_selected(self, _event=None):
        val = self.month_str_var.get()
        try:
            m = int(val.split(' - ')[0])
            self.month_var.set(m)
        except Exception:
            pass
        self._render_days()

    def _render_days(self):
        for w in self.days_frame.winfo_children():
            w.destroy()

        weekdays = [PT_WEEKDAYS_SHORT[i] for i in range(7)]
        for i, wd in enumerate(weekdays):
            style = 'Muted.TLabel'
            ttk.Label(self.days_frame, text=wd, width=4, anchor='center', style=style).grid(
                row=0, column=i, padx=2, pady=(0, 4)
            )

        y = int(self.year_var.get())
        m = int(self.month_var.get())
        first_wd, ndays = calendar.monthrange(y, m)

        row = 1
        col = first_wd
        for d in range(1, ndays + 1):
            dt_iso = f"{y:04d}-{m:02d}-{d:02d}"
            is_selected = dt_iso in self.selected_dates
            ttk.Button(
                self.days_frame,
                text=f"{'✓ ' if is_selected else ''}{d}",
                width=5,
                style='Accent.TButton' if is_selected else 'TButton',
                command=lambda iso=dt_iso: self._toggle_date(iso)
            ).grid(row=row, column=col, padx=2, pady=2)
            col += 1
            if col > 6:
                col = 0
                row += 1

    def _toggle_date(self, iso: str):
        if iso in self.selected_dates:
            self.selected_dates.remove(iso)
        else:
            self.selected_dates.add(iso)
        self._render_days()
        self._update_preview()

    def _update_preview(self):
        sorted_dates = sorted(self.selected_dates)
        count = len(sorted_dates)
        self.confirm_btn.configure(text=f"Confirmar ({count})")
        if not sorted_dates:
            self.preview_lbl.configure(text="Nenhuma data selecionada (membro disponível em todas).")
        else:
            formatted = ", ".join(to_display_date(d) for d in sorted_dates)
            self.preview_lbl.configure(text=f"{count} data(s): {formatted}")

    def _clear_all(self):
        self.selected_dates.clear()
        self._render_days()
        self._update_preview()

    def _confirm(self):
        self.result = sorted(self.selected_dates)
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def pick_date_dialog(parent, current_date_str: str = '', title: str = 'Selecionar data') -> str | None:
    initial = _next_month_reference_date()
    if current_date_str:
        parsed = parse_date_input(current_date_str)
        if parsed:
            initial = parsed

    dlg = DatePickerDialog(parent, initial_date=initial, title=title)
    parent.wait_window(dlg)
    return dlg.result


def pick_multi_dates_dialog(parent, current_dates_iso: list[str] | None = None, title: str = 'Gerir indisponibilidades') -> list[str] | None:
    dlg = MultiDatePickerDialog(parent, initial_dates_iso=current_dates_iso or [], title=title)
    parent.wait_window(dlg)
    return dlg.result
