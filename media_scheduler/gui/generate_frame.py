"""Schedule generation tab: controls, editable assignment table, and message preview."""

from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from media_scheduler.db.assignments import (
    list_assignments_db,
    list_coordinators_in_range,
    update_assignment_member,
)
from media_scheduler.db.members import list_members_db
from media_scheduler.export import export_assignments_csv
from media_scheduler.gui.date_picker import pick_date_dialog
from media_scheduler.scheduler.algorithm import generate_schedule_db
from media_scheduler.utils.formatting import format_month_message
from media_scheduler.utils.helpers import _safe_float, _safe_int


class GenerateFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.last_start = None
        self.last_end = None
        self.last_missing = []
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

        # --- editable assignment table (source of truth; the message below is
        # just a preview rendered FROM this data, never edited directly) ---
        ttk.Label(self, text='Assignments (double-click, or select + Edit, to change a member)').pack(
            anchor='w', padx=10, pady=(8, 0)
        )

        table_frm = ttk.Frame(self)
        table_frm.pack(fill='both', expand=False, padx=10, pady=(2, 4))

        self.tree = ttk.Treeview(
            table_frm, columns=('aid', 'date', 'event', 'zone', 'member'), show='headings', height=10
        )
        for h, w in [('aid', 0), ('date', 100), ('event', 320), ('zone', 70), ('member', 160)]:
            self.tree.heading(h, text=h if h != 'aid' else '')
            self.tree.column(h, width=w, stretch=(h != 'aid'))
        self.tree.column('aid', width=0, stretch=False)  # keep assignment id out of view, but addressable
        self.tree.pack(side='left', fill='both', expand=True)
        sb = ttk.Scrollbar(table_frm, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscroll=sb.set)
        self.tree.bind('<Double-1>', lambda _e: self.edit_selected_assignment())

        tbtns = ttk.Frame(self)
        tbtns.pack(fill='x', padx=10)
        ttk.Button(tbtns, text='Edit selected', command=self.edit_selected_assignment).pack(side='left', padx=4)

        # --- read-only preview of the message that would be sent ---
        ttk.Label(self, text='Message preview (auto-updates after edits above — not directly editable)').pack(
            anchor='w', padx=10, pady=(8, 0)
        )
        self.output = tk.Text(self, height=16)
        self.output.pack(fill='both', expand=True, padx=10, pady=(2, 8))
        self.output.configure(state='disabled')

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

        self.last_start = s
        self.last_end = e
        self.last_missing = res.get('missing', [])

        self._refresh_table_and_preview()

        rows = res.get('assignments', [])
        msg = f'{len(rows)} assignments created.'
        if self.last_missing:
            msg += f' Missing: {len(self.last_missing)}.'
        messagebox.showinfo('Done', msg)

    def _current_rows(self):
        """Fetch assignments for the last generated range straight from the DB.

        The DB is the single source of truth — no in-memory copy that could
        drift out of sync after an edit.
        """
        if not self.last_start or not self.last_end:
            return []
        return list(list_assignments_db(self.last_start, self.last_end))

    def _refresh_table_and_preview(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        db_rows = self._current_rows()
        for r in db_rows:
            self.tree.insert('', 'end', values=(r['aid'], r['evdate'], r['evname'], r['zone'], r['mname']))

        rows = [(r['evid'], r['evdate'], r['evname'], r['zone'], r['mid'], r['mname']) for r in db_rows]

        self.output.configure(state='normal')
        self.output.delete('1.0', 'end')

        if not rows and not self.last_missing:
            self.output.insert('end', 'No assignments created (no events in range?)\n')
            self.output.configure(state='disabled')
            return

        sdate = datetime.strptime(self.last_start, '%Y-%m-%d').date()
        edate = datetime.strptime(self.last_end, '%Y-%m-%d').date()
        month_label_map = {
            1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
            5: "maio", 6: "junho", 7: "julho", 8: "agosto",
            9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
        }
        month_label = month_label_map.get(sdate.month, "este mês") if sdate.month == edate.month else "este período"

        coords = list_coordinators_in_range(self.last_start, self.last_end)
        msg_text = format_month_message(rows, coords, month_label)
        self.output.insert('end', msg_text)

        if self.last_missing:
            self.output.insert('end', '\nMISSING (no available member found):\n')
            for (eid, ds, nm, zone) in self.last_missing:
                self.output.insert('end', f'  {ds} | {nm} | zone {zone}\n')

        self.output.configure(state='disabled')

    def _selected_assignment(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0])['values']

    def edit_selected_assignment(self):
        vals = self._selected_assignment()
        if not vals:
            messagebox.showerror('Error', 'Select an assignment first')
            return

        assignment_id = int(vals[0])
        ev_date, ev_name, zone, current_name = vals[1], vals[2], vals[3], vals[4]

        dlg = tk.Toplevel(self)
        dlg.title('Edit assignment')
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        body = ttk.Frame(dlg)
        body.pack(fill='both', expand=True, padx=12, pady=12)

        ttk.Label(body, text=f'{ev_date} | {ev_name}').grid(row=0, column=0, columnspan=2, sticky='w')
        ttk.Label(body, text=f'Zone: {zone}').grid(row=1, column=0, columnspan=2, sticky='w', pady=(0, 8))

        members = list_members_db()
        member_items = [m['name'] for m in members]
        member_lookup = {m['name']: int(m['id']) for m in members}

        ttk.Label(body, text='Member').grid(row=2, column=0, sticky='w')
        member_cb = ttk.Combobox(body, values=member_items, state='readonly', width=30)
        member_cb.grid(row=2, column=1, sticky='w', padx=(6, 0))
        if current_name in member_items:
            member_cb.set(current_name)
        elif member_items:
            member_cb.current(0)

        btns = ttk.Frame(body)
        btns.grid(row=3, column=0, columnspan=2, sticky='e', pady=(12, 0))

        def on_confirm():
            selected = member_cb.get().strip()
            if selected not in member_lookup:
                messagebox.showerror('Error', 'Select a valid member.', parent=dlg)
                return
            update_assignment_member(assignment_id, member_lookup[selected])
            dlg.destroy()
            self._refresh_table_and_preview()

        ttk.Button(btns, text='Cancel', command=dlg.destroy).pack(side='right', padx=(8, 0))
        ttk.Button(btns, text='Confirm', command=on_confirm).pack(side='right')

        dlg.wait_window()

    def export_csv(self):
        db_rows = self._current_rows()
        if not db_rows:
            messagebox.showerror('Error', 'No generated assignments to export')
            return
        rows = [(r['evid'], r['evdate'], r['evname'], r['zone'], r['mid'], r['mname']) for r in db_rows]
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')])
        if not path:
            return
        export_assignments_csv(path, rows)
        messagebox.showinfo('Saved', f'Exported to {path}')