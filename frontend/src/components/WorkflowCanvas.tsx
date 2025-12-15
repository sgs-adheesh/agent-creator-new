import { useEffect, useState } from 'react';
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
import { nodeTypes } from './nodeTypes';
import { agentApi, type WorkflowGraph, type ExecuteAgentResponse, type WorkflowConfig } from '../services/api';
import { DynamicPlayground } from './DynamicPlayground';

interface WorkflowCanvasProps {
  agentId: string;
}

export default function WorkflowCanvas({ agentId }: WorkflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPlayground, setShowPlayground] = useState(false);
  const [query, setQuery] = useState('');
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<ExecuteAgentResponse | null>(null);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [toolConfigs, setToolConfigs] = useState<Record<string, Record<string, string>>>({});
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configToolName, setConfigToolName] = useState<string>('');
  const [workflowConfig, setWorkflowConfig] = useState<WorkflowConfig>({
    trigger_type: 'text_query',
    input_fields: [],
    output_format: 'text',
  });

  useEffect(() => {
    loadWorkflow();
  }, [agentId]);

  const loadWorkflow = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch agent data to get workflow config
      const agentData = await agentApi.getAgent(agentId);
      
      // Set workflow config from agent data or use defaults
      if (agentData.workflow_config) {
        setWorkflowConfig(agentData.workflow_config);
      }
      
      const workflow: WorkflowGraph = await agentApi.getWorkflow(agentId, false);
      
      // Enhance nodes with configuration handler
      const enhancedNodes = (workflow.nodes as Node[]).map(node => ({
        ...node,
        data: {
          ...node.data,
          onConfigure: handleToolConfigure,
          isConfigured: node.data?.tool_name ? !!toolConfigs[node.data.tool_name] : false,
        }
      }));
      
      setNodes(enhancedNodes);
      setEdges(workflow.edges as Edge[]);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load workflow';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleToolConfigure = (toolName: string) => {
    setConfigToolName(toolName);
    setShowConfigModal(true);
  };

  const handleSaveConfig = (config: Record<string, string>) => {
    setToolConfigs(prev => ({
      ...prev,
      [configToolName]: config
    }));
    
    // Update node to show configured state
    setNodes(nds => nds.map(node => {
      if (node.data?.tool_name === configToolName) {
        return {
          ...node,
          data: {
            ...node.data,
            isConfigured: true,
          }
        };
      }
      return node;
    }));
    
    setShowConfigModal(false);
  };

  const highlightNode = (nodeId: string, skipEdges: boolean = false) => {
    setActiveNodeId(nodeId);
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        data: {
          ...node.data,
          isActive: node.id === nodeId,
        },
        style: {
          ...node.style,
          opacity: node.id === nodeId ? 1 : 0.5,
          transition: 'opacity 0.3s ease',
        },
        className: node.id === nodeId ? 'active-node' : '',
      }))
    );
    
    if (!skipEdges) {
      setEdges((eds) =>
        eds.map((edge) => ({
          ...edge,
          animated: edge.source === nodeId || edge.target === nodeId,
          style: {
            stroke: edge.source === nodeId || edge.target === nodeId ? '#3b82f6' : '#b1b1b7',
            strokeWidth: edge.source === nodeId || edge.target === nodeId ? 2 : 1,
            transition: 'all 0.3s ease',
          },
        }))
      );
    }
  };

  const resetNodeHighlights = () => {
    setActiveNodeId(null);
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        data: {
          ...node.data,
          isActive: false,
        },
        style: {
          ...node.style,
          opacity: 1,
        },
        className: '',
      }))
    );
    
    setEdges((eds) =>
      eds.map((edge) => ({
        ...edge,
        animated: false,
        style: {
          stroke: '#b1b1b7',
          strokeWidth: 1,
        },
      }))
    );
  };

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    await executeAgent({ query });
  };

  const handleDynamicExecute = async (inputData: Record<string, string | number | boolean>) => {
    await executeAgent(inputData);
  };

  const executeAgent = async (inputData: Record<string, string | number | boolean>) => {
    setExecuting(true);
    setError(null);
    setResult(null);

    try {
      // Animate input node
      highlightNode('input');
      await new Promise((resolve) => setTimeout(resolve, 400));

      // Animate agent node (but don't animate edges yet - we don't know which tools will be used)
      highlightNode('agent', true); // skipEdges = true
      
      // Build query from input data based on trigger type
      let queryString = '';
      if (inputData.query) {
        queryString = String(inputData.query);
      } else {
        // For non-text-query types, build query from input data
        queryString = JSON.stringify(inputData);
      }
      
      // Execute actual agent in parallel with animation
      const executionPromise = agentApi.executeAgent(agentId, queryString, toolConfigs);
      await new Promise((resolve) => setTimeout(resolve, 600));

      // Wait for execution to complete
      const response = await executionPromise;

      // Collect IDs of nodes that should be animated (only used tools)
      const usedToolIds = new Set<string>();
      const toolNodes = nodes.filter(n => n.type === 'tool');
      
      if (toolNodes.length > 0 && response.intermediate_steps && response.intermediate_steps.length > 0) {
        // Extract tool names from intermediate steps
        const usedTools = new Set<string>();
        response.intermediate_steps.forEach((step: unknown) => {
          if (typeof step === 'object' && step !== null) {
            const stepObj = step as Record<string, unknown>;
            // LangChain intermediate steps format: [action, observation]
            if (Array.isArray(stepObj) && stepObj.length >= 1) {
              const action = stepObj[0] as Record<string, unknown>;
              if (action && typeof action.tool === 'string') {
                usedTools.add(action.tool);
              }
            }
          }
        });

        // Find tool node IDs that match used tools
        toolNodes.forEach((toolNode) => {
          const toolName = toolNode.data?.tool_name || toolNode.data?.label;
          if (usedTools.has(toolName)) {
            usedToolIds.add(toolNode.id);
          }
        });
      }

      // Animate only the tools that were actually used
      if (usedToolIds.size > 0) {
        for (const toolId of usedToolIds) {
          // Temporarily set only this tool and its edges as active
          setNodes((nds) =>
            nds.map((node) => ({
              ...node,
              style: {
                ...node.style,
                opacity: node.id === toolId ? 1 : 0.5,
              },
            }))
          );
          
          setEdges((eds) =>
            eds.map((edge) => ({
              ...edge,
              animated: edge.source === toolId || edge.target === toolId,
              style: {
                stroke: edge.source === toolId || edge.target === toolId ? '#3b82f6' : '#b1b1b7',
                strokeWidth: edge.source === toolId || edge.target === toolId ? 2 : 1,
              },
            }))
          );
          
          await new Promise((resolve) => setTimeout(resolve, 400));
        }
      }

      // Animate output node
      highlightNode('output');
      await new Promise((resolve) => setTimeout(resolve, 400));

      setResult(response);
      
      // Reset after a brief pause
      await new Promise((resolve) => setTimeout(resolve, 300));
      resetNodeHighlights();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to execute agent';
      setError(message);
      resetNodeHighlights();
    } finally {
      setExecuting(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading workflow...</p>
        </div>
      </div>
    );
  }

  if (error && !nodes.length) {
    return (
      <div className="h-full flex items-center justify-center bg-red-50">
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
    <div className="h-full w-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
        nodesDraggable={!executing}
        nodesConnectable={false}
        elementsSelectable={!executing}
        attributionPosition="bottom-right"
      >
        <Background />
        <Controls position="bottom-left" />
        <MiniMap
          position="bottom-right"
          nodeColor={(node) => {
            if (activeNodeId === node.id) return '#3b82f6';
            switch (node.type) {
              case 'input': return '#93c5fd';
              case 'agent': return '#c4b5fd';
              case 'tool': return '#86efac';
              case 'output': return '#fdba74';
              case 'decision': return '#fde047';
              default: return '#e5e7eb';
            }
          }}
          pannable
          zoomable
        />
      </ReactFlow>

      {/* Playground Button */}
      <button
        onClick={() => setShowPlayground(!showPlayground)}
        className="absolute top-4 right-4 z-20 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center gap-2 transition-all"
      >
        <span>{showPlayground ? '✕' : '▶'}</span>
        <span>{showPlayground ? 'Close' : 'Playground'}</span>
      </button>

      {/* Playground Panel */}
      {showPlayground && (
        <div className="absolute top-16 right-4 w-96 max-w-[calc(100vw-2rem)] bg-white rounded-lg shadow-2xl z-10 max-h-[calc(100vh-10rem)] overflow-hidden flex flex-col border border-gray-200">
          <div className="p-6 overflow-y-auto flex-1">
            {/* Dynamic Playground based on workflow config */}
            {workflowConfig.trigger_type === 'text_query' ? (
              // Legacy text query form for backward compatibility
              <>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Agent Playground</h3>
                <form onSubmit={handleExecute} className="space-y-4">
                  <div>
                    <label htmlFor="query" className="block text-sm font-medium text-gray-700 mb-2">
                      Your Query
                    </label>
                    <textarea
                      id="query"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      rows={4}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm"
                      placeholder="Ask the agent to perform a task..."
                      disabled={executing}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={executing || !query.trim()}
                    className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-all"
                  >
                    {executing ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>Executing...</span>
                      </span>
                    ) : (
                      'Execute'
                    )}
                  </button>
                </form>
              </>
            ) : (
              // Use DynamicPlayground for other trigger types
              <DynamicPlayground
                triggerType={workflowConfig.trigger_type}
                inputFields={workflowConfig.input_fields}
                onExecute={handleDynamicExecute}
                loading={executing}
              />
            )}

            {error && (
              <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
                {error}
              </div>
            )}

            {result && (
              <div className="mt-4">
                <h4 className="text-sm font-semibold text-gray-900 mb-2">Result</h4>
                {result.success ? (
                  <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                    <div className="flex items-start gap-2 mb-2">
                      <span className="text-green-600 text-lg">✓</span>
                      <span className="text-xs font-medium text-green-700">Success</span>
                    </div>
                    <div className="text-green-800 text-sm whitespace-pre-wrap">{result.output}</div>
                    {result.intermediate_steps && result.intermediate_steps.length > 0 && (
                      <details className="mt-3">
                        <summary className="text-xs font-medium text-green-700 cursor-pointer hover:text-green-900">
                          View Execution Steps ({result.intermediate_steps.length})
                        </summary>
                        <div className="mt-2 space-y-1">
                          {result.intermediate_steps.map((step: unknown, idx: number) => (
                            <div key={idx} className="text-xs bg-green-100 p-2 rounded">
                              <span className="font-mono text-green-900">Step {idx + 1}</span>
                              <pre className="mt-1 overflow-auto">{JSON.stringify(step, null, 2)}</pre>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                ) : (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <div className="flex items-start gap-2 mb-2">
                      <span className="text-red-600 text-lg">✗</span>
                      <span className="text-xs font-medium text-red-700">Failed</span>
                    </div>
                    <div className="text-red-700 text-sm">{result.error || 'Execution failed'}</div>
                  </div>
                )}
              </div>
            )}  
          </div>
        </div>
      )}

      {/* Tool Configuration Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowConfigModal(false)}>
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Configure {configToolName}
            </h3>
            <ToolConfigForm
              toolName={configToolName}
              initialConfig={toolConfigs[configToolName] || {}}
              onSave={handleSaveConfig}
              onCancel={() => setShowConfigModal(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// Tool Configuration Form Component
interface ToolConfigFormProps {
  toolName: string;
  initialConfig: Record<string, string>;
  onSave: (config: Record<string, string>) => void;
  onCancel: () => void;
}

function ToolConfigForm({ toolName, initialConfig, onSave, onCancel }: ToolConfigFormProps) {
  const [config, setConfig] = useState(initialConfig);

  const getConfigFields = (tool: string): Array<{ key: string; label: string; type: string; placeholder: string }> => {
    const name = tool.toLowerCase();
    
    if (name.includes('gmail')) {
      return [{ key: 'api_key', label: 'Gmail API Key', type: 'password', placeholder: 'Enter your Gmail API key' }];
    }
    if (name.includes('stripe')) {
      return [{ key: 'api_key', label: 'Stripe API Key', type: 'password', placeholder: 'sk_test_...' }];
    }
    if (name.includes('paypal')) {
      return [{ key: 'api_key', label: 'PayPal API Key', type: 'password', placeholder: 'Enter your PayPal API key' }];
    }
    if (name.includes('salesforce')) {
      return [{ key: 'api_key', label: 'Salesforce API Key', type: 'password', placeholder: 'Enter your Salesforce API key' }];
    }
    if (name.includes('aws') || name.includes('s3')) {
      return [
        { key: 'api_key', label: 'AWS Access Key ID', type: 'password', placeholder: 'AKIA...' },
        { key: 'secret_key', label: 'AWS Secret Access Key', type: 'password', placeholder: 'Enter secret key' },
        { key: 'region', label: 'AWS Region (Optional)', type: 'text', placeholder: 'us-east-1' }
      ];
    }
    if (name.includes('dropbox')) {
      return [{ key: 'access_token', label: 'Dropbox Access Token', type: 'password', placeholder: 'Enter your Dropbox access token' }];
    }
    if (name.includes('qbo')) {
      return [{ key: 'api_key', label: 'QuickBooks API Key', type: 'password', placeholder: 'Enter your QBO API key' }];
    }
    if (name.includes('analytics')) {
      return [{ key: 'api_key', label: 'Google Analytics API Key', type: 'password', placeholder: 'Enter your Google Analytics API key or OAuth token' }];
    }
    if (name.includes('sheets')) {
      return [{ key: 'api_key', label: 'Google Sheets API Key', type: 'password', placeholder: 'Enter your Google Sheets API key or OAuth token' }];
    }
    
    // Generic API tool
    return [{ key: 'api_key', label: 'API Key', type: 'password', placeholder: 'Enter API key' }];
  };

  const fields = getConfigFields(toolName);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(config);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {fields.map(field => (
        <div key={field.key}>
          <label htmlFor={field.key} className="block text-sm font-medium text-gray-700 mb-1">
            {field.label}
          </label>
          <input
            type={field.type}
            id={field.key}
            value={config[field.key] || ''}
            onChange={(e) => setConfig({ ...config, [field.key]: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm"
            placeholder={field.placeholder}
          />
        </div>
      ))}
      
      <div className="flex gap-2 pt-2">
        <button
          type="submit"
          className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium"
        >
          Save Configuration
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400 text-sm font-medium"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
