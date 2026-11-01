import { useCallback, useState } from "react";
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
import type { ConceptFlowEdge, ConceptFlowNode } from "../flow-types";
import type { GenerateMapResponse } from "../types";
import { adaptMindMap } from "../utils/graph-adapter";
import { layoutGraph } from "../utils/layout-graph";
import { ConceptDetails } from "./concept-details";
import { MindMapErrorBoundary } from "./mind-map-error-boundary";
import { MindMapNode } from "./mind-map-node";
import { MindMapToolbar } from "./mind-map-toolbar";

const nodeTypes = { concept: MindMapNode };
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

function MindMapCanvas({ map }: { map: GenerateMapResponse }) {
  const [initialGraph] = useState(() => layoutGraph(adaptMindMap(map)));
  const [nodes, setNodes, onNodesChange] = useNodesState<ConceptFlowNode>(initialGraph.nodes);
  const [edges, , onEdgesChange] = useEdgesState<ConceptFlowEdge>(initialGraph.edges);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { fitView, zoomIn, zoomOut } = useReactFlow<ConceptFlowNode, ConceptFlowEdge>();

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
        Selecione um conceito para ler os detalhes. Arraste os conceitos para mudar suas posições ou o fundo para navegar pelo mapa.
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
      <ConceptDetails node={map.nodes.find((node) => node.id === selectedId)} map={map} />
    </div>
  );
}

export function MindMapViewer({ map, onShowList }: { map: GenerateMapResponse; onShowList?: () => void }) {
  return (
    <MindMapErrorBoundary key={JSON.stringify(map)} onShowList={onShowList}>
      <ReactFlowProvider>
        <MindMapCanvas map={map} />
      </ReactFlowProvider>
    </MindMapErrorBoundary>
  );
}
