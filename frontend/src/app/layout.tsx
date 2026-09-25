import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { DisclaimerBar } from "@/components/layout/chrome";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

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

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="min-h-full">
        <Providers>
          <DisclaimerBar />
          {children}
        </Providers>
      </body>
    </html>
  );
}
