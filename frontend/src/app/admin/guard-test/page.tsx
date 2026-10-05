"use client";

import { useState } from "react";
import Link from "next/link";
import { FlaskConical, ShieldCheck, ShieldX, ScrollText } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, CardHeader, ErrorNote, Label, Spinner, Textarea } from "@/components/ui";
import type { GuardTestResult } from "@/lib/types";

const LANG: Record<string, string> = { en: "English", hi: "Hindi", "hi-Latn": "Hindi (romanised)", or: "Odia" };

/** C4 demo step 5: a person types (or picks) a sentence and sees the output guard block it. Clearly a test, never a
 *  model output; nothing here reaches a patient's note. */
export default function GuardTestPage() {
  const { tr } = usePrefs();
  const samples = useAsync(() => api.guardTestSamples(), []);
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ text: string; r: GuardTestResult } | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function run(t = text, s = source) {
    if (!t.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setResult({ text: t, r: await api.guardTest(t, s) });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title={tr("Output guard test")}
        subtitle={tr("Every sentence the AI model writes for a note passes this guard. Type a sentence here, or pick one, to see what it blocks.")}
      />
      <div className="mb-4 flex items-start gap-2 rounded-xl border border-semi-line bg-semi-bg px-4 py-2.5 text-sm font-medium text-semi">
        <FlaskConical className="mt-0.5 size-4 shrink-0" />
        {tr("Test only. These sentences are typed by a person, not written by the AI model, and nothing here is added to any patient's note.")}
      </div>

      <Card className="p-4">
        <Label htmlFor="guard-text">{tr("Sentence to check")}</Label>
        <Textarea id="guard-text" rows={3} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)} placeholder={tr("e.g. Fever for 4 days, likely dengue.")} />
        <div className="mt-3">
          <Label htmlFor="guard-source" hint={tr("Optional. A phrase already in this data may be repeated, as in a real summary.")}>{tr("Data the model was given")}</Label>
          <Textarea id="guard-source" rows={2} maxLength={2000} value={source} onChange={(e) => setSource(e.target.value)} placeholder={tr("e.g. Chronic check-in. Condition: diabetes.")} />
        </div>
        <div className="mt-3 flex justify-end">
          <Button variant="teal" loading={busy} disabled={!text.trim()} icon={<ShieldCheck className="size-4" />} onClick={() => run()}>
            {tr("Run guard test")}
          </Button>
        </div>
      </Card>

      {error ? <div className="mt-4"><ErrorNote error={error} /></div> : null}

      {result && (
        <Card className={`mt-4 border-2 ${result.r.ok ? "border-rout-line" : "border-crit-line"}`}>
          <CardHeader
            icon={result.r.ok ? <ShieldCheck className="size-4 text-rout" /> : <ShieldX className="size-4 text-crit" />}
            title={result.r.ok ? tr("Passed — this sentence could appear in a note") : tr("Blocked — this sentence would never reach a note")}
            action={<Badge tone="semi">{tr("Test")}</Badge>}
          />
          <div className="space-y-3 px-4 pb-4 text-sm">
            <p className="rounded-lg bg-canvas px-3 py-2 text-ink-2">“{result.text}”</p>
            {result.r.hits.length > 0 && (
              <ul className="space-y-1.5">
                {result.r.hits.map((h) => (
                  <li key={h.category + h.phrase} className="flex flex-wrap items-center gap-2">
                    <Badge tone="crit">{tr(h.label)}</Badge>
                    <span className="font-mono text-ink">“{h.phrase}”</span>
                  </li>
                ))}
              </ul>
            )}
            {!result.r.ok && <p className="text-muted">{tr("In a real summary the whole AI text is dropped, the rules-based template note is used instead, and the rejected text is kept on the note for the reviewer.")}</p>}
            <p className="flex items-center gap-2 text-xs text-subtle">
              <ScrollText className="size-3.5" />
              {tr(result.r.ok ? "Written to the audit log as a test." : "Written to the audit log as GUARD_BLOCK, marked as a test.")}{" "}
              <Link href="/admin/audit" className="font-medium text-teal-700 underline">{tr("Open audit log")}</Link>
              <span>· {tr("Guard version")} {result.r.guard_version}</span>
            </p>
          </div>
        </Card>
      )}

      <Card className="mt-4">
        <CardHeader title={tr("Sentences from the red-team set")} subtitle={tr("Written by the team to test the guard; synthetic, no patient data.")} />
        {samples.error ? <div className="p-4"><ErrorNote error={samples.error} onRetry={samples.reload} /></div> : !samples.data ? <Spinner /> : (
          <ul className="divide-y divide-line">
            {samples.data.samples.map((s) => (
              <li key={s.text + (s.source ?? "")}>
                <button
                  type="button"
                  className="flex w-full flex-wrap items-center gap-2 px-4 py-2.5 text-left text-sm hover:bg-canvas/60"
                  onClick={() => { setText(s.text); setSource(s.source ?? ""); run(s.text, s.source ?? ""); }}
                >
                  <Badge tone={s.expect === "block" ? "crit" : "rout"}>{tr(s.expect === "block" ? "Should block" : "Should pass")}</Badge>
                  <Badge>{tr(LANG[s.language] ?? s.language)}</Badge>
                  <span className="min-w-0 flex-1 text-ink">{s.text}</span>
                  {s.source && <span className="w-full pl-1 text-xs text-subtle">{tr("Data given")}: {s.source}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
