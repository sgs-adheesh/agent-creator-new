import { useCallback, useEffect, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { nodeTypes } from '../components/nodeTypes';
import { agentApi, type WorkflowGraph } from '../services/api';

interface WorkflowViewerProps {
  agentId: string;
  useAi?: boolean;
}

export default function WorkflowViewer({ agentId, useAi = true }: WorkflowViewerProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    loadWorkflow();
  }, [agentId, useAi]);

  const loadWorkflow = async () => {
    setLoading(true);
    setError(null);
    try {
      const workflow: WorkflowGraph = await agentApi.getWorkflow(agentId, true);
      setNodes(workflow.nodes as Node[]);
      setEdges(workflow.edges as Edge[]);
      setMetadata(workflow.metadata || null);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load workflow';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const onInit = useCallback(() => {
    console.log('Workflow initialized');
  }, []);

  if (loading) {
    return (
      <div className="h-[600px] flex items-center justify-center bg-gray-50 rounded-lg border-1 border-dashed border-gray-300">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading workflow...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-[600px] flex items-center justify-center bg-red-50 rounded-lg border-1 border-red-300">
        <div className="text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <p className="text-red-700">{error}</p>
          <button
            onClick={loadWorkflow}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[600px] border-1 border-gray-200 rounded-lg overflow-hidden">
      {metadata && (
        <div className="bg-gray-100 px-4 py-2 border-b border-gray-200">
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <span className="font-medium">
              Generation: {String(metadata.generation_method || 'unknown')}
            </span>
            {metadata.tool_count !== undefined && (
              <span>Tools: {String(metadata.tool_count)}</span>
            )}
            {typeof metadata.ai_suggestions === 'string' && (
              <span className="text-xs italic">AI: {metadata.ai_suggestions}</span>
            )}
          </div>
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onInit={onInit}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
        <MiniMap
          nodeColor={(node) => {
            switch (node.type) {
              case 'input':
                return '#93c5fd';
              case 'agent':
                return '#c4b5fd';
              case 'tool':
                return '#86efac';
              case 'output':
                return '#fdba74';
              case 'decision':
                return '#fde047';
              default:
                return '#e5e7eb';
            }
          }}
        />
      </ReactFlow>
    </div>
  );
}
