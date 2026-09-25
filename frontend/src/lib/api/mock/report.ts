/**
 * Renders a synthetic lab slip as an SVG so source-traceability crops point at real pixels.
 * Every row's bounding box is returned normalised to 0..1 so the UI can crop it.
 */
export interface ReportRow {
  test: string;
  value: string;
  unit: string;
  ref: string;
}

const W = 640;
const ROW_H = 34;
const TOP = 150;

function esc(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function renderLabReport(opts: {
  lab: string;
  patient: string;
  date: string;
  rows: ReportRow[];
  handwritten?: boolean;
}): { dataUrl: string; boxes: [number, number, number, number][] } {
  const H = TOP + opts.rows.length * ROW_H + 90;
  const font = opts.handwritten ? "'Comic Sans MS','Segoe Print',cursive" : "Courier New, monospace";
  const rows = opts.rows
    .map((r, i) => {
      const y = TOP + i * ROW_H;
      return `<g font-family="${font}" font-size="15" fill="#1f2937">
  <text x="32" y="${y + 22}">${esc(r.test)}</text>
  <text x="330" y="${y + 22}" font-weight="700">${esc(r.value)} ${esc(r.unit)}</text>
  <text x="480" y="${y + 22}" fill="#6b7280" font-size="13">${esc(r.ref)}</text>
  <line x1="24" y1="${y + ROW_H}" x2="${W - 24}" y2="${y + ROW_H}" stroke="#e5e7eb"/>
</g>`;
    })
    .join("\n");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
<rect width="${W}" height="${H}" fill="#fffdf7"/>
<rect x="8" y="8" width="${W - 16}" height="${H - 16}" fill="none" stroke="#d6d3d1"/>
<text x="32" y="48" font-family="Georgia,serif" font-size="22" font-weight="700" fill="#0f172a">${esc(opts.lab)}</text>
<text x="32" y="72" font-family="Arial" font-size="12" fill="#b91c1c">SYNTHETIC SAMPLE — NOT A REAL PATIENT RECORD</text>
<text x="32" y="104" font-family="Arial" font-size="14" fill="#334155">Patient: ${esc(opts.patient)}</text>
<text x="400" y="104" font-family="Arial" font-size="14" fill="#334155">Date: ${esc(opts.date)}</text>
<g font-family="Arial" font-size="12" font-weight="700" fill="#475569">
  <text x="32" y="138">TEST</text><text x="330" y="138">RESULT</text><text x="480" y="138">REFERENCE</text>
</g>
${rows}
<text x="32" y="${H - 36}" font-family="Arial" font-size="12" fill="#64748b">Authorised signatory · Jeevia demo data generator</text>
</svg>`;
  const boxes = opts.rows.map((_, i) => {
    const y = TOP + i * ROW_H;
    return [16 / W, (y - 2) / H, (W - 32) / W, (ROW_H + 4) / H] as [number, number, number, number];
  });
  const dataUrl = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
  return { dataUrl, boxes };
}
