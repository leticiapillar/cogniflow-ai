import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "CogniFlow AI | Tutor de aula",
  description:
    "Tutor de aula para alunos neurodivergentes: mapa mental do PDF da aula e respostas às dúvidas com base no material.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
