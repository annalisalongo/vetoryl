from __future__ import annotations

import calendar
import json
import math
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Monitor Vetoryl di Zoe",
    page_icon="💊",
    layout="wide",
)

CONFIG_PATH = Path("zoe_vetoryl_config.json")


@dataclass
class MedicationConfig:
    label: str
    strength_mg: int
    purchase_date: date
    boxes_bought: int
    pills_per_box: int
    pills_per_day: int


@dataclass
class MedicationPlan:
    label: str
    strength_mg: int
    purchase_date: date
    boxes_bought: int
    pills_per_box: int
    pills_per_day: int
    total_pills: int
    coverage_days: int
    finish_date: date
    recipe_date: date
    reorder_date: date
    remaining_pills: int
    remaining_boxes_equivalent: float
    days_left: int
    status: str
    next_action: str


DEFAULTS = {
    "reference_date": date.today().isoformat(),
    "dose_already_given": False,
    "recipe_lead_days": 10,
    "reorder_lead_days": 5,
    "med_10": {
        "purchase_date": "2026-04-02",
        "boxes_bought": 2,
        "pills_per_box": 30,
        "pills_per_day": 2,
    },
    "med_5": {
        "purchase_date": "2026-04-08",
        "boxes_bought": 2,
        "pills_per_box": 30,
        "pills_per_day": 2,
    },
}


def load_saved_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULTS.copy()
    return DEFAULTS.copy()


if "config_loaded" not in st.session_state:
    st.session_state.config_loaded = load_saved_config()


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


cfg = st.session_state.config_loaded


def get_remaining_pills(
    total_pills: int,
    pills_per_day: int,
    purchase_date: date,
    reference_date: date,
    dose_already_given: bool,
) -> int:
    if reference_date < purchase_date:
        return total_pills

    elapsed_days = (reference_date - purchase_date).days
    consumed_days = elapsed_days + 1 if dose_already_given else elapsed_days
    consumed_days = max(consumed_days, 0)
    consumed_pills = min(total_pills, consumed_days * pills_per_day)
    return max(total_pills - consumed_pills, 0)


