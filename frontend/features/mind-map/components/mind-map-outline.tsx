import { useId } from "react";
import { conceptCountLabel, type TopicExpansion } from "../expansion";
import { getCategoryMeta } from "../graph-config";
import type { MindMap, MindMapNode } from "../types";
import { childrenByParent, parentEdgeOf, rootOf, topicsInOrder } from "../utils/tree";

type OutlineProps = {
  map: MindMap;
  expansion: TopicExpansion;
  onAskAbout?: (node: MindMapNode) => void;
};

function ConceptItem({ map, concept, examples, onAskAbout }: {
  map: MindMap;
  concept: MindMapNode;
  examples: MindMapNode[];
  onAskAbout?: (node: MindMapNode) => void;
}) {
  const relation = parentEdgeOf(map, concept.id);
  const parent = map.nodes.find((node) => node.id === relation?.source);
  const acronyms = Object.entries(concept.data.acronyms);

  return (
    <li className="break-words rounded-lg border border-border bg-surface p-3">
      <h5 className="font-semibold">{concept.data.label}</h5>
      {relation && parent && (
        <p className="mt-1 text-xs text-muted">{parent.data.label} {relation.label} {concept.data.label}.</p>
      )}
      <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted">
        {concept.data.summary || "Resumo não informado."}
      </p>
      {acronyms.length > 0 && (
        <dl aria-label={`Siglas de ${concept.data.label}`} className="mt-2 space-y-1 text-sm text-muted">
          {acronyms.map(([acronym, expansionText]) => (
            <div key={acronym}><dt className="inline font-semibold">{acronym}:</dt> <dd className="inline">{expansionText}</dd></div>
          ))}
        </dl>
      )}
      {examples.length > 0 && (
        <ul aria-label={`Exemplos de ${concept.data.label}`} className="mt-2 space-y-1 text-sm">
          {examples.map((example) => (
            <li key={example.id}>
              <span className="font-semibold">Exemplo: {example.data.label}.</span>{" "}
              <span className="text-muted">{example.data.summary}</span>
            </li>
          ))}
        </ul>
      )}
      {onAskAbout && (
        <button type="button" onClick={() => onAskAbout(concept)}
          className="mt-3 rounded-lg border border-border px-3 py-2 text-sm font-semibold text-accent">
          Tirar dúvida sobre {concept.data.label}
        </button>
      )}
    </li>
  );
}

export function MindMapOutline({ map, expansion, onAskAbout }: OutlineProps) {
  const idPrefix = useId();
  const root = rootOf(map);
  const children = childrenByParent(map);

  return (
    <div className="space-y-5">
      <h3 className="font-semibold">Leitura do mapa</h3>

      <div className="break-words rounded-xl border border-border bg-background/70 p-4">
        <p className="text-xs font-bold uppercase tracking-[0.1em] text-muted">Tema central</p>
        <h4 className="mt-1 font-semibold">{root.data.label}</h4>
        <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted">
          {root.data.summary || "Resumo não informado."}
        </p>
      </div>

      <ol aria-label="Eixos de estudo" className="space-y-4">
        {topicsInOrder(map).map((topic) => {
          const meta = getCategoryMeta(topic.data.category, false, topic.data.order);
          const concepts = children.get(topic.id) ?? [];
          const expanded = expansion.isExpanded(topic.id);
          const panelId = `${idPrefix}-${topic.id}`;

          return (
            <li key={topic.id} className="break-words rounded-xl border border-border bg-background/70 p-4 shadow-sm">
              <div className="mb-1 flex items-center gap-2">
                <span aria-hidden="true" className={`size-2 rounded-full ${meta.dotClass}`} />
                <span className="text-xs font-bold uppercase tracking-[0.1em] text-muted">{meta.label}</span>
              </div>
              <h4 className="font-semibold">{topic.data.label}</h4>
              <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted">
                {topic.data.summary || "Resumo não informado."}
              </p>
              <button
                type="button"
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => expansion.toggle(topic.id)}
                className="mt-3 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-semibold"
              >
                <span aria-hidden="true">{expanded ? "▾" : "▸"} </span>
                {expanded ? `Fechar ${meta.label.toLowerCase()}` : `Abrir ${meta.label.toLowerCase()} (${conceptCountLabel(concepts.length)})`}
              </button>
              <div id={panelId} hidden={!expanded}>
                {expanded && (
                  <ul aria-label={`Conceitos do ${meta.label.toLowerCase()}`} className="mt-3 space-y-3">
                    {concepts.map((concept) => (
                      <ConceptItem key={concept.id} map={map} concept={concept}
                        examples={children.get(concept.id) ?? []} onAskAbout={onAskAbout} />
                    ))}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
