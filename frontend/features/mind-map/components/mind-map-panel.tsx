import { useEffect, useId, useRef, useState } from "react";
import { TopicExpansionProvider, useTopicExpansion } from "../expansion";
import type { FailedSection, MindMap, MindMapNode, MindMapState } from "../types";
import { topicsInOrder } from "../utils/tree";
import { MindMapOutline } from "./mind-map-outline";
import { MindMapProgress } from "./mind-map-progress";
import { MindMapViewer } from "./mind-map-viewer";

type PanelProps = {
  state: MindMapState;
  onRefresh: () => void;
  onRegenerate: () => void;
  onRetrySection: (sectionIndex: number) => void;
  onAskAbout?: (node: MindMapNode) => void;
};

function sectionName(section: FailedSection) {
  return section.section_title || `Seção ${section.section_index + 1}`;
}

function MindMapPresentation({ map, onAskAbout }: { map: MindMap; onAskAbout?: (node: MindMapNode) => void }) {
  const [view, setView] = useState<"map" | "list">("map");
  const expansion = useTopicExpansion(map);
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
    <TopicExpansionProvider value={expansion}>
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <div role="group" aria-label="Forma de leitura" className="inline-flex rounded-xl border border-border bg-background p-1">
            {(["map", "list"] as const).map((option) => (
              <button key={option} type="button" aria-pressed={view === option}
                aria-controls={`${panelId}-${option}`} onClick={() => setView(option)}
                className="rounded-lg px-4 py-2 text-sm font-semibold text-muted transition-colors aria-pressed:bg-surface aria-pressed:text-foreground aria-pressed:shadow-sm">
                {option === "map" ? "Mapa" : "Lista"}
              </button>
            ))}
          </div>
          <div role="group" aria-label="Eixos de estudo" className="flex flex-wrap gap-2">
            <button type="button" onClick={expansion.expandAll}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-semibold">
              Abrir todos os eixos
            </button>
            <button type="button" onClick={expansion.collapseAll}
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-semibold">
              Fechar todos os eixos
            </button>
          </div>
        </div>

        <div id={`${panelId}-map`} hidden={view !== "map"}>
          <MindMapViewer map={map} expansion={expansion} onShowList={showListAfterFailure} onAskAbout={onAskAbout} />
        </div>

        <div id={`${panelId}-list`} ref={listPanel} hidden={view !== "list"}
          role="region" aria-label="Leitura textual do mapa" tabIndex={0}>
          <MindMapOutline map={map} expansion={expansion} onAskAbout={onAskAbout} />
        </div>
      </div>
    </TopicExpansionProvider>
  );
}

