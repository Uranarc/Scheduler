"""Schedule generation tab with controls, output text, and CSV export."""

import re
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from media_scheduler.db.assignments import update_assignment_member
from media_scheduler.db.members import list_members_db
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
        self.original_text = ""
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
        ttk.Button(frm, text='Save message changes', command=self.save_message_changes).grid(row=1, column=5, padx=6)

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
        self.original_text = msg_text

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

    def save_message_changes(self):
        """
        Parse the edited text in the output window and apply changes to the DB.
        Detects member name changes per zone and updates assignments.
        """
        if not self.last_rows:
            messagebox.showerror('Error', 'No schedule generated yet')
            return

        current_text = self.output.get('1.0', 'end')

        # Build a map: (date, event_name, zone) -> member_name from original text
        original_map = {}
        for (_, ds, evname, zone, _, mname) in self.last_rows:
            original_map[(ds, evname, zone)] = mname

        # Build a map: (date, event_name, zone) -> member_name from current text
        current_map = self._parse_schedule_text(current_text)

        # Find differences and update
        members = list_members_db()
        member_lookup = {m['name']: m['id'] for m in members}

        changes = []
        for key, old_name in original_map.items():
            new_name = current_map.get(key, old_name)
            if new_name != old_name:
                ds, evname, zone = key
                # Find the assignment id for this (date, event_name, zone, old_name)
                for (aid, r_ds, r_evname, r_zone, r_mid, r_mname) in self.last_rows:
                    if r_ds == ds and r_evname == evname and r_zone == zone and r_mname == old_name:
                        # New member must exist
                        if new_name not in member_lookup:
                            messagebox.showerror('Error', f'Member "{new_name}" not found in DB')
                            return
                        new_mid = member_lookup[new_name]
                        update_assignment_member(aid, new_mid)
                        changes.append(f'{ds} | {evname} | {zone}: {old_name} → {new_name}')
                        break

        if changes:
            msg = f'Applied {len(changes)} changes:\n\n' + '\n'.join(changes)
            messagebox.showinfo('Done', msg)
        else:
            messagebox.showinfo('Info', 'No changes detected')

    def _parse_schedule_text(self, text: str) -> dict:
        """
        Parse the schedule text and extract (date, event_name, zone) -> member_name.
        Looks for patterns like "• Segunda, 01/01 – Culto de Ceia" and "Slide – Isaac".
        """
        result = {}
        lines = text.split('\n')

        current_date = None
        current_event = None

        for i, line in enumerate(lines):
            # Match event header: "• Weekday, dd/mm – Event Name"
            event_match = re.match(r'^• .+?, \d{2}/\d{2} – (.+)$', line.strip())
            if event_match:
                # Extract date from previous lines
                for j in range(i - 1, max(0, i - 5), -1):
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', lines[j])
                    if date_match:
                        current_date = date_match.group(1)
                        break
                current_event = event_match.group(1).strip()
                continue

            # Match zone assignments: "Slide – Name" or " Slide – Name"
            zone_match = re.match(r'^\s*(Slide|Luzes|Live)\s*–\s*(.+)$', line.strip())
            if zone_match and current_date and current_event:
                zone = zone_match.group(1).lower()
                member_name = zone_match.group(2).strip()
                if member_name != '—':  # Ignore empty assignments
                    result[(current_date, current_event, zone)] = member_name

        return result

