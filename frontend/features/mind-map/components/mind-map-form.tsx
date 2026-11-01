import { useEffect, useRef, type Ref } from "react";
import type { GenerationState } from "../types";

type MindMapFormProps = {
  documentName?: string;
  query: string;
  state: GenerationState;
  onQueryChange: (query: string) => void;
  onGenerate: () => void;
  onCancel: () => void;
  inputRef?: Ref<HTMLTextAreaElement>;
};

export function MindMapForm({ documentName, query, state, onQueryChange, onGenerate, onCancel, inputRef }: MindMapFormProps) {
  const errorMessage = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (state.status === "error") errorMessage.current?.focus();
  }, [state]);

  const isGenerating = state.status === "generating";
  const isInvalidQuery = state.status === "error" &&
    (state.error.kind === "validation" || state.error.status === 422);

  return (
    <section
      aria-labelledby="query-heading"
      className="surface-card rounded-2xl p-6"
    >
      <div className="flex items-center gap-3">
        <span aria-hidden="true" className="flex size-8 items-center justify-center rounded-lg bg-orange-50 text-sm font-bold text-[#c94627]">02</span>
        <h2 id="query-heading" className="text-lg font-semibold tracking-tight">Seu tema de estudo</h2>
      </div>

      <p id="query-help" className="mt-2 text-sm leading-relaxed text-muted">
        Diga qual assunto você quer explorar no seu material. Use de 3 a 2.000 caracteres.
      </p>

      {documentName && (
        <p className="mt-3 break-words text-sm text-muted">Material selecionado: {documentName}</p>
      )}

      <form
        aria-label="Geração de mapa mental"
        noValidate
        className="mt-5"
        onSubmit={(event) => {
          event.preventDefault();
          onGenerate();
        }}
      >
        <fieldset disabled={!documentName} aria-describedby="query-help query-availability">
          <legend className="sr-only">Consulta para geração do mapa mental</legend>

          <label htmlFor="study-query" className="block text-sm font-semibold">
            O que você quer estudar?
          </label>
          <textarea
            ref={inputRef}
            id="study-query"
            name="query"
            rows={3}
            minLength={3}
            maxLength={2000}
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            aria-invalid={isInvalidQuery}
            aria-describedby={`query-help query-availability query-count${state.status === "error" ? " query-error" : ""}`}
            placeholder="Ex.: conceitos principais da fotossíntese"
            className="mt-2 block w-full resize-y rounded-xl border border-border bg-background px-3 py-3 text-sm transition-colors placeholder:text-muted focus:border-accent disabled:cursor-not-allowed disabled:bg-[#f1f2f6]"
          />
          <p id="query-count" className="mt-2 text-sm text-muted">{query.trim().length}/2.000 caracteres</p>

          {state.status === "error" && (
            <p id="query-error" ref={errorMessage} role="alert" tabIndex={-1} className="mt-3 text-sm font-medium text-red-800">
              {state.error.message}
            </p>
          )}

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={isGenerating}
              className="primary-button flex-1 rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-border disabled:text-muted disabled:shadow-none"
            >
              {isGenerating ? "Gerando mapa…" : state.status === "error" ? "Tentar novamente" : "Gerar mapa"}
            </button>

            {isGenerating && (
              <button type="button" onClick={onCancel} className="rounded-lg border border-border px-4 py-3 text-sm font-semibold">
                Cancelar geração
              </button>
            )}

          </div>
        </fieldset>
      </form>

      <p id="query-availability" className="mt-3 text-sm text-muted">
        {documentName
          ? "A consulta usa apenas o documento selecionado. Você pode editar o tema para iniciar uma nova consulta."
          : "Envie um PDF para habilitar a consulta."}
      </p>
    </section>
  );
}
