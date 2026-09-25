"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync, useOnline } from "@/lib/hooks";
import { Card, ErrorNote, Label, Select, Spinner } from "@/components/ui";

import { IntakeFlow } from "@/components/intake/intake-flow";

export default function NewProblem() {
  const online = useOnline();
  const { data, error } = useAsync(() => Promise.all([api.myRecord(), api.listFacilities()]), []);
  const [fid, setFid] = useState("fac_phc_manikpur");
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Spinner />;
  const [record, facilities] = data;
  return (
    <div className="space-y-4">
      <Card className="mx-auto max-w-3xl p-4">
        <Label htmlFor="fac">Health centre you will visit</Label>
        <Select id="fac" value={fid} onChange={(e) => setFid(e.target.value)}>
          {facilities.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name} — {f.district}
            </option>
          ))}
        </Select>
      </Card>
      <IntakeFlow key={fid} mode="patient" facilityId={fid} fixedPatient={record.patient} offline={!online} />
    </div>
  );
}
