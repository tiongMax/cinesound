import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CineSound",
  description: "AI-paired movie and music recommendations",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
