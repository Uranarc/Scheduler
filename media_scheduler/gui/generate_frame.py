"""Schedule generation tab with controls, output text, and CSV export."""

from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from media_scheduler.export import export_assignments_csv
from media_scheduler.gui.date_picker import pick_date_dialog
from media_scheduler.scheduler.algorithm import generate_schedule_db
from media_scheduler.utils.formatting import format_month_message
from media_scheduler.utils.helpers import _safe_float, _safe_int


class GenerateFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.last_rows = []
        self.last_coords = {}
        self._build()

    def _build(self):
        frm = ttk.Frame(self)
        frm.pack(fill='x', padx=10, pady=8)

        ttk.Label(frm, text='Start yyyy-mm-dd').grid(row=0, column=0)
        self.start_e = ttk.Entry(frm, width=12)
        self.start_e.grid(row=0, column=1)
        ttk.Button(frm, text='Pick', command=self.pick_start_date).grid(row=0, column=2, padx=(4, 8))

        ttk.Label(frm, text='End yyyy-mm-dd').grid(row=0, column=3)
        self.end_e = ttk.Entry(frm, width=12)
        self.end_e.grid(row=0, column=4)
        ttk.Button(frm, text='Pick', command=self.pick_end_date).grid(row=0, column=5, padx=(4, 8))

        ttk.Label(frm, text='Cansaço por culto (0–2)').grid(row=0, column=6)
        self.si_e = ttk.Entry(frm, width=5)
        self.si_e.insert(0, '1')
        self.si_e.grid(row=0, column=7)

        ttk.Label(frm, text='Priorizar descanso (0-3)').grid(row=0, column=8)
        self.sw_e = ttk.Entry(frm, width=5)
        self.sw_e.insert(0, '1')
        self.sw_e.grid(row=0, column=9)

        ttk.Label(frm, text='Evitar repetição (0-1)').grid(row=0, column=10)
        self.rw_e = ttk.Entry(frm, width=5)
        self.rw_e.insert(0, '0.3')
        self.rw_e.grid(row=0, column=11)

        ttk.Label(frm, text='Descanso mínimo (dias)').grid(row=1, column=0)
        self.cd_e = ttk.Entry(frm, width=5)
        self.cd_e.insert(0, '0')
        self.cd_e.grid(row=1, column=1)

        ttk.Button(frm, text='Generate schedule', command=self.generate).grid(row=1, column=3, padx=6)
        ttk.Button(frm, text='Export CSV', command=self.export_csv).grid(row=1, column=4, padx=6)

        self.output = tk.Text(self, height=25)
        self.output.pack(fill='both', expand=True, padx=10, pady=8)

    def pick_start_date(self):
        chosen = pick_date_dialog(self, self.start_e.get().strip(), title='Select start date')
        if chosen:
            self.start_e.delete(0, 'end')
            self.start_e.insert(0, chosen)

    def pick_end_date(self):
        chosen = pick_date_dialog(self, self.end_e.get().strip(), title='Select end date')
        if chosen:
            self.end_e.delete(0, 'end')
            self.end_e.insert(0, chosen)

    def generate(self):
        s = self.start_e.get().strip()
        e = self.end_e.get().strip()

        try:
            sdate = datetime.strptime(s, '%Y-%m-%d').date()
            edate = datetime.strptime(e, '%Y-%m-%d').date()
        except Exception:
            messagebox.showerror('Error', 'Invalid dates')
            return

        if sdate > edate:
            messagebox.showerror('Error', 'Start date must be <= End date')
            return

        try:
            si = _safe_float(self.si_e.get(), 1.0)
            sw = _safe_float(self.sw_e.get(), 1.0)
            rw = _safe_float(self.rw_e.get(), 0.3)
            cd = _safe_int(self.cd_e.get(), 0)
        except ValueError:
            messagebox.showerror('Error', 'Stress/weights/cooldown must be numeric')
            return

        res = generate_schedule_db(
            s, e,
            stress_increase=si,
            stress_penalty=sw,
            recent_penalty=rw,
            cooldown_days=cd,
            clear_existing_in_range=True
        )

        rows = res.get('assignments', [])
        coords = res.get('coordinators', {})
        missing = res.get('missing', [])

        self.output.delete('1.0', 'end')

        if not rows and not missing:
            self.output.insert('end', 'No assignments created (no events in range?)\n')
            self.last_rows = []
            self.last_coords = {}
            return

        month_label_map = {
            1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
            5: "maio", 6: "junho", 7: "julho", 8: "agosto",
            9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
        }
        month_label = month_label_map.get(sdate.month, "este mês") if sdate.month == edate.month else "este período"

        msg_text = format_month_message(rows, coords, month_label)
        self.output.insert('end', msg_text)

        if missing:
            self.output.insert('end', '\nMISSING (no available member found):\n')
            for (eid, ds, nm, zone) in missing:
                self.output.insert('end', f'  {ds} | {nm} | zone {zone}\n')

        self.last_rows = rows
        self.last_coords = coords

        msg = f'{len(rows)} assignments created.'
        if missing:
            msg += f' Missing: {len(missing)}.'
        messagebox.showinfo('Done', msg)

    def export_csv(self):
        if not self.last_rows:
            messagebox.showerror('Error', 'No generated assignments to export')
            return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if not path:
            return
        export_assignments_csv(path, self.last_rows)
        messagebox.showinfo('Saved', f'Exported to {path}')


