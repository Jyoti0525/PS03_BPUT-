import type { Encounter, ExportFormat, Facility } from "@/lib/types";

export const URGENCY_LABEL = { red: "Critical", yellow: "Semi-urgent", green: "Routine" } as const;

export const DISCLAIMER =
  "Educational prototype for triage support only. Not a diagnosis. All content must be reviewed by a qualified medical professional. Synthetic data.";

/** Plain-text lines of a triage note; the base for PDF, print and referral text. */
export function noteLines(e: Encounter, facility?: Facility | null): string[] {
  const n = e.note;
  const p = e.patient;
  const L: string[] = [];
  L.push("JEEVIA TRIAGE NOTE");
  L.push(DISCLAIMER);
  L.push("");
  L.push(`Patient: ${p.name} (${p.code})  Age/Sex: ${p.age}/${p.sex}  Language: ${p.language}`);
  if (facility) L.push(`Facility: ${facility.name}, ${facility.district}, ${facility.state}`);
  L.push(`Captured: ${new Date(e.created_at).toLocaleString("en-IN")}  Visit type: ${e.category}`);
  if (e.urgency) L.push(`Rules-engine urgency: ${URGENCY_LABEL[e.urgency]}${e.urgency_source === "override" ? " (clinician override)" : ""}`);
  if (e.override) L.push(`Override: ${e.override.from_urgency} -> ${e.override.to_urgency} by ${e.override.by}. Reason: ${e.override.reason}`);
  L.push(`Chief complaint: ${e.chief_complaint}`);
  if (!n) return L;
  L.push("");
  L.push("SUMMARY");
  L.push(n.summary);
  if (n.flags.length) {
    L.push("");
    L.push("FLAGS");
    n.flags.forEach((f) => L.push(`- [${f.severity.toUpperCase()}] ${f.label} (${f.code})`));
  }
  if (n.vitals.length) {
    L.push("");
    L.push("VITALS");
    n.vitals.forEach((v) => L.push(`- ${v.label}: ${v.value}${v.unit ? " " + v.unit : ""}${v.needs_check ? "  [NEEDS CHECKING]" : ""}  (source: ${v.source.engine})`));
  }
  if (n.labs.length) {
    L.push("");
    L.push("REPORT VALUES");
    n.labs.forEach((v) => L.push(`- ${v.label}: ${v.value}${v.unit ? " " + v.unit : ""} (ref ${v.reference ?? "-"})${v.needs_check ? "  [NEEDS CHECKING]" : ""}`));
  }
  if (n.disagreements.length) {
    L.push("");
    L.push("SOURCE DISAGREEMENTS");
    n.disagreements.forEach((d) => L.push(`- ${d.field}: ${d.values.map((v) => `${v.engine} ${v.value}`).join(" vs ")}. ${d.action}`));
  }
  if (n.timeline.length) {
    L.push("");
    L.push("TIMELINE");
    n.timeline.forEach((t) => L.push(`- ${t.when}: ${t.event}`));
  }
  if (n.missing_info.length) {
    L.push("");
    L.push("MISSING INFORMATION");
    n.missing_info.forEach((m) => L.push(`- ${m}`));
  }
  L.push("");
  L.push("RULES FIRED");
  n.rules_fired.forEach((r) => L.push(`- ${r.rule_id} (${r.protocol}): ${r.description} -> ${r.urgency}`));
  if (e.reviewed_by) {
    L.push("");
    L.push(`Reviewed by ${e.reviewed_by} at ${new Date(e.reviewed_at!).toLocaleString("en-IN")}`);
  }
  return L;
}

export function toCsv(e: Encounter): string {
  const rows: string[][] = [["section", "label", "value", "unit", "reference", "needs_check", "source"]];
  const n = e.note;
  rows.push(["patient", "code", e.patient.code, "", "", "", ""]);
  rows.push(["patient", "age_sex", `${e.patient.age}/${e.patient.sex}`, "", "", "", ""]);
  rows.push(["encounter", "urgency", e.urgency ?? "", "", "", "", e.urgency_source]);
  rows.push(["encounter", "chief_complaint", e.chief_complaint, "", "", "", ""]);
  n?.vitals.forEach((v) => rows.push(["vital", v.label, v.value, v.unit ?? "", v.reference ?? "", String(v.needs_check), v.source.engine]));
  n?.labs.forEach((v) => rows.push(["lab", v.label, v.value, v.unit ?? "", v.reference ?? "", String(v.needs_check), v.source.engine]));
  n?.flags.forEach((f) => rows.push(["flag", f.code, f.label, "", "", "", f.severity]));
  return rows.map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(",")).join("\n");
}

