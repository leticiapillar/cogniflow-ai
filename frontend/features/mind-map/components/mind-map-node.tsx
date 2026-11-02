import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { ConceptFlowNode } from "../flow-types";
import { getCategoryMeta } from "../graph-config";

export const MindMapNode = memo(function MindMapNode({ data, selected }: NodeProps<ConceptFlowNode>) {
  const meta = getCategoryMeta(data.category, data.isRoot);

  return (
    <div className={`concept-node ${meta.nodeClass}${selected ? " concept-node-selected" : ""}`} title={data.label}>
      <Handle type="target" position={Position.Top} isConnectable={false} />

      <div className="flex items-center gap-2">
        <span aria-hidden="true" className={`size-2 rounded-full ${meta.dotClass}`} />
        <p className="text-[0.65rem] font-bold uppercase tracking-[0.12em] text-muted">{meta.label}</p>
      </div>

      <p className="mt-1.5 line-clamp-2 break-words text-sm font-semibold leading-5">{data.label}</p>
      {data.summary && (
        <p className="mt-1 line-clamp-1 break-words text-xs leading-4 text-muted">{data.summary}</p>
      )}

      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
});