def build_plan(
    med: MedicationConfig,
    recipe_lead_days: int,
    reorder_lead_days: int,
    reference_date: date,
    dose_already_given: bool,
) -> MedicationPlan:
    total_pills = med.boxes_bought * med.pills_per_box
    coverage_days = max(total_pills // med.pills_per_day, 0)
    finish_date = med.purchase_date + timedelta(days=max(coverage_days - 1, 0))
    recipe_date = finish_date - timedelta(days=recipe_lead_days)
    reorder_date = finish_date - timedelta(days=reorder_lead_days)
    remaining_pills = get_remaining_pills(
        total_pills=total_pills,
        pills_per_day=med.pills_per_day,
        purchase_date=med.purchase_date,
        reference_date=reference_date,
        dose_already_given=dose_already_given,
    )

    if remaining_pills == 0 and reference_date >= med.purchase_date:
        days_left = 0
    else:
        days_left = math.ceil(remaining_pills / med.pills_per_day)

    remaining_boxes_equivalent = (
        remaining_pills / med.pills_per_box if med.pills_per_box else 0
    )

    if reference_date > finish_date:
        status = "Scorta finita"
        next_action = "Riordino urgente"
    elif reference_date >= reorder_date:
        status = "Da riordinare"
        next_action = "Riordina adesso"
    elif reference_date >= recipe_date:
        status = "Richiedi ricetta"
        next_action = "Contatta il veterinario"
    else:
        status = "Coperta"
        next_action = f"Nessuna urgenza fino al {recipe_date.strftime('%d/%m/%Y')}"

    return MedicationPlan(
        label=med.label,
        strength_mg=med.strength_mg,
        purchase_date=med.purchase_date,
        boxes_bought=med.boxes_bought,
        pills_per_box=med.pills_per_box,
        pills_per_day=med.pills_per_day,
        total_pills=total_pills,
        coverage_days=coverage_days,
        finish_date=finish_date,
        recipe_date=recipe_date,
        reorder_date=reorder_date,
        remaining_pills=remaining_pills,
        remaining_boxes_equivalent=remaining_boxes_equivalent,
        days_left=days_left,
        status=status,
        next_action=next_action,
    )


MONTH_NAMES_IT = {
    1: "Gennaio",
    2: "Febbraio",
    3: "Marzo",
    4: "Aprile",
    5: "Maggio",
    6: "Giugno",
    7: "Luglio",
    8: "Agosto",
    9: "Settembre",
    10: "Ottobre",
    11: "Novembre",
    12: "Dicembre",
}


def google_calendar_url(title: str, event_date: date, details: str = "") -> str:
    start = event_date.strftime("%Y%m%d")
    end = (event_date + timedelta(days=1)).strftime("%Y%m%d")
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start}/{end}",
        "details": details,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def render_calendar_html(year: int, month: int, events: dict[date, list[str]], today: date) -> str:
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)
    weekdays = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

    html = [
        """
        <style>
        .zoe-calendar {width: 100%; border-collapse: collapse; table-layout: fixed;}
        .zoe-calendar th {padding: 10px 6px; border-bottom: 1px solid #d9d9d9; text-align: center;}
        .zoe-calendar td {vertical-align: top; min-height: 120px; height: 120px; border: 1px solid #ececec; padding: 6px;}
        .zoe-muted {color: #999999; background: #fafafa;}
        .zoe-day {font-weight: 700; margin-bottom: 6px;}
        .zoe-today {outline: 2px solid #ffb347; border-radius: 8px; padding: 2px 6px; display: inline-block;}
        .zoe-chip {display: block; border-radius: 999px; padding: 3px 8px; margin-top: 4px; font-size: 0.78rem; line-height: 1.2; background: #f1f3f5;}
        .zoe-chip.recipe {background: #fff3cd;}
        .zoe-chip.reorder {background: #d1ecf1;}
        .zoe-chip.finish {background: #f8d7da;}
        .zoe-chip.buy {background: #d4edda;}
        </style>
        """
    ]
    html.append('<table class="zoe-calendar">')
    html.append("<thead><tr>" + "".join(f"<th>{d}</th>" for d in weekdays) + "</tr></thead>")
    html.append("<tbody>")

    for week in weeks:
        html.append("<tr>")
        for day in week:
            muted = "zoe-muted" if day.month != month else ""
            html.append(f'<td class="{muted}">')
            day_class = "zoe-day"
            day_html = str(day.day)
            if day == today:
                day_html = f'<span class="zoe-today">{day.day}</span>'
            html.append(f'<div class="{day_class}">{day_html}</div>')
            for label in events.get(day, []):
                cls = ""
                upper = label.upper()
                if "RICETTA" in upper:
                    cls = "recipe"
                elif "RIORDINO" in upper:
                    cls = "reorder"
                elif "FINE" in upper:
                    cls = "finish"
                elif "ACQUISTO" in upper:
                    cls = "buy"
                html.append(f'<span class="zoe-chip {cls}">{label}</span>')
            html.append("</td>")
        html.append("</tr>")
    html.append("</tbody></table>")
    return "".join(html)


st.title("💊 Monitor Vetoryl di Zoe")
st.caption(
    "Tieni sotto controllo scorte, date chiave e prossima ricetta per Vetoryl 10 mg e 5 mg."
)

with st.sidebar:
    st.header("Impostazioni")
    reference_date = st.date_input(
        "Situazione al giorno",
        value=parse_date(cfg["reference_date"]),
        format="DD/MM/YYYY",
        help="La data per cui vuoi vedere quante compresse restano.",
    )
    dose_already_given = st.checkbox(
        "Dose del giorno già somministrata",
        value=cfg["dose_already_given"],
        help="Se attivo, il conteggio scala anche la dose completa della data selezionata.",
    )
    st.divider()
    recipe_lead_days = st.number_input(
        "Anticipo per richiesta ricetta (giorni)",
        min_value=0,
        max_value=60,
        value=int(cfg["recipe_lead_days"]),
        step=1,
    )
    reorder_lead_days = st.number_input(
        "Anticipo per riordino (giorni)",
        min_value=0,
        max_value=60,
        value=int(cfg["reorder_lead_days"]),
        step=1,
    )

    st.divider()
    save_clicked = st.button("Salva configurazione")
    reset_clicked = st.button("Ripristina dati iniziali")

