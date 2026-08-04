import type { Metadata, Viewport } from "next";
import { JetBrains_Mono, Space_Grotesk, Unbounded } from "next/font/google";
import "./globals.css";

const display = Unbounded({
  subsets: ["latin"],
  weight: ["500", "700", "900"],
  variable: "--font-display",
  display: "swap",
});

const body = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://castiron.edycu.dev"),
  title: "CastIron — TTS Failover Podcast Pipeline on B2",
  description:
    "Self-healing podcast pipeline on Genblaze + Backblaze B2 — a cross-provider TTS failover ladder that keeps shipping when a vendor dies. 96/96, 0 dropped.",
  applicationName: "CastIron",
  authors: [{ name: "Edy Cu" }],
  manifest: "/site.webmanifest",
  alternates: { canonical: "/" },
  keywords: [
    "TTS failover",
    "podcast pipeline",
    "generative media reliability",
    "text-to-speech fallback",
    "Backblaze B2 Object Lock",
    "Genblaze pipeline",
    "audio provenance",
    "tamper-evident media",
    "self-healing pipeline",
    "ElevenLabs outage",
  ],
  openGraph: {
    type: "website",
    url: "https://castiron.edycu.dev",
    siteName: "CastIron",
    title: "Your TTS provider just died. The episode still ships.",
    description:
      "Cross-provider TTS failover + provenance sealed in the MP3, Object-Locked on Backblaze B2. 96/96 shipped, 0 dropped.",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "CastIron — zero dropped episodes" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Your TTS provider just died. The episode still ships.",
    description:
      "Self-healing audio-episode factory on Genblaze + Backblaze B2. 96/96 shipped hash-verified, 0 dropped.",
    images: ["/og-image.png"],
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#070B0E",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        {children}
        <div className="noise-overlay" aria-hidden="true" />
      </body>
    </html>
  );
}
