"""Triage note export: PDF, print (HTML), JSON, CSV, FHIR R4 document bundle."""

import csv
import io
import json
from datetime import datetime
from html import escape

from fpdf import FPDF

DISCLAIMER = (
    "Triage support only. Not a diagnosis. All content must be reviewed by a qualified medical "
    "professional before any clinical decision."
)
LABEL = {"red": "Critical", "yellow": "Semi-urgent", "green": "Routine"}


def origin_line(e: dict) -> str:
    """G8: every export says where its data came from."""
    o = e.get("data_origin") or "SYNTHETIC"
    return f"Data origin: {o} ({'synthetic demo data, no real patient' if o == 'SYNTHETIC' else 'public sample data'})"


def _dt(s) -> str:
    if isinstance(s, datetime):
        return s.strftime("%d/%m/%Y %H:%M")
    return str(s or "")


def note_lines(e: dict, facility: dict | None) -> list[str]:
    p, n = e["patient"], e.get("note")
    L = ["JEEVIA TRIAGE NOTE", DISCLAIMER, origin_line(e), ""]
    L.append(f"Patient: {p['name']} ({p['code']})  Age/Sex: {p['age']}/{p['sex']}  Language: {p['language']}")
    if facility:
        L.append(f"Facility: {facility['name']}, {facility['district']}, {facility['state']}")
    L.append(f"Captured: {_dt(e['created_at'])}  Visit type: {e['category']}")
    if e.get("urgency"):
        L.append(f"Rules-engine urgency: {LABEL[e['urgency']]}" + (" (clinician override)" if e.get("urgency_source") == "override" else ""))
    if e.get("override"):
        o = e["override"]
        L.append(f"Override: {o['from_urgency']} -> {o['to_urgency']} by {o['by']}. Reason: {o['reason']}")
    L.append(f"Chief complaint: {e['chief_complaint']}")
    if not n:
        return L
    L += ["", "SUMMARY", n["summary"]]
    if n["flags"]:
        L += ["", "FLAGS"] + [f"- [{f['severity'].upper()}] {f['label']} ({f['code']})" for f in n["flags"]]
    if n["vitals"]:
        L += ["", "VITALS"] + [f"- {v['label']}: {v['value']} {v.get('unit') or ''}{'  [NEEDS CHECKING]' if v['needs_check'] else ''}  (source: {v['source']['engine']})" for v in n["vitals"]]
    if n["labs"]:
        L += ["", "REPORT VALUES"] + [f"- {v['label']}: {v['value']} {v.get('unit') or ''} (ref {v.get('reference') or '-'}){'  [NEEDS CHECKING]' if v['needs_check'] else ''}" for v in n["labs"]]
    if n["disagreements"]:
        L += ["", "SOURCE DISAGREEMENTS"] + [f"- {d['field']}: " + " vs ".join(f"{x['engine']} {x['value']}" for x in d["values"]) + f". {d['action']}" for d in n["disagreements"]]
    if n["timeline"]:
        L += ["", "TIMELINE"] + [f"- {t['when']}: {t['event']}" for t in n["timeline"]]
    if n["missing_info"]:
        L += ["", "MISSING INFORMATION"] + [f"- {m}" for m in n["missing_info"]]
    L += ["", "RULES FIRED"] + [f"- {r['rule_id']} ({r['protocol']}): {r['description']} -> {r['urgency']}" for r in n["rules_fired"]]
    if e.get("reviewed_by"):
        L += ["", f"Reviewed by {e['reviewed_by']} at {_dt(e.get('reviewed_at'))}"]
    return L


def to_csv(e: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL)
    w.writerow(["section", "label", "value", "unit", "reference", "needs_check", "source"])
    w.writerow(["meta", "disclaimer", DISCLAIMER, "", "", "", ""])
    w.writerow(["meta", "data_origin", e.get("data_origin") or "SYNTHETIC", "", "", "", ""])
    w.writerow(["patient", "code", e["patient"]["code"], "", "", "", ""])
    w.writerow(["patient", "age_sex", f"{e['patient']['age']}/{e['patient']['sex']}", "", "", "", ""])
    w.writerow(["encounter", "urgency", e.get("urgency") or "", "", "", "", e.get("urgency_source")])
    w.writerow(["encounter", "chief_complaint", e["chief_complaint"], "", "", "", ""])
    n = e.get("note") or {}
    for v in n.get("vitals", []):
        w.writerow(["vital", v["label"], v["value"], v.get("unit") or "", v.get("reference") or "", v["needs_check"], v["source"]["engine"]])
    for v in n.get("labs", []):
        w.writerow(["lab", v["label"], v["value"], v.get("unit") or "", v.get("reference") or "", v["needs_check"], v["source"]["engine"]])
    for f in n.get("flags", []):
        w.writerow(["flag", f["code"], f["label"], "", "", "", f["severity"]])
    return buf.getvalue()


