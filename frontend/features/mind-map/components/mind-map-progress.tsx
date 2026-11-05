import type { MindMapStatusResponse } from "../types";

const STEPS = [
  { phase: "mapping", label: "Ler cada seção do material" },
  { phase: "consolidating", label: "Juntar conceitos repetidos" },
  { phase: "organizing", label: "Organizar os eixos de estudo" },
] as const;

/** Always the same three steps, so the student knows what comes next. */
export function MindMapProgress({ response }: { response: MindMapStatusResponse }) {
  const { progress } = response;
  const currentStep = STEPS.findIndex((step) => step.phase === progress.phase);

  return (
    <div className="mt-6 space-y-4 rounded-xl border border-border bg-background/70 p-5">
      <p className="text-sm font-semibold">Montando o mapa mental do material inteiro.</p>
      <ol aria-label="Etapas da geração do mapa" className="space-y-2 text-sm">
        {STEPS.map((step, index) => {
          const state = currentStep === -1 || index > currentStep ? "pending" : index < currentStep ? "done" : "current";
          return (
            <li key={step.phase} aria-current={state === "current" ? "step" : undefined}
              className={`flex items-center gap-2 ${state === "pending" ? "text-muted" : "font-semibold"}`}>
              <span aria-hidden="true" className={`flex size-6 items-center justify-center rounded-full text-xs ${
                state === "done" ? "bg-emerald-600 text-white" : state === "current" ? "bg-accent text-white" : "border border-border"
              }`}>
                {state === "done" ? "✓" : index + 1}
              </span>
              {step.label}
              <span className="sr-only">
                {state === "done" ? " (concluída)" : state === "current" ? " (em andamento)" : " (a fazer)"}
              </span>
            </li>
          );
        })}
      </ol>
      {progress.phase === "mapping" && progress.total > 0 && (
        <div>
          <label htmlFor="mind-map-progress" className="text-sm text-muted">
            Seções lidas: {progress.done} de {progress.total}
          </label>
          <progress id="mind-map-progress" className="mt-1 block h-2 w-full accent-[var(--accent)]"
            value={progress.done} max={progress.total} />
        </div>
      )}
      <p className="text-xs text-muted">
        Você pode continuar nesta página. O mapa aparece aqui quando ficar pronto.
      </p>
    </div>
  );
}
