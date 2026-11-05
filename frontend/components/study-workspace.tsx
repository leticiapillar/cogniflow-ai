"use client";

import { useCallback, useRef, useState } from "react";
import { DocumentUpload } from "@/features/documents/components/document-upload";
import type { DocumentUploadResponse } from "@/features/documents/types";
import { MindMapPanel } from "@/features/mind-map/components/mind-map-panel";
import { useMindMap } from "@/features/mind-map/hooks/use-mind-map";
import type { MindMapNode, MindMapState } from "@/features/mind-map/types";
import { ServiceStatus } from "@/features/service-status/components/service-status";
import { useServiceHealth } from "@/features/service-status/hooks/use-service-health";
import { TutorPanel } from "@/features/tutor/components/tutor-panel";
import { useTutor } from "@/features/tutor/hooks/use-tutor";
import { StatusMessage } from "@/components/ui/status-message";

function workspaceMessage(document: DocumentUploadResponse | null, map: MindMapState): string {
  if (!document) return "Envie o PDF da aula. O mapa mental e o tira-dúvidas usam apenas esse material.";
  if (map.status === "ready") return `Material “${document.document_name}” pronto. Explore o mapa e tire suas dúvidas.`;
  if (map.status === "failed" || map.status === "missing" || map.status === "error") {
    return `Material “${document.document_name}” recebido, mas o mapa ainda não está disponível.`;
  }
  return `Material “${document.document_name}” recebido. O mapa mental está sendo montado.`;
}

export function StudyWorkspace() {
  const health = useServiceHealth();
  const [activeDocument, setActiveDocument] = useState<DocumentUploadResponse | null>(null);
  const documentId = activeDocument?.document_id ?? null;
  const mindMap = useMindMap(documentId);
  const tutor = useTutor(documentId);
  const questionInput = useRef<HTMLTextAreaElement>(null);
  const mapReady = mindMap.state.status === "ready";
  const { setConcept } = tutor;

  const handleDocumentChange = useCallback((document: DocumentUploadResponse | null) => {
    setActiveDocument(document);
  }, []);

  const askAbout = useCallback((node: MindMapNode) => {
    setConcept({ nodeId: node.id, label: node.data.label });
    questionInput.current?.focus();
  }, [setConcept]);

  return (
    <div className="space-y-6">
      <StatusMessage>{workspaceMessage(activeDocument, mindMap.state)}</StatusMessage>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-5">
          <ServiceStatus state={health.state} onRecheck={health.recheck} />
          <DocumentUpload onDocumentChange={handleDocumentChange} disabled={health.state.status !== "ready"} />
          <TutorPanel
            tutor={tutor}
            enabled={mapReady}
            disabledMessage={activeDocument
              ? "O tira-dúvidas fica disponível quando o mapa estiver pronto."
              : "Envie um PDF para tirar dúvidas."}
            inputRef={questionInput}
          />
        </div>

        <MindMapPanel
          state={mindMap.state}
          onRefresh={mindMap.refresh}
          onRegenerate={mindMap.regenerate}
          onRetrySection={mindMap.retrySection}
          onAskAbout={mapReady ? askAbout : undefined}
        />
      </div>
    </div>
  );
}
