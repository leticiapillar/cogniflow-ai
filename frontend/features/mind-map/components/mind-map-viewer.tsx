import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type OnSelectionChangeParams,
  type AriaLabelConfig,
} from "@xyflow/react";
import type { TopicExpansion } from "../expansion";
import type { ConceptFlowEdge, ConceptFlowNode, MindMapGraph } from "../flow-types";
import type { MindMap, MindMapNode } from "../types";
import { adaptMindMap } from "../utils/graph-adapter";
import { layoutGraph } from "../utils/layout-graph";
import { visibleNodeIds } from "../utils/tree";
import { ConceptDetails } from "./concept-details";
import { MindMapErrorBoundary } from "./mind-map-error-boundary";
import { MindMapNode as MindMapNodeView } from "./mind-map-node";
import { MindMapToolbar } from "./mind-map-toolbar";

const nodeTypes = { concept: MindMapNodeView };
const fitOptions = { padding: 0.2, minZoom: 0.05, maxZoom: 1, duration: 0 };

const ariaLabelConfig: Partial<AriaLabelConfig> = {
  "node.a11yDescription.default": "Pressione Enter ou Espaço para selecionar um conceito. Use as setas para movê-lo. Pressione Escape para cancelar a seleção.",
  "node.a11yDescription.keyboardDisabled": "Pressione Enter ou Espaço para selecionar um conceito e ler seus detalhes.",
  "node.a11yDescription.ariaLiveMessage": ({ direction }) => {
    const directions: Record<string, string> = { up: "cima", down: "baixo", left: "a esquerda", right: "a direita" };
    return `Conceito movido para ${directions[direction] || "uma nova posição"}.`;
  },
  "edge.a11yDescription.default": "Pressione Enter ou Espaço para selecionar uma relação. Pressione Escape para cancelar a seleção.",
  "controls.ariaLabel": "Controles do mapa",
  "controls.zoomIn.ariaLabel": "Aumentar zoom",
  "controls.zoomOut.ariaLabel": "Diminuir zoom",
  "controls.fitView.ariaLabel": "Ajustar à tela",
  "controls.interactive.ariaLabel": "Alternar interação",
  "minimap.ariaLabel": "Visão geral do mapa",
  "handle.ariaLabel": "Ponto de conexão",
};

function visibleLayout(graph: MindMapGraph, visible: ReadonlySet<string>, selectedId: string | null): MindMapGraph {
  const laid = layoutGraph({
    nodes: graph.nodes.filter((node) => visible.has(node.id)),
    edges: graph.edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target)),
  });
  return { ...laid, nodes: laid.nodes.map((node) => ({ ...node, selected: node.id === selectedId })) };
}

type CanvasProps = {
  map: MindMap;
  expansion: TopicExpansion;
  onAskAbout?: (node: MindMapNode) => void;
};

function MindMapCanvas({ map, expansion, onAskAbout }: CanvasProps) {
  const fullGraph = useMemo(() => adaptMindMap(map), [map]);
  const visible = useMemo(() => visibleNodeIds(map, expansion.expanded), [map, expansion.expanded]);
  const visibleKey = [...visible].sort().join("|");

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [initialGraph] = useState(() => visibleLayout(fullGraph, visible, null));
  const [nodes, setNodes, onNodesChange] = useNodesState<ConceptFlowNode>(initialGraph.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<ConceptFlowEdge>(initialGraph.edges);
  const [layoutKey, setLayoutKey] = useState(visibleKey);
  const { fitView, zoomIn, zoomOut } = useReactFlow<ConceptFlowNode, ConceptFlowEdge>();

  // Opening or closing an axis lays the visible tree out again (during render, so the
  // canvas never shows nodes of a closed axis).
  if (layoutKey !== visibleKey) {
    const next = visibleLayout(fullGraph, visible, selectedId);
    setLayoutKey(visibleKey);
    setNodes(next.nodes);
    setEdges(next.edges);
  }

  useEffect(() => {
    const frame = requestAnimationFrame(() => { void fitView(fitOptions); });
    return () => cancelAnimationFrame(frame);
  }, [layoutKey, fitView]);

  const onSelectionChange = useCallback(({ nodes: selected }: OnSelectionChangeParams<ConceptFlowNode>) => {
    setSelectedId(selected[0]?.id ?? null);
  }, []);

  const reorganize = useCallback(() => {
    setNodes((current) => layoutGraph({ nodes: current, edges }).nodes);

    requestAnimationFrame(() => { void fitView(fitOptions); });
  }, [edges, fitView, setNodes]);

  return (
    <div className="space-y-4">
      <MindMapToolbar
        onZoomIn={() => { void zoomIn({ duration: 0 }); }}
        onZoomOut={() => { void zoomOut({ duration: 0 }); }}
        onFitView={() => { void fitView(fitOptions); }}
        onReorganize={reorganize}
      />
      <p id="map-instructions" className="rounded-lg bg-accent-soft/60 px-3 py-2 text-sm leading-relaxed text-muted">
        Comece pelo Eixo 1. Use o botão Abrir de cada eixo para ver os conceitos dele. Selecione um conceito para ler os detalhes.
      </p>
      <div role="region" aria-label="Mapa mental interativo" aria-describedby="map-instructions" className="mind-map-canvas">
        <ReactFlow<ConceptFlowNode, ConceptFlowEdge>
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onSelectionChange={onSelectionChange}
          fitView
          fitViewOptions={fitOptions}
          minZoom={0.05}
          maxZoom={2.5}
          nodesDraggable
          nodesConnectable={false}
          edgesReconnectable={false}
          deleteKeyCode={null}
          zoomOnScroll={false}
          zoomOnDoubleClick={false}
          preventScrolling={false}
          colorMode="light"
          ariaLabelConfig={ariaLabelConfig}
        >
          <Background variant={BackgroundVariant.Dots} gap={24} size={1} />
        </ReactFlow>
      </div>
      <ConceptDetails
        node={map.nodes.find((node) => node.id === selectedId)}
        map={map}
        expansion={expansion}
        onAskAbout={onAskAbout}
      />
    </div>
  );
}

export function MindMapViewer({ map, expansion, onShowList, onAskAbout }: CanvasProps & { onShowList?: () => void }) {
  return (
    <MindMapErrorBoundary key={JSON.stringify(map)} onShowList={onShowList}>
      <ReactFlowProvider>
        <MindMapCanvas map={map} expansion={expansion} onAskAbout={onAskAbout} />
      </ReactFlowProvider>
    </MindMapErrorBoundary>
  );
}
