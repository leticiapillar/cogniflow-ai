import { conceptCountLabel, type TopicExpansion } from "../expansion";
import { getCategoryMeta } from "../graph-config";
import type { MindMap, MindMapNode } from "../types";

type ConceptDetailsProps = {
  node?: MindMapNode;
  map: MindMap;
  expansion?: TopicExpansion;
  onAskAbout?: (node: MindMapNode) => void;
};

export function ConceptDetails({ node, map, expansion, onAskAbout }: ConceptDetailsProps) {
  const labels = new Map(map.nodes.map((item) => [item.id, item.data.label]));
  const relations = node ? map.edges.filter((edge) => edge.source === node.id || edge.target === node.id) : [];
  const meta = node ? getCategoryMeta(node.data.category, node.type === "input", node.data.order) : null;
  const acronyms = node ? Object.entries(node.data.acronyms) : [];
  const isTopic = node?.data.category === "topic";

  return (
    <aside aria-labelledby="concept-details-heading" className="rounded-xl border border-border bg-background/70 p-4">
      <div className="flex items-center gap-2">
        <span aria-hidden="true" className="size-2 rounded-full bg-coral" />
        <h3 id="concept-details-heading" className="font-semibold">Detalhes do conceito</h3>
      </div>
      <div aria-live="polite" className="mt-2 space-y-3 break-words text-sm leading-relaxed">
        {node && meta ? (
          <>
            <div className="flex items-center gap-2">
              <span aria-hidden="true" className={`size-2 rounded-full ${meta.dotClass}`} />
              <span className="text-xs font-bold uppercase tracking-[0.1em] text-muted">{meta.label}</span>
            </div>
            <p className="font-semibold">{node.data.label}</p>
            <p className="whitespace-pre-line text-muted">{node.data.summary || "Resumo não informado."}</p>

            {acronyms.length > 0 && (
              <dl aria-label="Siglas" className="space-y-1 text-muted">
                {acronyms.map(([acronym, expansionText]) => (
                  <div key={acronym}><dt className="inline font-semibold">{acronym}:</dt> <dd className="inline">{expansionText}</dd></div>
                ))}
              </dl>
            )}

            {relations.length > 0 && (
              <ul aria-label="Relações do conceito" className="space-y-2 text-muted">
                {relations.map((edge) => (
                  <li key={edge.id}>
                    {labels.get(edge.source)} → {edge.label} → {labels.get(edge.target)}
                  </li>
                ))}
              </ul>
            )}

            <div className="flex flex-wrap gap-2">
              {isTopic && expansion && (
                <button
                  type="button"
                  aria-expanded={expansion.isExpanded(node.id)}
                  onClick={() => expansion.toggle(node.id)}
                  className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-semibold"
                >
                  {expansion.isExpanded(node.id) ? "Fechar eixo" : `Abrir eixo (${conceptCountLabel(expansion.conceptCount(node.id))})`}
                </button>
              )}
              {onAskAbout && (
                <button
                  type="button"
                  onClick={() => onAskAbout(node)}
                  className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white"
                >
                  Tirar dúvida sobre este conceito
                </button>
              )}
            </div>
          </>
        ) : <p className="text-muted">Selecione um conceito no mapa para ler seu resumo e suas relações.</p>}
      </div>
    </aside>
  );
}
