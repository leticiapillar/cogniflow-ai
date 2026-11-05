import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { conceptCountLabel, useExpansionContext } from "../expansion";
import type { ConceptFlowNode } from "../flow-types";
import { getCategoryMeta } from "../graph-config";

export const MindMapNode = memo(function MindMapNode({ id, data, selected }: NodeProps<ConceptFlowNode>) {
  const meta = getCategoryMeta(data.category, data.isRoot, data.order);
  const expansion = useExpansionContext();
  const isTopic = data.category === "topic";
  const expanded = expansion?.isExpanded(id) ?? false;
  const count = expansion?.conceptCount(id) ?? 0;

  return (
    <div className={`concept-node ${meta.nodeClass}${selected ? " concept-node-selected" : ""}`} title={data.label}>
      <Handle type="target" position={Position.Top} isConnectable={false} />

      <div className="flex items-center gap-2">
        <span aria-hidden="true" className={`size-2 rounded-full ${meta.dotClass}`} />
        <p className="text-[0.65rem] font-bold uppercase tracking-[0.12em] text-muted">{meta.label}</p>
      </div>

      <p className="mt-1.5 line-clamp-2 break-words text-sm font-semibold leading-5">{data.label}</p>

      {isTopic && expansion ? (
        <button
          type="button"
          className="nodrag nopan mt-1.5 rounded-md border border-border bg-background px-2 py-0.5 text-xs font-semibold text-accent"
          aria-expanded={expanded}
          // The accessible name starts with the visible text (WCAG 2.5.3, label in name).
          aria-label={expanded
            ? `Fechar ${meta.label.toLowerCase()}: ${data.label}`
            : `Abrir ${conceptCountLabel(count)} do ${meta.label.toLowerCase()}: ${data.label}`}
          onClick={() => expansion.toggle(id)}
        >
          <span aria-hidden="true">{expanded ? "▾" : "▸"} </span>
          {expanded ? "Fechar" : `Abrir ${conceptCountLabel(count)}`}
        </button>
      ) : data.summary && (
        <p className="mt-1 line-clamp-1 break-words text-xs leading-4 text-muted">{data.summary}</p>
      )}

      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
});
