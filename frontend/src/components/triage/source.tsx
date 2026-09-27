"use client";

import { usePrefs } from "@/components/providers";
import { useEffect, useState } from "react";
import { FileImage, Mic, Cpu, PenLine, Maximize2 } from "lucide-react";
import { api } from "@/lib/api";
import type { ExtractedValue, FileObject, SourceRef } from "@/lib/types";
import { Modal, cx } from "@/components/ui";

const cache = new Map<string, Promise<FileObject>>();
function loadFile(id: string) {
  if (!cache.has(id)) cache.set(id, api.getFile(id).catch((e) => { cache.delete(id); throw e; }));
  return cache.get(id)!;
}

export function useFile(id?: string | null) {
  const [file, setFile] = useState<FileObject | null>(null);
  useEffect(() => {
    if (!id) return;
    let live = true;
    loadFile(id).then((f) => live && setFile(f)).catch(() => {});
    return () => {
      live = false;
    };
  }, [id]);
  return file;
}

function useNatural(url?: string | null) {
  const [dim, setDim] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    if (!url) return;
    const img = new Image();
    img.onload = () => setDim({ w: img.naturalWidth || 640, h: img.naturalHeight || 400 });
    img.src = url;
  }, [url]);
  return dim;
}

/** Shows exactly the region of the source image a value was extracted from. */
export function Crop({ url, bbox, className }: { url: string; bbox: [number, number, number, number]; className?: string }) {
  const { tr } = usePrefs();
  const dim = useNatural(url);
  if (!dim) return <div className={cx("h-10 animate-pulse rounded-md bg-canvas", className)} />;
  const [x, y, w, h] = bbox;
  return (
    <div
      className={cx("w-full rounded-md border border-line bg-no-repeat", className)}
      style={{
        aspectRatio: `${w * dim.w} / ${h * dim.h}`,
        backgroundImage: `url("${url}")`,
        backgroundSize: `${100 / w}% auto`,
        backgroundPosition: `${w >= 1 ? 0 : (x / (1 - w)) * 100}% ${h >= 1 ? 0 : (y / (1 - h)) * 100}%`,
      }}
      role="img"
      aria-label={tr("Cropped region of the source report")}
    />
  );
}

export function SourceIcon({ kind }: { kind: SourceRef["kind"] }) {
  const Icon = { image_crop: FileImage, transcript: Mic, sensor: Cpu, manual: PenLine }[kind];
  return <Icon className="size-3.5" aria-hidden />;
}

/** Inline evidence beside a value: crop for OCR, excerpt for transcripts, device for sensors. */
export function SourceEvidence({ v, compact }: { v: ExtractedValue; compact?: boolean }) {
  const { tr } = usePrefs();
  const s = v.source;
  const file = useFile(s.kind === "image_crop" ? s.file_id : null);
  const [open, setOpen] = useState(false);

  if (s.kind === "image_crop") {
    return (
      <>
        <button onClick={() => setOpen(true)} className="group relative block w-full text-left" title={tr("Open full report with this region highlighted")}>
          {file?.url && s.bbox ? (
            <Crop url={file.url} bbox={s.bbox} className={compact ? "max-h-9" : ""} />
          ) : (
            <span className="block rounded-md border border-dashed border-line px-2 py-1.5 font-mono text-[11px] text-muted">{file?.purged_at ? tr("Source image purged (retention)") : s.crop_text ?? tr("Image")}</span>
          )}
          <Maximize2 className="absolute top-1 right-1 size-3.5 text-muted opacity-0 group-hover:opacity-100" />
        </button>
        <Modal open={open} onClose={() => setOpen(false)} title={`${v.label}: ${v.value}${v.unit ? " " + v.unit : ""}`} subtitle={`${s.engine} · ${file?.filename ?? ""}`} size="lg">
          {file?.url ? (
            <div className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={file.url} alt="Source report" className="w-full rounded-lg border border-line" />
              {s.bbox && (
                <span
                  className="absolute rounded-sm border-2 border-coral-500 bg-coral-300/20"
                  style={{ left: `${s.bbox[0] * 100}%`, top: `${s.bbox[1] * 100}%`, width: `${s.bbox[2] * 100}%`, height: `${s.bbox[3] * 100}%` }}
                />
              )}
            </div>
          ) : (
            <p className="text-sm text-muted">{tr("The source image is no longer available (retention policy) or could not be loaded.")}</p>
          )}
          <p className="mt-3 text-xs text-muted">{tr("Highlighted box = pixels the value was read from. Values that disagree between engines are marked “needs checking”.")}</p>
        </Modal>
      </>
    );
  }
  if (s.kind === "transcript") {
    return (
      <div className="rounded-md border border-line bg-canvas px-2 py-1.5 text-[11px] leading-snug text-muted">
        <span className="font-medium text-ink-2">“{s.transcript_excerpt}”</span>
        {s.original_excerpt && s.original_excerpt !== s.transcript_excerpt && <span className="mt-0.5 block italic">{s.original_excerpt}</span>}
      </div>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-muted">
      <SourceIcon kind={s.kind} /> {s.engine}
    </span>
  );
}
