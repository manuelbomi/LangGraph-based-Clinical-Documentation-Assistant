import { Background, type Edge, Handle, type Node, Position, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";

import { GRAPH_NODE_LABELS, GRAPH_NODES, type GraphNodeName } from "../api/types";

interface GraphViewProps {
  currentNode: GraphNodeName | null;
  completedNodes: GraphNodeName[];
}

interface NodeData extends Record<string, unknown> {
  label: string;
  active: boolean;
  done: boolean;
}

function StepNode({ data }: { data: NodeData }) {
  const base =
    "rounded-lg border-2 px-3 py-2 text-sm font-medium shadow-sm min-w-[190px] text-center transition-colors";
  const cls = data.active
    ? `${base} border-brand-500 bg-brand-500 text-white animate-pulse`
    : data.done
      ? `${base} border-brand-300 bg-brand-50 text-brand-800`
      : `${base} border-slate-300 bg-white text-slate-500`;
  return (
    <div className={cls}>
      <Handle type="target" position={Position.Top} className="!bg-slate-400" />
      {data.label}
      <Handle type="source" position={Position.Bottom} className="!bg-slate-400" />
    </div>
  );
}

const nodeTypes = { step: StepNode };

/** This graph has no conditional routing -- every encounter visits all six
 * nodes in this exact order, so the layout is a single straight line
 * (unlike the branching GraphViews in the tax-intake/invoice-audit
 * tutorials in this series). */
const LAYOUT: Record<GraphNodeName, { x: number; y: number }> = {
  ingest: { x: 0, y: 0 },
  extract_structured: { x: 0, y: 100 },
  code_lookup: { x: 0, y: 200 },
  generate_patient_summary: { x: 0, y: 300 },
  clinician_review: { x: 0, y: 400 },
  finalize: { x: 0, y: 500 },
};

export function GraphView({ currentNode, completedNodes }: GraphViewProps) {
  const nodes: Node[] = useMemo(
    () =>
      GRAPH_NODES.map((id, index) => ({
        id,
        type: "step",
        position: LAYOUT[id],
        data: {
          label: `${index + 1}. ${GRAPH_NODE_LABELS[id]}`,
          active: currentNode === id,
          done: completedNodes.includes(id) && currentNode !== id,
        } satisfies NodeData,
        draggable: false,
      })),
    [currentNode, completedNodes],
  );

  const edgeStyle = (active: boolean) => ({
    stroke: active ? "#19766f" : "#cbd5e1",
    strokeWidth: active ? 2.5 : 1.5,
  });

  const edges: Edge[] = useMemo(() => {
    const list: Edge[] = [];
    for (let i = 0; i < GRAPH_NODES.length - 1; i++) {
      const source = GRAPH_NODES[i];
      const target = GRAPH_NODES[i + 1];
      list.push({
        id: `e-${source}-${target}`,
        source,
        target,
        style: edgeStyle(completedNodes.includes(target)),
      });
    }
    return list;
  }, [completedNodes]);

  return (
    <div className="h-[560px] w-full rounded-xl border border-slate-200 bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background gap={16} color="#e2e8f0" />
      </ReactFlow>
    </div>
  );
}
