import { useEffect, useRef } from "react";
import { useIngestDocument } from "../hooks/use-ingest-document";
import type { DocumentUploadResponse } from "../types";

export function DocumentUpload({ onDocumentChange }: {
  onDocumentChange: (document: DocumentUploadResponse | null) => void;
}) {
  const { selectedFile, state, selectFile, upload, cancel } = useIngestDocument(onDocumentChange);
  const errorMessage = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (state.status === "error") errorMessage.current?.focus();
  }, [state]);

  const isUploading = state.status === "uploading";
  const isInvalidFile = state.status === "error" && state.error.kind === "validation";

  return (
    <section
      aria-labelledby="document-heading"
      className="surface-card rounded-2xl p-6"
    >
      <div className="flex items-center gap-3">
        <span aria-hidden="true" className="flex size-8 items-center justify-center rounded-lg bg-accent-soft text-sm font-bold text-accent">01</span>
        <h2 id="document-heading" className="text-lg font-semibold tracking-tight">Seu material</h2>
      </div>
      <p id="document-help" className="mt-2 text-sm leading-relaxed text-muted">
        Escolha um PDF com texto selecionável, de até 20 MiB.
      </p>

      <form
        aria-label="Envio de material de estudo"
        className="mt-5 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          void upload();
        }}
      >
        <div className="dot-grid rounded-xl border border-dashed border-[#bbb7e8] bg-[#faf9ff] p-4 transition-colors hover:border-accent">
          <label htmlFor="document-file" className="block text-sm font-semibold">
            Arquivo PDF
          </label>
          <input
            id="document-file"
            type="file"
            accept=".pdf,application/pdf"
            onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
            aria-invalid={isInvalidFile}
            aria-describedby={`document-help document-status${state.status === "error" ? " document-error" : ""}`}
            className="mt-3 block w-full min-w-0 text-sm text-muted file:mr-3 file:cursor-pointer file:rounded-lg file:border-0 file:bg-accent-soft file:px-3 file:py-2 file:text-sm file:font-semibold file:text-accent"
          />
        </div>

        {state.status === "error" && (
          <p id="document-error" ref={errorMessage} role="alert" tabIndex={-1} className="text-sm font-medium text-red-800">
            {state.error.message}
          </p>
        )}

        <div className="flex flex-wrap gap-3">
          <button
            type="submit"
            aria-busy={isUploading}
            disabled={!selectedFile || isUploading || isInvalidFile || state.status === "success"}
            className="primary-button flex-1 rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-border disabled:text-muted disabled:shadow-none"
          >
            {isUploading ? "Enviando PDF…" : state.status === "error" && !isInvalidFile ? "Tentar novamente" : "Enviar PDF"}
          </button>

          {isUploading && (
            <button type="button" onClick={cancel} className="rounded-lg border border-border px-4 py-3 text-sm font-semibold">
              Cancelar
            </button>
          )}
        </div>

        <p id="document-status" role="status" aria-atomic="true" className="text-sm leading-relaxed text-muted">
          {isUploading
            ? "Enviando e preparando o material. Você pode cancelar ou selecionar outro arquivo."
            : state.status === "success"
              ? `PDF preparado: ${state.document.total_chunks} ${state.document.total_chunks === 1 ? "trecho disponível" : "trechos disponíveis"}. Selecione outro arquivo para substituir o material.`
              : selectedFile ? `Arquivo selecionado: ${selectedFile.name}.` : "Selecione um PDF para começar."}
        </p>
      </form>
    </section>
  );
}