/** Minimal FHIR R4 document bundle: Composition + Patient + Observations. */
export function toFhir(e: Encounter) {
  const obs = [...(e.note?.vitals ?? []), ...(e.note?.labs ?? [])].map((v) => ({
    fullUrl: `urn:uuid:${v.id}`,
    resource: {
      resourceType: "Observation",
      id: v.id,
      status: v.needs_check ? "preliminary" : "final",
      code: { text: v.label },
      subject: { reference: `Patient/${e.patient.id}` },
      valueString: `${v.value}${v.unit ? " " + v.unit : ""}`,
      interpretation: [{ text: v.status }],
      note: [{ text: `Source: ${v.source.engine}` }],
    },
  }));
  return {
    resourceType: "Bundle",
    type: "document",
    timestamp: new Date().toISOString(),
    meta: { tag: [{ system: "https://jeevia.example/tags", code: "synthetic", display: "Synthetic demo data" }] },
    entry: [
      {
        fullUrl: `urn:uuid:${e.id}`,
        resource: {
          resourceType: "Composition",
          id: e.id,
          status: e.reviewed_by ? "final" : "preliminary",
          type: { text: "Triage note (non-diagnostic)" },
          subject: { reference: `Patient/${e.patient.id}` },
          date: e.created_at,
          title: "Jeevia triage note",
          section: [
            { title: "Summary", text: { status: "generated", div: `<div xmlns="http://www.w3.org/1999/xhtml">${e.note?.summary ?? ""}</div>` } },
            { title: "Flags", text: { status: "generated", div: `<div xmlns="http://www.w3.org/1999/xhtml">${(e.note?.flags ?? []).map((f) => f.label).join("; ")}</div>` } },
          ],
          extension: [{ url: "https://jeevia.example/fhir/urgency", valueCode: e.urgency ?? "unknown" }],
        },
      },
      {
        fullUrl: `urn:uuid:${e.patient.id}`,
        resource: {
          resourceType: "Patient",
          id: e.patient.id,
          identifier: [{ system: "https://jeevia.example/patient-code", value: e.patient.code }],
          name: [{ text: e.patient.name }],
          gender: e.patient.sex === "F" ? "female" : e.patient.sex === "M" ? "male" : "other",
        },
      },
      ...obs,
    ],
  };
}