if reset_clicked:
    st.session_state.config_loaded = DEFAULTS.copy()
    st.rerun()

col10, col5 = st.columns(2)

with col10:
    st.subheader("Vetoryl 10 mg")
    purchase_10 = st.date_input(
        "Data acquisto 10 mg",
        value=parse_date(cfg["med_10"]["purchase_date"]),
        format="DD/MM/YYYY",
        key="purchase_10",
    )
    boxes_10 = st.number_input(
        "Scatole acquistate 10 mg",
        min_value=0,
        max_value=20,
        value=int(cfg["med_10"]["boxes_bought"]),
        step=1,
        key="boxes_10",
    )
    pills_box_10 = st.number_input(
        "Pasticche per scatola 10 mg",
        min_value=1,
        max_value=500,
        value=int(cfg["med_10"]["pills_per_box"]),
        step=1,
        key="pills_box_10",
    )
    per_day_10 = st.number_input(
        "Pasticche al giorno 10 mg",
        min_value=1,
        max_value=20,
        value=int(cfg["med_10"]["pills_per_day"]),
        step=1,
        key="per_day_10",
    )

with col5:
    st.subheader("Vetoryl 5 mg")
    purchase_5 = st.date_input(
        "Data acquisto 5 mg",
        value=parse_date(cfg["med_5"]["purchase_date"]),
        format="DD/MM/YYYY",
        key="purchase_5",
    )
    boxes_5 = st.number_input(
        "Scatole acquistate 5 mg",
        min_value=0,
        max_value=20,
        value=int(cfg["med_5"]["boxes_bought"]),
        step=1,
        key="boxes_5",
    )
    pills_box_5 = st.number_input(
        "Pasticche per scatola 5 mg",
        min_value=1,
        max_value=500,
        value=int(cfg["med_5"]["pills_per_box"]),
        step=1,
        key="pills_box_5",
    )
    per_day_5 = st.number_input(
        "Pasticche al giorno 5 mg",
        min_value=1,
        max_value=20,
        value=int(cfg["med_5"]["pills_per_day"]),
        step=1,
        key="per_day_5",
    )

config_to_save = {
    "reference_date": reference_date.isoformat(),
    "dose_already_given": dose_already_given,
    "recipe_lead_days": int(recipe_lead_days),
    "reorder_lead_days": int(reorder_lead_days),
    "med_10": {
        "purchase_date": purchase_10.isoformat(),
        "boxes_bought": int(boxes_10),
        "pills_per_box": int(pills_box_10),
        "pills_per_day": int(per_day_10),
    },
    "med_5": {
        "purchase_date": purchase_5.isoformat(),
        "boxes_bought": int(boxes_5),
        "pills_per_box": int(pills_box_5),
        "pills_per_day": int(per_day_5),
    },
}

if save_clicked:
    CONFIG_PATH.write_text(json.dumps(config_to_save, indent=2), encoding="utf-8")
    st.session_state.config_loaded = config_to_save
    st.sidebar.success("Configurazione salvata nel file locale zoe_vetoryl_config.json")

plan_10 = build_plan(
    MedicationConfig(
        label="Vetoryl 10 mg",
        strength_mg=10,
        purchase_date=purchase_10,
        boxes_bought=int(boxes_10),
        pills_per_box=int(pills_box_10),
        pills_per_day=int(per_day_10),
    ),
    recipe_lead_days=int(recipe_lead_days),
    reorder_lead_days=int(reorder_lead_days),
    reference_date=reference_date,
    dose_already_given=dose_already_given,
)