def to_fhir(e: dict) -> dict:
    n = e.get("note") or {}
    obs = [
        {
            "fullUrl": f"urn:uuid:{v['id']}",
            "resource": {
                "resourceType": "Observation",
                "id": v["id"],
                "status": "preliminary" if v["needs_check"] else "final",
                "code": {"text": v["label"]},
                "subject": {"reference": f"Patient/{e['patient']['id']}"},
                "valueString": f"{v['value']} {v.get('unit') or ''}".strip(),
                "interpretation": [{"text": v["status"]}],
                "note": [{"text": f"Source: {v['source']['engine']}"}],
            },
        }
        for v in [*n.get("vitals", []), *n.get("labs", [])]
    ]
    div = lambda s: f'<div xmlns="http://www.w3.org/1999/xhtml">{escape(s)}</div>'  # noqa: E731
    return {
        "resourceType": "Bundle",
        "type": "document",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "meta": {"tag": [{"system": "https://jeevia.example/tags", "code": (e.get("data_origin") or "SYNTHETIC").lower(), "display": origin_line(e)}]},
        "entry": [
            {
                "fullUrl": f"urn:uuid:{e['id']}",
                "resource": {
                    "resourceType": "Composition",
                    "id": e["id"],
                    "status": "final" if e.get("reviewed_by") else "preliminary",
                    "type": {"text": "Triage note (non-diagnostic)"},
                    "subject": {"reference": f"Patient/{e['patient']['id']}"},
                    "date": str(e["created_at"]),
                    "title": "Jeevia triage note",
                    "section": [
                        {"title": "Disclaimer", "text": {"status": "generated", "div": div(DISCLAIMER)}},
                        {"title": "Summary", "text": {"status": "generated", "div": div(n.get("summary", ""))}},
                        {"title": "Flags", "text": {"status": "generated", "div": div("; ".join(f["label"] for f in n.get("flags", [])))}},
                    ],
                    "extension": [{"url": "https://jeevia.example/fhir/urgency", "valueCode": e.get("urgency") or "unknown"}],
                },
            },
            {
                "fullUrl": f"urn:uuid:{e['patient']['id']}",
                "resource": {
                    "resourceType": "Patient",
                    "id": e["patient"]["id"],
                    "identifier": [{"system": "https://jeevia.example/patient-code", "value": e["patient"]["code"]}],
                    "name": [{"text": e["patient"]["name"]}],
                    "gender": {"F": "female", "M": "male"}.get(e["patient"]["sex"], "other"),
                },
            },
            *obs,
        ],
    }


def to_print_html(e: dict, facility: dict | None) -> str:
    rows = []
    for line in note_lines(e, facility):
        if not line:
            rows.append("<br/>")
        elif line.isupper():
            rows.append(f"<h3>{escape(line)}</h3>")
        else:
            rows.append(f"<p>{escape(line)}</p>")
    return (
        f'<!doctype html><html><head><meta charset="utf-8"><title>Triage note {escape(e["patient"]["code"])}</title>'
        "<style>body{font:14px/1.5 system-ui,sans-serif;max-width:760px;margin:24px auto;color:#111}"
        "h3{margin:16px 0 4px;font-size:13px;letter-spacing:.06em;color:#444}p{margin:2px 0}</style>"
        f"</head><body>{''.join(rows)}<script>window.onload=()=>window.print()</script></body></html>"
    )


_TRANS = str.maketrans({"₂": "2", "°": " deg ", "–": "-", "—": "-", "≥": ">=", "≤": "<=", "µ": "u", "→": "->", "•": "-", "’": "'", "“": '"', "”": '"', "…": "..."})


def _latin1(s: str) -> str:
    return s.translate(_TRANS).encode("latin-1", "replace").decode("latin-1")


def to_pdf(e: dict, facility: dict | None) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    lines = note_lines(e, facility)
    for i, line in enumerate(lines):
        if i == 0:
            pdf.set_font("Helvetica", "B", 15)
        elif i == 1:
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(160, 30, 30)
        elif line.isupper() and line:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(60, 60, 60)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(20, 20, 20)
        if not line:
            pdf.ln(3)
            continue
        pdf.multi_cell(0, 5.2, _latin1(line), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def build(e: dict, fmt: str, facility: dict | None) -> tuple[bytes, str, str]:
    base = f"jeevia-{e['patient']['code']}-{e['id'][-6:]}"
    if fmt == "json":
        body = {"disclaimer": DISCLAIMER, "data_origin": e.get("data_origin") or "SYNTHETIC", **e}
        return json.dumps(body, indent=2, default=str).encode(), "application/json", f"{base}.json"
    if fmt == "csv":
        return to_csv(e).encode(), "text/csv", f"{base}.csv"
    if fmt == "fhir":
        return json.dumps(to_fhir(e), indent=2, default=str).encode(), "application/fhir+json", f"{base}.fhir.json"
    if fmt == "print":
        return to_print_html(e, facility).encode(), "text/html", f"{base}.html"
    return to_pdf(e, facility), "application/pdf", f"{base}.pdf"