function FailedSections({ sections, onRetrySection }: {
  sections: FailedSection[];
  onRetrySection: (sectionIndex: number) => void;
}) {
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm">
      <p className="font-semibold text-amber-900">
        {sections.length === 1 ? "Uma seção do material não foi processada." : `${sections.length} seções do material não foram processadas.`}
        {" "}O mapa mostra as outras seções.
      </p>
      <ul aria-label="Seções não processadas" className="mt-3 space-y-2">
        {sections.map((section) => (
          <li key={section.section_index} className="flex flex-wrap items-center justify-between gap-2">
            <span>{sectionName(section)}</span>
            <button type="button" onClick={() => onRetrySection(section.section_index)}
              aria-label={`Tentar de novo: ${sectionName(section)}`}
              className="rounded-lg border border-amber-400 bg-surface px-3 py-1.5 font-semibold">
              Tentar de novo
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Placeholder() {
  return (
    <div aria-hidden="true" className="dot-grid relative mt-6 hidden min-h-[27rem] overflow-hidden rounded-2xl border border-border bg-[#fafaff] sm:block">
      <div className="absolute left-1/2 top-[14%] w-44 -translate-x-1/2 rounded-xl border border-border bg-white p-4 shadow-lg">
        <span className="block h-2 w-16 rounded bg-[#ff8a70]" />
        <span className="mt-3 block h-2 w-28 rounded bg-border" />
      </div>
      <div className="absolute bottom-[22%] left-[14%] w-40 rounded-xl border border-border bg-white p-4 shadow-lg">
        <span className="block h-2 w-14 rounded bg-[#0284c7]/70" />
        <span className="mt-3 block h-2 w-24 rounded bg-border" />
      </div>
      <div className="absolute bottom-[22%] right-[14%] w-40 rounded-xl border border-border bg-white p-4 shadow-lg">
        <span className="block h-2 w-12 rounded bg-[#0284c7]/70" />
        <span className="mt-3 block h-2 w-20 rounded bg-border" />
      </div>
      <svg className="absolute inset-0 size-full text-[#b7b4dc]" viewBox="0 0 700 430" preserveAspectRatio="none">
        <path d="M350 120 C350 200 180 220 180 300" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="5 7" />
        <path d="M350 120 C350 200 520 220 520 300" fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="5 7" />
      </svg>
      <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center">
        <p className="text-sm font-semibold text-foreground">Seu mapa aparecerá aqui</p>
        <p className="mt-1 text-xs text-muted">Tema central, eixos de estudo e conceitos do PDF</p>
      </div>
    </div>
  );
}

function statusText(state: MindMapState): string {
  switch (state.status) {
    case "idle": return "Envie um PDF. O mapa mental do material inteiro aparecerá aqui.";
    case "loading": return "Consultando o mapa do material…";
    case "generating": return state.response.progress.message;
    case "ready": return state.response.status === "partial"
      ? "Mapa pronto. Algumas seções não puderam ser processadas."
      : "Mapa pronto. Comece pelo Eixo 1.";
    case "failed": return "Não foi possível gerar o mapa.";
    case "missing": return "Este material ainda não tem um mapa mental.";
    case "error": return state.error.message;
  }
}

export function MindMapPanel({ state, onRefresh, onRegenerate, onRetrySection, onAskAbout }: PanelProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  const isReady = state.status === "ready";

  useEffect(() => {
    if (isReady) heading.current?.focus();
  }, [isReady]);

  return (
    <section aria-labelledby="mind-map-heading" className="surface-card min-w-0 overflow-hidden rounded-2xl p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-5">
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="flex size-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">✦</span>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted">Workspace visual</p>
            <h2 id="mind-map-heading" ref={heading} tabIndex={-1} className="text-xl font-semibold tracking-tight">Mapa mental da aula</h2>
          </div>
        </div>
      </div>

      <p role="status" aria-atomic="true" className="mt-4 text-sm leading-relaxed text-muted">
        {statusText(state)}
      </p>

      {(state.status === "idle" || state.status === "loading") && <Placeholder />}

      {state.status === "generating" && <MindMapProgress response={state.response} />}

      {state.status === "failed" && (
        <div className="mt-6 space-y-4">
          <p role="alert" className="text-sm font-medium text-red-800">
            O mapa não foi gerado. Verifique se o serviço de IA está ativo e gere o mapa novamente.
          </p>
          {state.response.failed_sections.length > 0 && (
            <FailedSections sections={state.response.failed_sections} onRetrySection={onRetrySection} />
          )}
          <button type="button" onClick={onRegenerate}
            className="primary-button rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white">
            Gerar novamente
          </button>
        </div>
      )}

      {state.status === "missing" && (
        <div className="mt-6">
          <button type="button" onClick={onRegenerate}
            className="primary-button rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white">
            Gerar mapa
          </button>
        </div>
      )}

      {state.status === "error" && (
        <div className="mt-6">
          <button type="button" onClick={onRefresh}
            className="rounded-lg border border-border px-4 py-3 text-sm font-semibold">
            Tentar novamente
          </button>
        </div>
      )}

      {state.status === "ready" && (
        <div className="mt-6 space-y-5">
          <div className="break-words rounded-xl border border-border bg-background/70 p-4">
            <h3 className="text-lg font-semibold tracking-tight">{state.map.topic}</h3>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted">
              <p className="rounded-full border border-border bg-surface px-3 py-1.5">Material: {state.response.document_name}</p>
              <p className="rounded-full border border-border bg-surface px-3 py-1.5">
                {topicsInOrder(state.map).length} eixos de estudo
              </p>
            </div>
          </div>
          {state.response.failed_sections.length > 0 && (
            <FailedSections sections={state.response.failed_sections} onRetrySection={onRetrySection} />
          )}
          <MindMapPresentation key={state.response.updated_at} map={state.map} onAskAbout={onAskAbout} />
        </div>
      )}
    </section>
  );
}
