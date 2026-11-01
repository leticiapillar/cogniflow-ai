import { useEffect, useId, useRef, useState } from "react";
import type { GenerateMapResponse, GenerationState } from "../types";
import { MindMapViewer } from "./mind-map-viewer";
import { MindMapOutline } from "./mind-map-outline";

function MindMapPresentation({ map }: { map: GenerateMapResponse }) {
  const [view, setView] = useState<"map" | "list">("map");
  const panelId = useId();
  const listPanel = useRef<HTMLDivElement>(null);
  const pendingListFocus = useRef(false);

  useEffect(() => {
    if (view === "list" && pendingListFocus.current) {
      listPanel.current?.focus();
      pendingListFocus.current = false;
    }
  }, [view]);

  const showListAfterFailure = () => {
    pendingListFocus.current = true;
    setView("list");
  };

  return (
    <div className="space-y-5">
      <div role="group" aria-label="Forma de leitura" className="inline-flex rounded-xl border border-border bg-background p-1">
        {(["map", "list"] as const).map((option) => (
          <button key={option} type="button" aria-pressed={view === option}
            aria-controls={`${panelId}-${option}`} onClick={() => setView(option)}
            className="rounded-lg px-4 py-2 text-sm font-semibold text-muted transition-colors aria-pressed:bg-surface aria-pressed:text-foreground aria-pressed:shadow-sm">
            {option === "map" ? "Mapa" : "Lista"}
          </button>
        ))}
      </div>

      <div id={`${panelId}-map`} hidden={view !== "map"}>
        <MindMapViewer map={map} onShowList={showListAfterFailure} />
      </div>

      <div id={`${panelId}-list`} ref={listPanel} hidden={view !== "list"}
        role="region" aria-label="Leitura textual do mapa" tabIndex={0}>
        <MindMapOutline map={map} />
      </div>
    </div>
  );
}

export function MindMapResult({ state }: { state: GenerationState }) {
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    if (state.status === "success") heading.current?.focus();
  }, [state]);

  const hasContext = state.status === "success" && state.map.source_chunks_used > 0;
  const statusMessage = state.status === "generating"
    ? "Gerando conceitos a partir do seu material…"
    : state.status === "error"
      ? "A geração não foi concluída. Revise a mensagem no formulário e tente novamente."
      : state.status === "success" && !hasContext
        ? "Nenhum trecho do documento foi recuperado. Revise a consulta ou envie novamente o PDF. Os conceitos não serão apresentados como baseados no seu material."
        : hasContext
          ? "Conceitos prontos para leitura."
          : "Envie um PDF e escolha um tema. Os conceitos aparecerão aqui.";

  return (
    <section
      aria-labelledby="mind-map-heading"
      className="surface-card min-w-0 overflow-hidden rounded-2xl p-5 sm:p-7"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-5">
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="flex size-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">✦</span>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted">Workspace visual</p>
            <h2 id="mind-map-heading" ref={heading} tabIndex={-1} className="text-xl font-semibold tracking-tight">Conceitos de estudo</h2>
          </div>
        </div>
        <span className="rounded-full border border-border bg-background px-3 py-1 text-xs font-semibold text-muted">
          React Flow
        </span>
      </div>
      <p role="status" aria-atomic="true" className="mt-4 text-sm leading-relaxed text-muted">
        {statusMessage}
      </p>

      {state.status !== "success" && (
        <div aria-hidden="true" className="dot-grid relative mt-6 hidden min-h-[27rem] overflow-hidden rounded-2xl border border-border bg-[#fafaff] sm:block">
          <div className="absolute left-[12%] top-[23%] w-40 rounded-xl border border-border bg-white p-4 shadow-lg">
            <span className="block h-2 w-14 rounded bg-accent/70" />
            <span className="mt-3 block h-2 w-24 rounded bg-border" />
          </div>
          <div className="absolute right-[12%] top-[20%] w-40 rounded-xl border border-border bg-white p-4 shadow-lg">
            <span className="block h-2 w-12 rounded bg-[#ff8a70]" />
            <span className="mt-3 block h-2 w-20 rounded bg-border" />
          </div>
          <div className="absolute bottom-[17%] left-1/2 w-44 -translate-x-1/2 rounded-xl border border-border bg-white p-4 shadow-lg">
            <span className="block h-2 w-16 rounded bg-emerald-400" />
            <span className="mt-3 block h-2 w-28 rounded bg-border" />
          </div>
          <svg className="absolute inset-0 size-full text-[#b7b4dc]" viewBox="0 0 700 430" preserveAspectRatio="none">
            <path d="M190 130 C280 130 270 320 350 320" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="5 7" />
            <path d="M510 125 C420 125 430 320 350 320" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="5 7" />
          </svg>
          <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center">
            <p className="text-sm font-semibold text-foreground">Seu mapa aparecerá aqui</p>
            <p className="mt-1 text-xs text-muted">Conceitos conectados ao conteúdo do PDF</p>
          </div>
        </div>
      )}

      {state.status === "success" && hasContext && (
        <div className="mt-6 space-y-5">
          <div className="break-words rounded-xl border border-border bg-background/70 p-4">
            <h3 className="text-lg font-semibold tracking-tight">{state.map.topic}</h3>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted">
              <p className="rounded-full border border-border bg-surface px-3 py-1.5">Documento: {state.request.document_name}</p>
              <p className="rounded-full border border-border bg-surface px-3 py-1.5">Consulta: {state.request.query}</p>
            </div>
            <p className="mt-3 text-sm text-muted">
              Baseado em {state.map.source_chunks_used} {state.map.source_chunks_used === 1 ? "trecho do documento" : "trechos do documento"}.
            </p>
          </div>
          <MindMapPresentation key={JSON.stringify({ map: state.map, request: state.request })} map={state.map} />
        </div>
      )}
    </section>
  );
}
