import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CogniFlow AI - Visual Learning Platform",
  description: "Translating dense academic text into accessible visual mind maps.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-50 text-slate-900 min-h-screen">
        {children}
      </body>
    </html>
  );
}