plan_5 = build_plan(
    MedicationConfig(
        label="Vetoryl 5 mg",
        strength_mg=5,
        purchase_date=purchase_5,
        boxes_bought=int(boxes_5),
        pills_per_box=int(pills_box_5),
        pills_per_day=int(per_day_5),
    ),
    recipe_lead_days=int(recipe_lead_days),
    reorder_lead_days=int(reorder_lead_days),
    reference_date=reference_date,
    dose_already_given=dose_already_given,
)

plans = [plan_10, plan_5]

summary_cols = st.columns(4)
summary_cols[0].metric(
    "Prossima richiesta ricetta",
    min(p.recipe_date for p in plans).strftime("%d/%m/%Y"),
)
summary_cols[1].metric(
    "Prossimo riordino",
    min(p.reorder_date for p in plans).strftime("%d/%m/%Y"),
)
summary_cols[2].metric(
    "Prima scadenza scorte",
    min(p.finish_date for p in plans).strftime("%d/%m/%Y"),
)
summary_cols[3].metric(
    "Situazione al",
    reference_date.strftime("%d/%m/%Y"),
)

upcoming_events = []
for p in plans:
    upcoming_events.extend(
        [
            (p.recipe_date, f"Richiedi ricetta per {p.label}"),
            (p.reorder_date, f"Riordina {p.label}"),
            (p.finish_date, f"Fine scorta {p.label}"),
        ]
    )
upcoming_events.sort(key=lambda x: x[0])

past_due = [event for event in upcoming_events if event[0] < reference_date]
future_or_today = [event for event in upcoming_events if event[0] >= reference_date]

if any(p.status == "Scorta finita" for p in plans):
    st.error("Attenzione: almeno una scorta è già finita rispetto alla data selezionata.")
elif any(p.status == "Da riordinare" for p in plans):
    first = min((p for p in plans if p.status == "Da riordinare"), key=lambda x: x.finish_date)
    st.warning(f"È il momento di riordinare: priorità a **{first.label}**.")
elif any(p.status == "Richiedi ricetta" for p in plans):
    first = min((p for p in plans if p.status == "Richiedi ricetta"), key=lambda x: x.recipe_date)
    st.info(f"Conviene richiedere la ricetta adesso, partendo da **{first.label}**.")
else:
    next_date, next_label = future_or_today[0]
    st.success(f"Tutto sotto controllo. Prossimo passaggio: **{next_label}** il **{next_date.strftime('%d/%m/%Y')}**.")

st.divider()
st.subheader("Dettaglio per dosaggio")

detail_cols = st.columns(2)
for idx, plan in enumerate(plans):
    with detail_cols[idx]:
        st.markdown(f"### {plan.label}")
        kpi_cols = st.columns(3)
        kpi_cols[0].metric("Pasticche residue", plan.remaining_pills)
        kpi_cols[1].metric("Giorni coperti rimasti", plan.days_left)
        kpi_cols[2].metric("Stato", plan.status)

        st.write(
            {
                "Data acquisto": plan.purchase_date.strftime("%d/%m/%Y"),
                "Scatole": plan.boxes_bought,
                "Pasticche per scatola": plan.pills_per_box,
                "Pasticche al giorno": plan.pills_per_day,
                "Copertura totale (giorni)": plan.coverage_days,
                "Richiedi ricetta": plan.recipe_date.strftime("%d/%m/%Y"),
                "Riordina": plan.reorder_date.strftime("%d/%m/%Y"),
                "Fine scorta": plan.finish_date.strftime("%d/%m/%Y"),
                "Equivalente scatole residue": f"{plan.remaining_boxes_equivalent:.2f}",
                "Prossima azione": plan.next_action,
            }
        )

st.divider()
st.subheader("Agenda scadenze")

