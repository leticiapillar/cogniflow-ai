import type { GenerateMapResponse } from "../types";

export function MindMapOutline({ map }: { map: GenerateMapResponse }) {
  const labels = new Map(map.nodes.map((node) => [node.id, node.data.label]));
  return (
    <div className="space-y-5">
      <h3 className="font-semibold">Leitura dos conceitos</h3>

      <ol aria-label="Conceitos gerados" className="space-y-4">
        {map.nodes.map((node) => (
          <li key={node.id} className="break-words rounded-xl border border-border bg-background/70 p-4 shadow-sm">
            <h4 className="font-semibold">{node.data.label}</h4>
            <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-muted">
              {node.data.summary || "Resumo não informado."}
            </p>
          </li>
        ))}
      </ol>

      <h3 className="font-semibold">Relações entre conceitos</h3>

      {map.edges.length ? (
        <ul aria-label="Relações entre conceitos" className="space-y-3 text-sm leading-relaxed">
          {map.edges.map((edge) => (
            <li key={edge.id} className="break-words rounded-lg border border-border bg-background/70 p-3">
              <span className="font-semibold">{labels.get(edge.source)}</span>{" "}
              {edge.label || "relaciona-se com"}{" "}
              <span className="font-semibold">{labels.get(edge.target)}</span>.
            </li>
          ))}
        </ul>
      ) : <p className="text-sm text-muted">Não foram retornadas relações entre os conceitos.</p>}
    </div>
  );
}
