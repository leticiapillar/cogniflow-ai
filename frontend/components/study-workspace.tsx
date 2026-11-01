"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { DocumentUpload } from "@/features/documents/components/document-upload";
import type { DocumentUploadResponse } from "@/features/documents/types";
import { MindMapForm } from "@/features/mind-map/components/mind-map-form";
import { MindMapResult } from "@/features/mind-map/components/mind-map-result";
import { useGenerateMindMap } from "@/features/mind-map/hooks/use-generate-mind-map";
import { StatusMessage } from "@/components/ui/status-message";

export function StudyWorkspace() {
  const [activeDocument, setActiveDocument] = useState<DocumentUploadResponse | null>(null);
  const queryInput = useRef<HTMLTextAreaElement>(null);
  const { query, state, updateQuery, generate, reset, cancel } = useGenerateMindMap();

  useEffect(() => {
    if (activeDocument) queryInput.current?.focus();
  }, [activeDocument]);

  const handleDocumentChange = useCallback((document: DocumentUploadResponse | null) => {
    reset();

    setActiveDocument(document);
  }, [reset]);

  return (
    <div className="space-y-6">
      <StatusMessage>
        {activeDocument
          ? `Documento “${activeDocument.document_name}” pronto para uso. Escolha um tema para gerar os conceitos.`
          : "Envie um PDF para preparar seu material e habilitar a geração de conceitos."}
      </StatusMessage>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(20rem,23rem)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-5 lg:sticky lg:top-6">
          <DocumentUpload onDocumentChange={handleDocumentChange} />
          <MindMapForm
            documentName={activeDocument?.document_name}
            inputRef={queryInput}
            query={query}
            state={state}
            onQueryChange={updateQuery}
            onGenerate={() => { void generate(activeDocument?.document_name); }}
            onCancel={cancel}
          />
        </div>

        <MindMapResult state={state} />
      </div>
    </div>
  );
}
