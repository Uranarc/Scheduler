"""Formatting helpers for event titles and month schedule message output."""

from datetime import datetime

from media_scheduler.utils.helpers import _format_pt_date, _pt_weekday_name


def _format_event_title(ev_name: str) -> str:
    base = (ev_name or "").strip()
    if " - " in base:
        base = base.split(" - ")[0].strip()

    mapping = {
        "Ceia": "Culto de Ceia",
        "Culto de Mulheres": "Culto das Mulheres",
        "Culto da Família": "Culto da Família",
        "Culto da Palavra": "Culto da Palavra",
        "Quarta em Família": "Quarta em Família",
        "Revolution": "Revolution",
    }
    return mapping.get(base, base)


def format_month_message(assign_rows, coordinators_map: dict[int, str], month_label: str) -> str:
    month_label_map = {
        1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
        5: "maio", 6: "junho", 7: "julho", 8: "agosto",
        9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
    }

    if assign_rows:
        month_keys = sorted({
            (datetime.strptime(ds, "%Y-%m-%d").date().year, datetime.strptime(ds, "%Y-%m-%d").date().month)
            for (_, ds, _, _, _, _) in assign_rows
        })
        labels = [month_label_map.get(mm, str(mm)) for (_, mm) in month_keys]
        if len(labels) == 1:
            resolved_month_label = labels[0]
        elif len(labels) == 2:
            resolved_month_label = f"{labels[0]} e {labels[1]}"
        else:
            resolved_month_label = ", ".join(labels[:-1]) + f" e {labels[-1]}"
    else:
        resolved_month_label = month_label or "este mês"

    intro = (
        "Paz do Senhor Jesus pessoal, como vocês estão?\n"
        f"Vou deixar aqui a nova escala do mês de {resolved_month_label}.\n\n"
        "Desde já agradeço a todos pelo empenho, e reforço que quem não puder cumprir a escala, "
        "por gentileza, faça a troca necessária com a devida antecedência.\n\n"
        "Deus abençoe a todos! 🙌\n\n"
    )

    grouped = {}
    for (eid, ds, evname, zone, mid, mname) in assign_rows:
        key = (ds, eid, evname)
        grouped.setdefault(key, {})[zone] = mname

    keys_sorted = sorted(grouped.keys(), key=lambda k: k[0])

    out = [intro]
    for (ds, eid, evname) in keys_sorted:
        d = datetime.strptime(ds, "%Y-%m-%d").date()
        weekday = _pt_weekday_name(d)
        ddmm = _format_pt_date(d)
        title = _format_event_title(evname)

        out.append(f"• {weekday}, {ddmm} – {title}\n\n")

        coord = coordinators_map.get(eid, "—")
        out.append(f" Coordenador(a) – {coord}\n")

        zone_map = grouped[(ds, eid, evname)]
        slide = zone_map.get("slide", "—")
        luzes = zone_map.get("luzes", "—")
        live = zone_map.get("live", "—")

        out.append(f" Slide – {slide}\n")
        out.append(f" Luzes – {luzes}\n")
        out.append(f" Live – {live}\n\n")

    return "".join(out)


