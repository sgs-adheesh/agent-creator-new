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
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Markdown Renderer Component using react-markdown
function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="markdown-content prose prose-sm max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Customize table styling
          table: ({ node, ...props }) => (
            <div className="overflow-x-auto my-3">
              <table className="min-w-full border-collapse border border-green-300" {...props} />
            </div>
          ),
          thead: ({ node, ...props }) => (
            <thead className="bg-green-100" {...props} />
          ),
          th: ({ node, ...props }) => (
            <th className="border border-green-300 px-3 py-2 text-left text-xs font-semibold text-green-900" {...props} />
          ),
          tbody: ({ node, ...props }) => (
            <tbody className="bg-white" {...props} />
          ),
          tr: ({ node, ...props }) => (
            <tr className="even:bg-green-50" {...props} />
          ),
          td: ({ node, ...props }) => (
            <td className="border border-green-300 px-3 py-2 text-xs text-green-800" {...props} />
          ),
          // Customize text elements
          p: ({ node, ...props }) => (
            <p className="text-green-800 text-sm mb-2" {...props} />
          ),
          strong: ({ node, ...props }) => (
            <strong className="font-semibold" {...props} />
          ),
          code: ({ node, ...props }) => (
            <code className="bg-green-100 px-1 rounded text-xs" {...props} />
          ),
          pre: ({ node, ...props }) => (
            <pre className="bg-green-100 p-3 rounded text-xs overflow-auto my-2" {...props} />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

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
  const [executedQuery, setExecutedQuery] = useState<string | null>(null);
  const [cachingQuery, setCachingQuery] = useState(false);

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
    // Skip configuration for postgres and qdrant (use .env config)
    const excludedTools = ['postgres_query', 'postgres_inspect_schema', 'qdrant_connector', 'qdrant_search', 'QdrantConnector', 'PostgresConnector'];
    if (excludedTools.some(excluded => toolName.toLowerCase().includes(excluded.toLowerCase()))) {
      return; // Don't show config modal for these tools
    }
    
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

  const handleApproveAndCacheQuery = async () => {
    if (!executedQuery) return;
    
    setCachingQuery(true);
    try {
      // Convert static query to dynamic template
      const queryTemplate = convertToTemplate(executedQuery, workflowConfig.trigger_type);
      
      // Determine parameters based on trigger type
      const parameters = getParametersForTriggerType(workflowConfig.trigger_type);
      
      // Call cache endpoint
      const response = await fetch(`http://localhost:8000/api/agents/${agentId}/cache-query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query_template: queryTemplate,
          parameters: parameters,
          tables: extractTablesFromQuery(executedQuery),
          joins: extractJoinsFromQuery(executedQuery)
        })
      });
      
      if (!response.ok) throw new Error('Failed to cache query');
      
      // Show success message
      alert('✅ Query cached successfully! Future executions will use this query template.');
      setExecutedQuery(null); // Hide button after caching
    } catch (err) {
      console.error('Error caching query:', err);
      alert('❌ Failed to cache query. Please try again.');
    } finally {
      setCachingQuery(false);
    }
  };
  
  const convertToTemplate = (query: string, triggerType: string): string => {
    if (triggerType === 'month_year') {
      // Replace patterns like '02/%/2025' with '{month}/%/{year}'
      return query.replace(/(\d{2})\/%\/(\d{4})/g, '{month}/%/{year}');
    } else if (triggerType === 'year') {
      // Replace year patterns
      return query.replace(/\b(20\d{2})\b/g, '{year}');
    } else if (triggerType === 'date_range') {
      // Replace date range patterns
      return query.replace(/(\d{2}\/\d{2}\/\d{4})/g, (match, index) => {
        return index === 0 ? '{start_date}' : '{end_date}';
      });
    }
    return query;
  };
  
  const getParametersForTriggerType = (triggerType: string): string[] => {
    switch (triggerType) {
      case 'month_year': return ['month', 'year'];
      case 'year': return ['year'];
      case 'date_range': return ['start_date', 'end_date'];
      default: return [];
    }
  };
  
  const extractTablesFromQuery = (query: string): string[] => {
    const tables: string[] = [];
    const fromMatch = query.match(/FROM\s+(\w+)/gi);
    const joinMatch = query.match(/JOIN\s+(\w+)/gi);
    
    if (fromMatch) {
      fromMatch.forEach(m => {
        const table = m.replace(/FROM\s+/i, '');
        if (!tables.includes(table)) tables.push(table);
      });
    }
    if (joinMatch) {
      joinMatch.forEach(m => {
        const table = m.replace(/JOIN\s+/i, '');
        if (!tables.includes(table)) tables.push(table);
      });
    }
    
    return tables;
  };
  
  const extractJoinsFromQuery = (query: string): string[] => {
    const joins: string[] = [];
    const joinMatches = query.match(/LEFT\s+JOIN\s+[^;]+?(?=LEFT\s+JOIN|WHERE|ORDER|GROUP|$)/gi);
    
    if (joinMatches) {
      joins.push(...joinMatches);
    }
    
    return joins;
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
      
      // Extract SQL query from intermediate steps for postgres_query tool
      console.log('🔍 ======= APPROVE BUTTON DEBUG =======');
      console.log('🔍 Full response:', JSON.stringify(response, null, 2));
      console.log('🔍 intermediate_steps exists:', !!response.intermediate_steps);
      console.log('🔍 intermediate_steps length:', response.intermediate_steps?.length);
      console.log('🔍 cached_execution flag:', (response as any).cached_execution);
      console.log('🔍 trigger_type:', workflowConfig.trigger_type);
      console.log('🔍 Current executedQuery state (before):', executedQuery);
      
      if (response.intermediate_steps && response.intermediate_steps.length > 0) {
        let foundQuery = false;
        response.intermediate_steps.forEach((step: any, index: number) => {
          console.log(`🔍 Step ${index}:`, JSON.stringify(step, null, 2));
          
          // New structure: {action: {tool, tool_input}, result}
          if (step.action && step.action.tool === 'postgres_query' && step.action.tool_input) {
            console.log('🔍 Found postgres_query! Tool input:', step.action.tool_input);
            console.log('🔍 Query value:', step.action.tool_input.query);
            console.log('🔍 Query type:', typeof step.action.tool_input.query);
            
            if (step.action.tool_input.query && typeof step.action.tool_input.query === 'string') {
              console.log('✅ SUCCESS! Setting executedQuery to:', step.action.tool_input.query);
              setExecutedQuery(step.action.tool_input.query);
              foundQuery = true;
            } else {
              console.warn('⚠️ Query exists but wrong type or empty');
            }
          }
        });
        
        if (!foundQuery) {
          console.warn('⚠️ No postgres_query found in any intermediate step');
        } else {
          console.log('✅ Query extraction completed successfully');
        }
      } else {
        console.warn('⚠️ No intermediate_steps in response or empty array');
      }
      
      // Debug: Check executedQuery state after setting
      setTimeout(() => {
        console.log('🔍 Current executedQuery state (after 100ms):', executedQuery);
        console.log('🔍 Approve button condition check:');
        console.log('  - executedQuery:', !!executedQuery);
        console.log('  - !cached_execution:', !(response as any).cached_execution);
        console.log('  - trigger_type !== text_query:', workflowConfig.trigger_type !== 'text_query');
        console.log('  - Should show button:', !!executedQuery && !(response as any).cached_execution && workflowConfig.trigger_type !== 'text_query');
        console.log('🔍 ======= END DEBUG =======');
      }, 100);
      
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
                    
                    {/* CSV Download */}
                    {(result as any).output_format === 'csv' && (result as any).download_link && (
                      <div className="mb-3">
                        <a
                          href={(result as any).download_link}
                          download={(result as any).csv_filename || 'report.csv'}
                          className="inline-flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 transition-colors text-sm font-medium"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          Download CSV Report
                        </a>
                        <p className="text-xs text-green-700 mt-2">{(result as any).csv_filename}</p>
                      </div>
                    )}
                    
                    {/* Summary Section */}
                    {(result as any).summary && (result as any).summary.full_summary && (
                      <div className="mb-3 p-4 bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-300 rounded-lg shadow-sm">
                        <div className="flex items-center gap-2 mb-3">
                          <span className="text-2xl">📊</span>
                          <h3 className="text-base font-bold text-blue-900">Detailed Query Summary</h3>
                        </div>
                        
                        {/* Render markdown summary */}
                        <div className="prose prose-sm max-w-none">
                          <MarkdownRenderer content={(result as any).summary.full_summary} />
                        </div>
                      </div>
                    )}
                    
                    {/* Table Display */}
                    {(result as any).output_format === 'table' && (result as any).table_data && (
                      <div className="mb-3 overflow-auto max-h-96">
                        <table className="min-w-full divide-y divide-green-200 text-xs">
                          <thead className="bg-green-100">
                            <tr>
                              {(result as any).table_data.columns.map((col: string, idx: number) => (
                                <th key={idx} className="px-3 py-2 text-left font-semibold text-green-900 uppercase tracking-wider">
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-green-100">
                            {(result as any).table_data.rows.map((row: Record<string, any>, idx: number) => (
                              <tr key={idx} className="hover:bg-green-50">
                                {(result as any).table_data.columns.map((col: string, colIdx: number) => {
                                  // Handle JSONB objects by extracting 'value' property
                                  const cellValue = row[col];
                                  const displayValue = 
                                    cellValue === null || cellValue === undefined 
                                      ? '-' 
                                      : typeof cellValue === 'object' && cellValue.value !== undefined
                                        ? cellValue.value  // Extract 'value' from JSONB object
                                        : typeof cellValue === 'object'
                                          ? JSON.stringify(cellValue)  // Fallback: stringify complex objects
                                          : String(cellValue);  // Convert primitives to string
                                  
                                  return (
                                    <td key={colIdx} className="px-3 py-2 text-green-800 whitespace-nowrap">
                                      {displayValue}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        <p className="text-xs text-green-700 mt-2">Showing {(result as any).table_data.row_count} rows</p>
                      </div>
                    )}
                    
                    {/* JSON Display */}
                    {(result as any).output_format === 'json' && (result as any).json_data && (
                      <div className="mb-3">
                        <pre className="bg-green-100 p-3 rounded text-xs overflow-auto max-h-96 text-green-900">
                          {JSON.stringify((result as any).json_data, null, 2)}
                        </pre>
                      </div>
                    )}
                    
                    {/* Text Output (show for non-CSV formats with Markdown support) */}
                    {(result as any).output_format !== 'csv' && (
                      <MarkdownRenderer content={result.output || ''} />
                    )}
                    
                    {/* Approve & Cache Query Button */}
                    {executedQuery && !(result as any).cached_execution && workflowConfig.trigger_type !== 'text_query' && (
                      <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <p className="text-xs text-blue-700 mb-2">
                          <strong>💡 Would you like to save this query for future use?</strong>
                          <br />
                          This will allow instant execution without re-analyzing the database.
                        </p>
                        <button
                          onClick={handleApproveAndCacheQuery}
                          disabled={cachingQuery}
                          className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium flex items-center gap-2"
                        >
                          {cachingQuery ? (
                            <>
                              <span className="animate-spin">⏳</span>
                              Caching...
                            </>
                          ) : (
                            <>
                              <span>✅</span>
                              Approve & Cache Query
                            </>
                          )}
                        </button>
                      </div>
                    )}
                    
                    {/* Show if using cached query */}
                    {(result as any).cached_execution && (
                      <div className="mt-3 p-2 bg-purple-50 border border-purple-200 rounded text-xs text-purple-700 flex items-center gap-2">
                        <span>⚡</span>
                        <span>Executed using cached query (instant response)</span>
                      </div>
                    )}
                    
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
