"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, X } from "lucide-react";
import jsQR from "jsqr";
import { usePrefs } from "@/components/providers";
import { Button, Card, CardHeader } from "@/components/ui";

type Detector = { detect(src: CanvasImageSource): Promise<{ rawValue: string }[]> };

export function QrScanner({ onCode, onClose, title = "Scan patient QR" }: { onCode: (code: string) => void; onClose: () => void; title?: string }) {
  const { tr } = usePrefs();
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const onCodeRef = useRef(onCode);
  const onCloseRef = useRef(onClose);
  const trRef = useRef(tr);
  const [msg, setMsg] = useState("Starting camera…");
  useEffect(() => { onCodeRef.current = onCode; }, [onCode]);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);
  useEffect(() => { trRef.current = tr; }, [tr]);
  useEffect(() => {
    let stream: MediaStream | null = null;
    let raf = 0;
    let stopped = false;
    let lastFrameAt = 0;
    (async () => {
      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          setMsg(trRef.current("Camera access is unavailable here. Open this page over HTTPS or type the patient ID instead."));
          return;
        }
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (!video.current) return;
        video.current.srcObject = stream;
        await video.current.play();
        setMsg(trRef.current("Point the camera at the patient's token QR"));
        const BD = (window as unknown as { BarcodeDetector?: new (o: { formats: string[] }) => Detector }).BarcodeDetector;
        let det: Detector | null = null;
        try { if (BD) det = new BD({ formats: ["qr_code"] }); } catch { /* jsQR is the universal fallback */ }
        const tick = async () => {
          if (stopped || !video.current) return;
          if (video.current.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && performance.now() - lastFrameAt > 120) {
            lastFrameAt = performance.now();
            try {
              const codes = det ? await det.detect(video.current) : [];
              if (codes[0]?.rawValue) {
                stopped = true;
                onCodeRef.current(codes[0].rawValue);
                return;
              }
            } catch { det = null; }
            const frame = video.current;
            const target = canvas.current;
            if (target && frame.videoWidth && frame.videoHeight) {
              const scale = Math.min(1, 960 / frame.videoWidth);
              target.width = Math.round(frame.videoWidth * scale);
              target.height = Math.round(frame.videoHeight * scale);
              const context = target.getContext("2d", { willReadFrequently: true });
              if (context) {
                context.drawImage(frame, 0, 0, target.width, target.height);
                const image = context.getImageData(0, 0, target.width, target.height);
                const code = jsQR(image.data, image.width, image.height, { inversionAttempts: "attemptBoth" });
                if (code?.data) {
                  stopped = true;
                  onCodeRef.current(code.data);
                  return;
                }
              }
            }
          }
          raf = requestAnimationFrame(tick);
        };
        tick();
      } catch (e) {
        const name = e instanceof DOMException ? e.name : "";
        setMsg(trRef.current(name === "NotAllowedError" ? "Camera permission denied. Allow camera access and try again, or type the patient ID instead." : name === "NotFoundError" ? "No camera was found on this device. Type the patient ID instead." : "Could not start the camera. Check camera access and try again."));
      }
    })();
    return () => {
      stopped = true;
      cancelAnimationFrame(raf);
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  return (
    <Card className="overflow-hidden">
      <CardHeader title={tr(title)} subtitle={msg} icon={<Camera className="size-4" />} action={<Button size="sm" variant="ghost" onClick={() => onCloseRef.current()} icon={<X className="size-4" />}>{tr("Close")}</Button>} />
      <video ref={video} className="aspect-video w-full bg-ink object-cover" muted playsInline />
      <canvas ref={canvas} className="hidden" aria-hidden="true" />
    </Card>
  );
}
