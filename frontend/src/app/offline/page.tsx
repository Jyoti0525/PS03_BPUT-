import Link from "next/link";
import { WifiOff } from "lucide-react";

export const metadata = { title: "Offline" };

export default function Offline() {
  return (
    <div className="grid min-h-[calc(100vh-28px)] place-items-center p-6 text-center">
      <div className="max-w-sm">
        <WifiOff className="mx-auto size-12 text-subtle" />
        <h1 className="mt-4 text-2xl font-bold text-ink">You are offline</h1>
        <p className="mt-2 text-muted">This page needs a connection. The patient intake kiosk keeps working offline and syncs later.</p>
        <Link href="/kiosk" className="mt-6 inline-flex h-12 items-center rounded-xl bg-teal-700 px-5 font-semibold text-white">
          Open intake kiosk
        </Link>
      </div>
    </div>
  );
}
