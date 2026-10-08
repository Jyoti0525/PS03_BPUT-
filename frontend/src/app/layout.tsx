import type { Metadata, Viewport } from "next";
import { Inter, Noto_Sans_Ol_Chiki } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { DisclaimerBar } from "@/components/layout/chrome";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
// Santali in Ol Chiki: not on most Android tablets; fetched only when Ol Chiki text is on screen (unicode-range).
const olChiki = Noto_Sans_Ol_Chiki({ variable: "--font-olchiki", subsets: ["ol-chiki"], preload: false });

export const metadata: Metadata = {
  title: { default: "Jeevia — Triage support", template: "%s · Jeevia" },
  description:
    "Human-in-the-loop multimodal triage assistant for government and institutional health facilities. Educational prototype — not a diagnostic tool.",
  applicationName: "Jeevia",
  appleWebApp: { capable: true, title: "Jeevia", statusBarStyle: "default" },
  icons: { icon: "/favicon-48.png", apple: "/apple-touch-icon.png" },
};

export const viewport: Viewport = {
  themeColor: "#16182b",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${olChiki.variable} h-full`}>
      <body className="min-h-full">
        <Providers>
          <DisclaimerBar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
