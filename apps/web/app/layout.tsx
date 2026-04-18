import type { Metadata } from "next";
import "./globals.css";
import "./prism-fallback.css";

export const metadata: Metadata = {
  title: "Prism — cited research matrix",
  description: "Multi-agent earnings + filings copilot (hackathon MVP)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
