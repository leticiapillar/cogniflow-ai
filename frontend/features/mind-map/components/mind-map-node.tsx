import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { ConceptFlowNode } from "../flow-types";

export const MindMapNode = memo(function MindMapNode({ data, selected }: NodeProps<ConceptFlowNode>) {
  return (
    <div className={`concept-node${selected ? " concept-node-selected" : ""}`} title={data.label}>
      <Handle type="target" position={Position.Top} isConnectable={false} />

      <div className="flex items-center gap-2">
        <span aria-hidden="true" className={`size-2 rounded-full ${data.isRoot ? "bg-[#ff6b4a]" : "bg-accent"}`} />
        <p className="text-[0.65rem] font-bold uppercase tracking-[0.12em] text-muted">{data.isRoot ? "Tema central" : "Conceito"}</p>
      </div>

      <p className="mt-2 line-clamp-2 break-words text-sm font-semibold leading-5">{data.label}</p>

      <Handle type="source" position={Position.Bottom} isConnectable={false} />
    </div>
  );
});
