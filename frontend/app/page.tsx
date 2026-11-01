import { StudyWorkspace } from "@/components/study-workspace";

export default function HomePage() {
  return (
    <>
      <a className="skip-link" href="#study-content">
        Ir para o conteúdo
      </a>

      <div className="app-shell min-h-screen">
      <header className="border-b border-border/80 bg-surface/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[90rem] items-center justify-between gap-4 px-5 py-4 sm:px-8">
          <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex size-10 items-center justify-center rounded-xl bg-accent text-sm font-bold text-white shadow-lg shadow-indigo-200"
          >
            CF
          </span>
          <div>
            <p className="font-bold tracking-tight">CogniFlow AI</p>
            <p className="text-sm text-muted">Seu espaço de aprendizagem visual</p>
          </div>
          </div>
          <span className="hidden items-center gap-2 rounded-full border border-border bg-background/80 px-3 py-1.5 text-xs font-semibold text-muted sm:flex">
            <span aria-hidden="true" className="size-2 rounded-full bg-emerald-500" />
            Ambiente de estudo
          </span>
        </div>
      </header>

      <main
        id="study-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-[90rem] px-5 py-10 sm:px-8 sm:py-14"
      >
        <div className="mb-10 grid items-end gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
          <div className="max-w-3xl space-y-4">
          <p className="inline-flex items-center gap-2 rounded-full bg-accent-soft px-3 py-1.5 text-xs font-bold uppercase tracking-[0.14em] text-accent">
            <span aria-hidden="true">✦</span> Aprendizagem visual com IA
          </p>
          <h1 className="text-4xl font-bold leading-[1.05] tracking-[-0.04em] sm:text-5xl lg:text-6xl">
            Transforme conteúdo em <span className="text-accent">conexões.</span>
          </h1>
          <p className="max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
            Envie seu material, faça uma pergunta e explore os conceitos em um
            mapa mental interativo — com tudo conectado ao seu documento.
          </p>
          </div>
          <div className="dot-grid hidden rounded-2xl border border-border bg-surface/70 p-5 lg:block">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted">Seu fluxo</p>
            <div className="mt-4 flex items-center gap-2 text-sm font-semibold">
              <span className="rounded-lg bg-accent-soft px-3 py-2 text-accent">PDF</span>
              <span aria-hidden="true" className="text-muted">→</span>
              <span className="rounded-lg bg-orange-50 px-3 py-2 text-[#c94627]">Tema</span>
              <span aria-hidden="true" className="text-muted">→</span>
              <span className="rounded-lg bg-emerald-50 px-3 py-2 text-emerald-700">Mapa</span>
            </div>
          </div>
        </div>

        <StudyWorkspace />
      </main>
      </div>
    </>
  );
}