agenda_rows = []
for p in plans:
    agenda_rows.extend(
        [
            {"Data": p.purchase_date, "Evento": f"Acquisto {p.label}", "Dosaggio": f"{p.strength_mg} mg"},
            {"Data": p.recipe_date, "Evento": "Richiesta ricetta", "Dosaggio": f"{p.strength_mg} mg"},
            {"Data": p.reorder_date, "Evento": "Riordino", "Dosaggio": f"{p.strength_mg} mg"},
            {"Data": p.finish_date, "Evento": "Fine scorta", "Dosaggio": f"{p.strength_mg} mg"},
        ]
    )

agenda_df = pd.DataFrame(agenda_rows).sort_values(["Data", "Dosaggio", "Evento"]).reset_index(drop=True)
agenda_df["Data"] = agenda_df["Data"].apply(lambda d: d.strftime("%d/%m/%Y"))
st.dataframe(agenda_df, use_container_width=True, hide_index=True)

csv_data = agenda_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Scarica agenda CSV",
    data=csv_data,
    file_name="agenda_vetoryl_zoe.csv",
    mime="text/csv",
)

st.divider()
st.subheader("Aggiungi a Google Calendar")
st.caption("Clicca un pulsante per aprire Google Calendar con l'evento già compilato.")

calendar_events = []
for p in plans:
    calendar_events.extend(
        [
            {
                "date": p.recipe_date,
                "title": f"Richiedi ricetta {p.label} per Zoe",
                "kind": "Richiesta ricetta",
                "dosaggio": f"{p.strength_mg} mg",
                "details": (
                    f"Zoe prende {p.pills_per_day} pasticche al giorno di {p.label}. "
                    f"Richiedere la ricetta per {p.boxes_bought} scatole da {p.strength_mg} mg."
                ),
            },
            {
                "date": p.reorder_date,
                "title": f"Riordina {p.label} per Zoe",
                "kind": "Riordino",
                "dosaggio": f"{p.strength_mg} mg",
                "details": (
                    f"Riordinare {p.boxes_bought} scatole di {p.label} per Zoe. "
                    f"Scorta prevista in esaurimento il {p.finish_date.strftime('%d/%m/%Y')}."
                ),
            },
        ]
    )

calendar_events.sort(key=lambda e: (e["date"], e["kind"], e["dosaggio"]))

for event in calendar_events:
    date_label = event["date"].strftime("%d/%m/%Y")
    button_label = f"{event['kind']} {event['dosaggio']} · {date_label}"
    st.link_button(
        button_label,
        google_calendar_url(
            title=event["title"],
            event_date=event["date"],
            details=event["details"],
        ),
        use_container_width=True,
    )

st.divider()
st.subheader("Vista calendario")

all_dates = sorted({
    plan_10.purchase_date,
    plan_10.recipe_date,
    plan_10.reorder_date,
    plan_10.finish_date,
    plan_5.purchase_date,
    plan_5.recipe_date,
    plan_5.reorder_date,
    plan_5.finish_date,
    reference_date,
})

month_options = []
for d in all_dates:
    label = f"{MONTH_NAMES_IT[d.month]} {d.year}"
    value = (d.year, d.month)
    if value not in month_options:
        month_options.append(value)

selected_month = st.selectbox(
    "Mese da visualizzare",
    options=month_options,
    format_func=lambda ym: f"{MONTH_NAMES_IT[ym[1]]} {ym[0]}",
)

events_map: dict[date, list[str]] = {}
for p in plans:
    events_map.setdefault(p.purchase_date, []).append(f"Acquisto {p.strength_mg} mg")
    events_map.setdefault(p.recipe_date, []).append(f"Ricetta {p.strength_mg} mg")
    events_map.setdefault(p.reorder_date, []).append(f"Riordino {p.strength_mg} mg")
    events_map.setdefault(p.finish_date, []).append(f"Fine {p.strength_mg} mg")

calendar_html = render_calendar_html(
    year=selected_month[0],
    month=selected_month[1],
    events=events_map,
    today=reference_date,
)
st.markdown(calendar_html, unsafe_allow_html=True)

st.caption(
    "Suggerimento: quando compri nuove scatole, aggiorna la data di acquisto e il numero di scatole, poi salva la configurazione."
)
