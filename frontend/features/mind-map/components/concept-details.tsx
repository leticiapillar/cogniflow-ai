import type { GenerateMapResponse, MindMapNode } from "../types";

export function ConceptDetails({ node, map }: { node?: MindMapNode; map: GenerateMapResponse }) {
  const labels = new Map(map.nodes.map((item) => [item.id, item.data.label]));
  const relations = node ? map.edges.filter((edge) => edge.source === node.id || edge.target === node.id) : [];

  return (
    <aside aria-labelledby="concept-details-heading" className="rounded-xl border border-border bg-background/70 p-4">
      <div className="flex items-center gap-2">
        <span aria-hidden="true" className="size-2 rounded-full bg-coral" />
        <h3 id="concept-details-heading" className="font-semibold">Detalhes do conceito</h3>
      </div>
      <div aria-live="polite" className="mt-2 space-y-3 break-words text-sm leading-relaxed">
        {node ? (
          <>
            <p className="font-semibold">{node.data.label}</p>
            <p className="whitespace-pre-line text-muted">{node.data.summary || "Resumo não informado."}</p>
            {relations.length > 0 && (
              <ul aria-label="Relações do conceito" className="space-y-2 text-muted">
                {relations.map((edge) => (
                  <li key={edge.id}>
                    {labels.get(edge.source)} → {edge.label || "relaciona-se com"} → {labels.get(edge.target)}
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : <p className="text-muted">Selecione um conceito no mapa para ler seu resumo e suas relações.</p>}
      </div>
    </aside>
  );
}
