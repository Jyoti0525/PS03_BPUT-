"use client";

import { useMemo, useState } from "react";
import { FileUp, Search, UserMinus, UserPlus, Users } from "lucide-react";
import { PageHeader } from "@/components/layout/app-shell";
import { api, ApiError } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { Badge, Button, Card, Empty, ErrorNote, FieldError, Input, Label, Modal, Select, Spinner, Textarea } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { FITNESS } from "@/components/employer/status";
import type { Worker, WorkerInput } from "@/lib/types";

const EMPTY: WorkerInput = { employee_code: "", name: "", age: 30, sex: "M", department: "", phone: "" };
const SAMPLE_CSV = "employee_code,name,age,sex,department,phone\nEMP-001,Ravi Kumar,34,M,Blast furnace,9876500001\nEMP-002,Sunita Das,29,F,Quality lab,";

const msg = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong");

export default function WorkersPage() {
  const { data, error, loading, reload } = useAsync(() => api.listWorkers(), []);
  const [q, setQ] = useState("");
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);
  const [removing, setRemoving] = useState<Worker | null>(null);
  const [form, setForm] = useState<WorkerInput>(EMPTY);
  const [csv, setCsv] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ created: number; updated: number; errors: string[] } | null>(null);

  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (data ?? []).filter((w) => !t || w.employee_code.toLowerCase().includes(t) || w.name.toLowerCase().includes(t) || (w.department ?? "").toLowerCase().includes(t));
  }, [data, q]);

  async function add() {
    setErr(null);
    if (form.employee_code.trim().length < 2 || form.name.trim().length < 2) return setErr("Employee code and name are required");
    if (form.phone && !/^\d{10}$/.test(form.phone)) return setErr("Phone must be 10 digits");
    setBusy(true);
    try {
      await api.addWorker({ ...form, employee_code: form.employee_code.trim(), name: form.name.trim(), department: form.department || null, phone: form.phone || null });
      toast(`${form.name} added to the roster`);
      setForm(EMPTY);
      setAdding(false);
      reload();
    } catch (e) {
      setErr(msg(e));
    } finally {
      setBusy(false);
    }
  }

  async function doImport() {
    setErr(null);
    if (!csv.trim()) return setErr("Paste CSV rows or choose a file");
    setBusy(true);
    try {
      const r = await api.importWorkers(csv);
      setResult(r);
      toast(`Imported: ${r.created} new, ${r.updated} updated`);
      reload();
    } catch (e) {
      setErr(msg(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(w: Worker) {
    setBusy(true);
    try {
      await api.removeWorker(w.employee_code);
      toast(`${w.employee_code} removed from the roster`);
      setRemoving(null);
      reload();
    } catch (e) {
      toast(msg(e), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title="Worker roster"
        subtitle="Workers on this roster are linked when they visit your health centre (by employee code). You see fitness outcomes only."
        actions={
          <div className="flex gap-2">
            <Button variant="secondary" icon={<FileUp className="size-4" />} onClick={() => { setErr(null); setResult(null); setImporting(true); }}>
              Import CSV
            </Button>
            <Button icon={<UserPlus className="size-4" />} onClick={() => { setErr(null); setAdding(true); }}>
              Add worker
            </Button>
          </div>
        }
      />
      {error ? (
        <ErrorNote error={error} onRetry={reload} />
      ) : loading && !data ? (
        <Spinner />
      ) : !data?.length ? (
        <Card>
          <Empty icon={<Users className="size-6" />} title="No workers yet" body="Add workers one by one or import your HR sheet as CSV." />
        </Card>
      ) : (
        <Card>
          <div className="border-b border-line p-3">
            <div className="relative max-w-sm">
              <Search className="absolute top-3.5 left-3 size-4 text-subtle" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search code, name, department" className="pl-9" aria-label="Search workers" />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs tracking-wide text-muted uppercase">
                  <th className="px-4 py-2 font-semibold">Code</th>
                  <th className="px-4 py-2 font-semibold">Name</th>
                  <th className="px-4 py-2 font-semibold">Department</th>
                  <th className="px-4 py-2 font-semibold">Fitness</th>
                  <th className="px-4 py-2 font-semibold">Valid until</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((w) => (
                  <tr key={w.employee_code}>
                    <td className="px-4 py-2.5 font-mono text-ink">{w.employee_code}</td>
                    <td className="px-4 py-2.5 text-ink">{w.name}</td>
                    <td className="px-4 py-2.5 text-muted">{w.department ?? "—"}</td>
                    <td className="px-4 py-2.5">
                      <Badge tone={FITNESS[w.fitness_status].tone}>{FITNESS[w.fitness_status].label}</Badge>
                      {w.restrictions && <p className="mt-0.5 text-xs text-muted">{w.restrictions}</p>}
                    </td>
                    <td className="px-4 py-2.5 text-muted">{w.valid_until ? new Date(w.valid_until).toLocaleDateString("en-IN") : "—"}</td>
                    <td className="px-4 py-2.5 text-right">
                      <Button size="sm" variant="ghost" icon={<UserMinus className="size-4" />} onClick={() => setRemoving(w)} aria-label={`Remove ${w.employee_code}`}>
                        Remove
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Modal
        open={adding}
        onClose={() => setAdding(false)}
        title="Add worker"
        footer={
          <>
            <Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
            <Button onClick={add} loading={busy}>Add to roster</Button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="w-code">Employee code</Label>
            <Input id="w-code" value={form.employee_code} onChange={(e) => setForm({ ...form, employee_code: e.target.value.toUpperCase() })} placeholder="EMP-1041" />
          </div>
          <div>
            <Label htmlFor="w-name">Full name</Label>
            <Input id="w-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="w-age">Age</Label>
            <Input id="w-age" type="number" min={14} max={100} value={form.age} onChange={(e) => setForm({ ...form, age: Number(e.target.value) })} />
          </div>
          <div>
            <Label htmlFor="w-sex">Sex</Label>
            <Select id="w-sex" value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value as WorkerInput["sex"] })}>
              <option value="M">Male</option>
              <option value="F">Female</option>
              <option value="O">Other</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="w-dept" hint="(optional)">Department</Label>
            <Input id="w-dept" value={form.department ?? ""} onChange={(e) => setForm({ ...form, department: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="w-phone" hint="(optional)">Mobile</Label>
            <Input id="w-phone" inputMode="numeric" value={form.phone ?? ""} onChange={(e) => setForm({ ...form, phone: e.target.value.replace(/\D/g, "").slice(0, 10) })} />
          </div>
        </div>
        <FieldError>{err}</FieldError>
      </Modal>

      <Modal
        open={importing}
        onClose={() => setImporting(false)}
        size="lg"
        title="Import workers from CSV"
        subtitle="Columns: employee_code, name, age, sex, department, phone. Existing codes are updated."
        footer={
          <>
            <Button variant="ghost" onClick={() => setImporting(false)}>Close</Button>
            <Button onClick={doImport} loading={busy}>Import</Button>
          </>
        }
      >
        <div className="space-y-3">
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="CSV file"
            className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-teal-50 file:px-3 file:py-2 file:font-medium file:text-teal-800"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (f) setCsv(await f.text());
            }}
          />
          <Textarea rows={8} value={csv} onChange={(e) => setCsv(e.target.value)} placeholder={SAMPLE_CSV} className="font-mono text-xs" aria-label="CSV rows" />
          <button className="text-xs font-semibold text-teal-700" onClick={() => setCsv(SAMPLE_CSV)}>
            Insert example rows
          </button>
          <FieldError>{err}</FieldError>
          {result && (
            <div className="rounded-xl bg-canvas p-3 text-sm">
              <p className="font-semibold text-ink">
                {result.created} added · {result.updated} updated
              </p>
              {result.errors.length > 0 && (
                <ul className="mt-2 list-disc pl-5 text-xs text-crit">
                  {result.errors.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </Modal>

      <Modal
        open={!!removing}
        onClose={() => setRemoving(null)}
        size="sm"
        title={`Remove ${removing?.employee_code}?`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRemoving(null)}>Cancel</Button>
            <Button variant="danger" loading={busy} onClick={() => removing && remove(removing)}>Remove</Button>
          </>
        }
      >
        <p className="text-sm text-ink-2">The worker is unlinked from your organisation. Their own health record stays with them and the health centre; you stop seeing their fitness status.</p>
      </Modal>
    </div>
  );
}
