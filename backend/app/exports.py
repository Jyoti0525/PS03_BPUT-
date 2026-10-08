"""Triage note export: PDF, print (HTML), JSON, CSV, FHIR R4 document bundle, HL7 CDA R2 document."""

import csv
import io
import json
from datetime import datetime
from html import escape
from xml.etree import ElementTree as ET

from fpdf import FPDF

DISCLAIMER = (
    "Educational prototype for triage support only. Not a diagnosis. All content must be reviewed by a qualified medical "
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


CDA_NS, XSI = "urn:hl7-org:v3", "http://www.w3.org/2001/XMLSchema-instance"
LOINC = "2.16.840.1.113883.6.1"
JEEVIA_OID = "2.25.276318398723961874165418342187521543"  # UUID-derived OID for this prototype; not a registered root


def _cda_ts(s) -> str:
    d = s if isinstance(s, datetime) else datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else datetime.utcnow()
    return d.strftime("%Y%m%d%H%M%S")


def to_cda(e: dict, facility: dict | None) -> bytes:
    """HL7 CDA Release 2 document (LOINC 54094-8, Emergency department triage note). Narrative sections carry the
    whole note; vitals and report values are also structured entries. Status stays "active" until a doctor reviews."""
    ET.register_namespace("", CDA_NS)
    ET.register_namespace("xsi", XSI)
    q = lambda t: f"{{{CDA_NS}}}{t}"  # noqa: E731
    n, p = e.get("note") or {}, e["patient"]

    def el(parent, tag, text=None, **attrs):
        x = ET.SubElement(parent, q(tag), {k.rstrip("_"): str(v) for k, v in attrs.items()})
        if text is not None:
            x.text = str(text)
        return x

    doc = ET.Element(q("ClinicalDocument"))
    el(doc, "realmCode", code="IN")
    el(doc, "typeId", root="2.16.840.1.113883.1.3", extension="POCD_HD000040")
    el(doc, "id", root=JEEVIA_OID, extension=e["id"])
    el(doc, "code", code="54094-8", codeSystem=LOINC, codeSystemName="LOINC", displayName="Emergency department Triage note")
    el(doc, "title", "Jeevia triage note (non-diagnostic, " + (e.get("data_origin") or "SYNTHETIC").lower() + " data)")
    el(doc, "effectiveTime", value=_cda_ts(e["created_at"]))
    el(doc, "confidentialityCode", code="R", codeSystem="2.16.840.1.113883.5.25")
    el(doc, "languageCode", code="en-IN")
    role = el(el(doc, "recordTarget"), "patientRole")
    el(role, "id", root=JEEVIA_OID + ".1", extension=p["code"])
    pat = el(role, "patient")
    el(el(pat, "name"), "given", p["name"])
    el(pat, "administrativeGenderCode", code={"F": "F", "M": "M"}.get(p["sex"], "UN"), codeSystem="2.16.840.1.113883.5.1")
    author = el(doc, "author")
    el(author, "time", value=_cda_ts(e["created_at"]))
    dev = el(el(author, "assignedAuthor"), "assignedAuthoringDevice")
    author[1].insert(0, ET.Element(q("id"), {"root": JEEVIA_OID + ".2", "extension": "rules-engine"}))
    el(dev, "softwareName", "Jeevia triage assistant (rules engine; urgency is never set by a language model)")
    org = el(el(el(doc, "custodian"), "assignedCustodian"), "representedCustodianOrganization")
    el(org, "id", root=JEEVIA_OID + ".3", extension=(facility or {}).get("id", "demo"))
    el(org, "name", (facility or {}).get("name", "Demo facility"))
    if e.get("reviewed_by"):
        la = el(doc, "legalAuthenticator")
        el(la, "time", value=_cda_ts(e.get("reviewed_at")))
        el(la, "signatureCode", code="S")
        ae = el(la, "assignedEntity")
        el(ae, "id", root=JEEVIA_OID + ".4", extension=e["reviewed_by"])
        el(el(el(ae, "assignedPerson"), "name"), "given", e["reviewed_by"])
    body = el(el(doc, "component"), "structuredBody")

    def section(title, code=None, lines=(), rows=None, entries=()):
        sec = el(el(body, "component"), "section")
        if code:
            el(sec, "code", code=code[0], codeSystem=LOINC, codeSystemName="LOINC", displayName=code[1])
        el(sec, "title", title)
        text = el(sec, "text")
        if rows:
            tb = el(text, "table", border="1")
            tr = el(el(tb, "thead"), "tr")
            for h in rows[0]:
                el(tr, "th", h)
            tbody = el(tb, "tbody")
            for r in rows[1:]:
                tr = el(tbody, "tr")
                for c in r:
                    el(tr, "td", c)
        elif lines:
            lst = el(text, "list")
            for line in lines:
                el(lst, "item", line)
        else:
            text.text = "None."
        for v in entries:
            ob = el(el(sec, "entry", typeCode="DRIV"), "observation", classCode="OBS", moodCode="EVN")
            c = el(ob, "code", nullFlavor="OTH")
            el(c, "originalText", v["label"])
            el(ob, "statusCode", code="active" if v["needs_check"] else "completed")
            val = ET.SubElement(ob, q("value"), {f"{{{XSI}}}type": "ST"})
            val.text = f"{v['value']} {v.get('unit') or ''}".strip()
            el(ob, "interpretationCode", nullFlavor="OTH").append(_txt(q, f"{v['status']}; source {v['source']['engine']}"))
        return sec

    urg = e.get("urgency")
    section("Disclaimer", lines=[DISCLAIMER, origin_line(e)])
    section("Chief complaint", ("10154-3", "Chief complaint Narrative - Reported"), [e["chief_complaint"]])
    section("Triage urgency", None, [f"Rules-engine urgency: {LABEL.get(urg, 'not set')}" + (" (clinician override)" if e.get("urgency_source") == "override" else "")]
            + ([f"Override: {e['override']['from_urgency']} to {e['override']['to_urgency']} by {e['override']['by']}. Reason: {e['override']['reason']}"] if e.get("override") else []))
    section("Summary", None, [n.get("summary", "")] if n.get("summary") else [])
    vit = n.get("vitals", [])
    section("Vital signs", ("8716-3", "Vital signs"), rows=[["Sign", "Value", "Unit", "Needs checking", "Source"]] + [[v["label"], v["value"], v.get("unit") or "", "yes" if v["needs_check"] else "no", v["source"]["engine"]] for v in vit] if vit else None, entries=vit)
    labs = n.get("labs", [])
    section("Report values", ("30954-2", "Relevant diagnostic tests/laboratory data Narrative"), rows=[["Test", "Value", "Unit", "Reference", "Needs checking"]] + [[v["label"], v["value"], v.get("unit") or "", v.get("reference") or "", "yes" if v["needs_check"] else "no"] for v in labs] if labs else None, entries=labs)
    section("Flags", None, [f"[{f['severity'].upper()}] {f['label']} ({f['code']})" for f in n.get("flags", [])])
    section("Missing information", None, list(n.get("missing_info", [])))
    section("Rules fired", None, [f"{r['rule_id']} ({r['protocol']}): {r['description']} -> {r['urgency']}" for r in n.get("rules_fired", [])])
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(doc, encoding="utf-8")


def _txt(q, s: str):
    x = ET.Element(q("originalText"))
    x.text = s
    return x


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
    if fmt == "cda":
        return to_cda(e, facility), "application/xml", f"{base}.cda.xml"
    if fmt == "print":
        return to_print_html(e, facility).encode(), "text/html", f"{base}.html"
    return to_pdf(e, facility), "application/pdf", f"{base}.pdf"