function htmlEsc(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function toPrintHtml(e: Encounter, facility?: Facility | null): string {
  const body = noteLines(e, facility)
    .map((l) => (l === "" ? "<br/>" : /^[A-Z][A-Z ]+$/.test(l) ? `<h3>${htmlEsc(l)}</h3>` : `<p>${htmlEsc(l)}</p>`))
    .join("\n");
  return `<!doctype html><html><head><meta charset="utf-8"><title>Triage note ${e.patient.code}</title>
<style>body{font:14px/1.5 system-ui,sans-serif;max-width:760px;margin:24px auto;color:#111}h3{margin:16px 0 4px;font-size:13px;letter-spacing:.06em;color:#444}p{margin:2px 0}</style>
</head><body>${body}<script>window.onload=()=>window.print()</script></body></html>`;
}

/** Dependency-free text PDF (Helvetica, A4, auto page breaks). Non-Latin-1 characters are transliterated. */
export function toPdf(lines: string[]): Blob {
  const clean = (s: string) =>
    s
      .replace(/₂/g, "2")
      .replace(/°/g, " deg ")
      .replace(/[–—]/g, "-")
      .replace(/[≥]/g, ">=")
      .replace(/[≤]/g, "<=")
      .replace(/[µ]/g, "u")
      .replace(/[^\x20-\x7E]/g, "?")
      .replace(/\\/g, "\\\\")
      .replace(/\(/g, "\\(")
      .replace(/\)/g, "\\)");
  const wrap = (s: string, n = 92) => {
    const out: string[] = [];
    let cur = "";
    for (const w of s.split(" ")) {
      if ((cur + " " + w).trim().length > n) {
        out.push(cur);
        cur = w;
      } else cur = (cur + " " + w).trim();
    }
    out.push(cur);
    return out;
  };
  const all = lines.flatMap((l) => (l === "" ? [""] : wrap(l)));
  const perPage = 58;
  const pages: string[][] = [];
  for (let i = 0; i < all.length; i += perPage) pages.push(all.slice(i, i + perPage));
  const objs: string[] = [];
  objs[1] = "<< /Type /Catalog /Pages 2 0 R >>";
  objs[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>";
  const kids: string[] = [];
  pages.forEach((pg, i) => {
    const pageId = 4 + i * 2;
    const contentId = pageId + 1;
    kids.push(`${pageId} 0 R`);
    const stream =
      "BT /F1 10 Tf 12 TL 50 800 Td " +
      pg.map((l, j) => `${j === 0 && i === 0 ? "/F1 13 Tf " : j === 1 && i === 0 ? "/F1 10 Tf " : ""}(${clean(l)}) '`).join(" ") +
      " ET";
    objs[pageId] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents ${contentId} 0 R >>`;
    objs[contentId] = `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`;
  });
  objs[2] = `<< /Type /Pages /Kids [${kids.join(" ")}] /Count ${pages.length} >>`;
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  for (let i = 1; i < objs.length; i++) {
    offsets[i] = out.length;
    out += `${i} 0 obj\n${objs[i]}\nendobj\n`;
  }
  const xref = out.length;
  out += `xref\n0 ${objs.length}\n0000000000 65535 f \n`;
  for (let i = 1; i < objs.length; i++) out += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objs.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return new Blob([out], { type: "application/pdf" });
}

export function buildExport(e: Encounter, format: ExportFormat, facility?: Facility | null) {
  const base = `jeevia-${e.patient.code}-${e.id.slice(-6)}`;
  switch (format) {
    case "json":
      return { filename: `${base}.json`, mime: "application/json", blob: new Blob([JSON.stringify(e, null, 2)], { type: "application/json" }) };
    case "csv":
      return { filename: `${base}.csv`, mime: "text/csv", blob: new Blob([toCsv(e)], { type: "text/csv" }) };
    case "fhir":
      return { filename: `${base}.fhir.json`, mime: "application/fhir+json", blob: new Blob([JSON.stringify(toFhir(e), null, 2)], { type: "application/fhir+json" }) };
    case "print":
      return { filename: `${base}.html`, mime: "text/html", blob: new Blob([toPrintHtml(e, facility)], { type: "text/html" }) };
    case "pdf":
      return { filename: `${base}.pdf`, mime: "application/pdf", blob: toPdf(noteLines(e, facility)) };
  }
}

/** Referral text built from the note and the facility's specialist configuration. */
export function referralText(e: Encounter, facility: Facility | null, destination: string, specialty: string, reason: string) {
  const n = e.note;
  const lines = [
    `REFERRAL NOTE — ${new Date().toLocaleString("en-IN")}`,
    `From: ${facility ? `${facility.name}, ${facility.district}` : "—"}`,
    `To: ${destination} (${specialty})`,
    "",
    `Patient: ${e.patient.name}, ${e.patient.age}/${e.patient.sex}, ID ${e.patient.code}, preferred language ${e.patient.language}`,
    `Reason for referral: ${reason}`,
    `Chief complaint: ${e.chief_complaint}`,
    e.urgency ? `Triage category (rules engine): ${URGENCY_LABEL[e.urgency]}` : "",
    "",
    "Summary:",
    n?.summary ?? "",
    "",
    "Key findings:",
    ...(n?.vitals ?? []).map((v) => `  ${v.label}: ${v.value}${v.unit ? " " + v.unit : ""}${v.needs_check ? " (needs re-check)" : ""}`),
    ...(n?.labs ?? []).filter((l) => l.status !== "normal").map((v) => `  ${v.label}: ${v.value}${v.unit ? " " + v.unit : ""} (ref ${v.reference})`),
    "",
    "Flags for receiving team:",
    ...(n?.flags ?? []).filter((f) => f.severity !== "info").map((f) => `  • ${f.label}`),
    ...(n?.missing_info.length ? ["", "Not yet available:", ...n.missing_info.map((m) => `  • ${m}`)] : []),
    "",
    DISCLAIMER,
  ];
  return lines.filter((l, i, a) => !(l === "" && a[i - 1] === "")).join("\n");
}

export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
