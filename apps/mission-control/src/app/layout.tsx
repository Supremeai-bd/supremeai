import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { ApiGate } from "@/components/mission-control/api-gate";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SupremeAI · Mission Control",
  description:
    "Governed operator console for the SupremeAI autonomous task-execution platform — live tower telemetry, 106-tool MCP explorer, PR↔main conflict watching, brain & memory.",
  keywords: ["SupremeAI", "Mission Control", "MCP", "autonomous agents", "zero cost", "operator console"],
  authors: [{ name: "SupremeAI" }],
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
  openGraph: {
    title: "SupremeAI · Mission Control",
    description: "Governed autonomy console — zero cost, fast, intelligent, dynamic by design.",
    siteName: "SupremeAI",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#0b0f0d",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <ApiGate />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
