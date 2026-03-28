"""CSV export utilities for generated assignments."""


def export_assignments_csv(path: str, rows):
    import csv
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['event_id', 'date', 'event_name', 'zone', 'member_id', 'member_name'])
        for r in rows:
            w.writerow(r)

