"use client";

import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { usePrefs } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { ErrorNote, Spinner } from "@/components/ui";
import { DutyList } from "@/components/staff/duty";

export default function DeskStaff() {
  const { tr } = usePrefs();
  const { data, error, loading, reload } = useAsync(() => api.listUsers(), []);
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={tr("Doctors & nurses")} subtitle={tr("Mark who is on duty so waiting patients are routed and the queue stays realistic. Every change is recorded.")} />
      {error ? <ErrorNote error={error} onRetry={reload} /> : loading && !data ? <Spinner /> : <DutyList staff={data} onChange={reload} />}
    </div>
  );
}
