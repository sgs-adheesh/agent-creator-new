import { useEffect, useState, useCallback, useRef } from 'react';
import * as React from 'react';
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { nodeTypes } from './nodeTypes';
import { agentApi, type WorkflowGraph, type ExecuteAgentResponse, type WorkflowConfig } from '../services/api';
import { DynamicPlayground } from './DynamicPlayground';
import { DataVisualization } from './DataVisualization';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

// ============================================================================
// MARKDOWN RENDERER COMPONENT
// ============================================================================
function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="markdown-content max-w-none" style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ ...props }) => <h1 className="text-3xl font-bold text-gray-900 mt-8 mb-4" style={{ fontFamily: 'inherit' }} {...props} />,
          h2: ({ ...props }) => <h2 className="text-2xl font-bold text-indigo-900 mt-6 mb-4" style={{ fontFamily: 'inherit' }} {...props} />,
          h3: ({ ...props }) => <h3 className="text-xl font-semibold text-indigo-800 mt-5 mb-3" style={{ fontFamily: 'inherit' }} {...props} />,
          h4: ({ ...props }) => <h4 className="text-lg font-semibold text-gray-800 mt-4 mb-2" style={{ fontFamily: 'inherit' }} {...props} />,
          p: ({ ...props }) => <p className="text-gray-700 text-base mb-3 leading-relaxed" style={{ fontFamily: 'inherit' }} {...props} />,
          ul: ({ ...props }) => <ul className="list-disc list-outside ml-6 mb-4 space-y-2" style={{ fontFamily: 'inherit' }} {...props} />,
          ol: ({ ...props }) => <ol className="list-decimal list-outside ml-6 mb-4 space-y-2" style={{ fontFamily: 'inherit' }} {...props} />,
          li: ({ ...props }) => <li className="text-gray-700 leading-relaxed" style={{ fontFamily: 'inherit' }} {...props} />,
          strong: ({ ...props }) => <strong className="font-bold text-indigo-900" style={{ fontFamily: 'inherit' }} {...props} />,
          em: ({ ...props }) => <em className="italic text-gray-700" style={{ fontFamily: 'inherit' }} {...props} />,
          blockquote: ({ ...props }) => <blockquote className="border-l-4 border-amber-500 bg-amber-50 pl-4 py-2 my-4 italic text-gray-800" style={{ fontFamily: 'inherit' }} {...props} />,
          code: ({ ...props }) => <code className="bg-gray-100 text-indigo-600 px-1.5 py-0.5 rounded text-sm" style={{ fontFamily: 'ui-monospace, monospace' }} {...props} />,
          pre: ({ ...props }) => <pre className="bg-gray-100 p-4 rounded-lg overflow-auto my-3" style={{ fontFamily: 'ui-monospace, monospace' }} {...props} />,
          table: ({ ...props }) => (
            <div className="overflow-x-auto my-4">
              <table className="min-w-full border-collapse border border-gray-300" style={{ fontFamily: 'inherit' }} {...props} />
            </div>
          ),
          thead: ({ ...props }) => <thead className="bg-indigo-100" style={{ fontFamily: 'inherit' }} {...props} />,
          th: ({ ...props }) => (
            <th className="border border-gray-300 px-4 py-2 text-left text-sm font-semibold text-gray-900" style={{ fontFamily: 'inherit' }} {...props} />
          ),
          tbody: ({ ...props }) => <tbody className="bg-white" style={{ fontFamily: 'inherit' }} {...props} />,
          tr: ({ ...props }) => <tr className="even:bg-gray-50" style={{ fontFamily: 'inherit' }} {...props} />,
          td: ({ ...props }) => (
            <td className="border border-gray-300 px-4 py-2 text-sm text-gray-700" style={{ fontFamily: 'inherit' }} {...props} />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

// ============================================================================
// TOOL CONFIGURATION FORM COMPONENT
// ============================================================================
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
            className="w-full px-3 py-2 border border-gray-300 rounded-xl focus:ring-blue-500 focus:border-blue-500 text-sm"
            placeholder={field.placeholder}
          />
        </div>
      ))}
      
      <div className="flex gap-2 pt-2">
        <button
          type="submit"
          className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-xl hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium"
        >
          Save Configuration
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-xl hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400 text-sm font-medium"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

// ============================================================================
// DATA VISUALIZATION WRAPPER
// ============================================================================
function ResultDataVisualization({ data }: { data: unknown }) {  
  return <DataVisualization data={data} title="Data Analysis" />;
}

// ============================================================================
// MAIN WORKFLOW CANVAS COMPONENT
// ============================================================================
interface WorkflowCanvasProps {
  agentId: string;
  viewMode?: 'full' | 'workflow-only' | 'playground-only';
}

export default function WorkflowCanvas({ agentId, viewMode = 'full' }: WorkflowCanvasProps) {
  // State management
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPlayground, setShowPlayground] = useState(viewMode === 'playground-only');
  const [query, setQuery] = useState('');
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<ExecuteAgentResponse | null>(null);
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
  const resultRef = useRef<HTMLDivElement>(null);
  const [showInputForm, setShowInputForm] = useState(true);

  // ============================================================================
  // WORKFLOW LOADING
  // ============================================================================
  const loadWorkflow = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const agentData = await agentApi.getAgent(agentId);
      
      if (agentData.workflow_config) {
        setWorkflowConfig(agentData.workflow_config);
      }
      
      const workflow: WorkflowGraph = await agentApi.getWorkflow(agentId, false);
      
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
  }, [agentId, setNodes, setEdges, toolConfigs]);

  useEffect(() => {
    loadWorkflow();
  }, [loadWorkflow]);

  // Create a ref to access ReactFlow instance
  const reactFlowInstance = React.useRef<{ fitView: (options?: { padding?: number; maxZoom?: number }) => void } | null>(null);

  // Re-trigger fitView when panel resizes
  useEffect(() => {
    if (!reactFlowInstance.current) return;

    const handleResize = () => {
      setTimeout(() => {
        if (reactFlowInstance.current) {
          reactFlowInstance.current.fitView({ padding: 0.2, maxZoom: 1 });
        }
      }, 0);
    };

    // Create ResizeObserver for this component's container
    const container = document.getElementById('workflow-container');
    let resizeObserver: ResizeObserver | null = null;
    
    if (container) {
      resizeObserver = new ResizeObserver(() => {
        handleResize();
      });
      resizeObserver.observe(container);
    }

    // Also listen to window resize
    window.addEventListener('resize', handleResize);
    
    return () => {
      window.removeEventListener('resize', handleResize);
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
    };
  }, [reactFlowInstance.current]);

  const onInit = (instance: { fitView: (options?: { padding?: number; maxZoom?: number }) => void }) => {
    reactFlowInstance.current = instance;
    // Initial fit
    instance.fitView({ padding: 0.2, maxZoom: 1 });
  };

  const handleDownloadPDF = async () => {
    if (!resultRef.current) return;

    try {
      const canvas = await html2canvas(resultRef.current, {
        scale: 2,
        useCORS: true,
        logging: false,
      });

      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
      });

      const imgWidth = 210; // A4 width in mm
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;
      let position = 0;

      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
      heightLeft -= 297; // A4 height in mm

      while (heightLeft > 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= 297;
      }

      pdf.save(`agent-result-${new Date().toISOString().split('T')[0]}.pdf`);
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Failed to generate PDF. Please try again.');
    }
  };

  // ============================================================================
  // TOOL CONFIGURATION HANDLERS
  // ============================================================================
  const handleToolConfigure = (toolName: string) => {
    const excludedTools = ['postgres_query', 'postgres_inspect_schema', 'qdrant_connector', 'qdrant_search', 'QdrantConnector', 'PostgresConnector'];
    if (excludedTools.some(excluded => toolName.toLowerCase().includes(excluded.toLowerCase()))) {
      return;
    }
    
    setConfigToolName(toolName);
    setShowConfigModal(true);
  };

  const handleSaveConfig = (config: Record<string, string>) => {
    setToolConfigs(prev => ({
      ...prev,
      [configToolName]: config
    }));
    
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

  // ============================================================================
  // NODE ANIMATION HANDLERS
  // ============================================================================
  const highlightNode = (nodeId: string, skipEdges: boolean = false) => {
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

  // ============================================================================
  // QUERY EXECUTION HANDLERS
  // ============================================================================
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
      const queryTemplate = convertToTemplate(executedQuery, workflowConfig.trigger_type);
      const parameters = getParametersForTriggerType(workflowConfig.trigger_type);
      
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
      
      alert('✅ Query cached successfully! Future executions will use this query template.');
      setExecutedQuery(null);
    } catch (err) {
      console.error('Error caching query:', err);
      alert('❌ Failed to cache query. Please try again.');
    } finally {
      setCachingQuery(false);
    }
  };
  
  const convertToTemplate = (query: string, triggerType: string): string => {
    if (triggerType === 'month_year') {
      return query.replace(/(\d{2})\/%\/(\d{4})/g, '{month}/%/{year}');
    } else if (triggerType === 'year') {
      return query.replace(/\b(20\d{2})\b/g, '{year}');
    } else if (triggerType === 'date_range') {
      return query.replace(/(\d{2}\/\d{2}\/\d{4})/g, (_match, index) => {
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
      highlightNode('input');
      await new Promise((resolve) => setTimeout(resolve, 400));

      highlightNode('agent', true);
      
      let queryString = '';
      if (inputData.query) {
        queryString = String(inputData.query);
      } else {
        queryString = JSON.stringify(inputData);
      }
      
      const executionPromise = agentApi.executeAgent(agentId, queryString, toolConfigs, inputData);
      await new Promise((resolve) => setTimeout(resolve, 600));

      const response = await executionPromise;

      const usedToolIds = new Set<string>();
      const toolNodes = nodes.filter(n => n.type === 'tool');
      
      if (toolNodes.length > 0 && response.intermediate_steps && response.intermediate_steps.length > 0) {
        const usedTools = new Set<string>();
        response.intermediate_steps.forEach((step: unknown) => {
          if (typeof step === 'object' && step !== null) {
            const stepObj = step as Record<string, unknown>;
            if (Array.isArray(stepObj) && stepObj.length >= 1) {
              const action = stepObj[0] as Record<string, unknown>;
              if (action && typeof action.tool === 'string') {
                usedTools.add(action.tool);
              }
            }
          }
        });

        toolNodes.forEach((toolNode) => {
          const toolName = toolNode.data?.tool_name || toolNode.data?.label;
          if (usedTools.has(toolName)) {
            usedToolIds.add(toolNode.id);
          }
        });
      }

      if (usedToolIds.size > 0) {
        for (const toolId of usedToolIds) {
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

      highlightNode('output');
      await new Promise((resolve) => setTimeout(resolve, 400));

      setResult(response);
      
      // Extract SQL query from intermediate steps
      if (response.intermediate_steps && response.intermediate_steps.length > 0) {
        response.intermediate_steps.forEach((step: unknown) => {
          if (typeof step === 'object' && step !== null) {
            const typedStep = step as Record<string, unknown>;
            if (typedStep.action && typeof typedStep.action === 'object') {
              const action = typedStep.action as Record<string, unknown>;
              if (action.tool === 'postgres_query' && action.tool_input && typeof action.tool_input === 'object') {
                const toolInput = action.tool_input as Record<string, unknown>;
                if (toolInput.query && typeof toolInput.query === 'string') {
                  setExecutedQuery(toolInput.query);
                }
              }
            }
          }
        });
      }
      
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

  // ============================================================================
  // LOADING & ERROR STATES
  // ============================================================================
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
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ============================================================================
  // RENDER: SPLIT VIEW BASED ON viewMode
  // ============================================================================
  return (
    <div style={{ width: '100%', height: '100%', overflow: 'hidden' }} id="workflow-container">
      {/* WORKFLOW VISUALIZATION (full or workflow-only mode) */}
      {(viewMode === 'full' || viewMode === 'workflow-only') && (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onInit={onInit}
          fitView
          fitViewOptions={{ padding: 0.2, maxZoom: 1 }}
          nodesDraggable={!executing}
          nodesConnectable={false}
          elementsSelectable={!executing}
          proOptions={{ hideAttribution: true }}
          style={{ width: '100%', height: '100%' }}
        >
          <Background />
          <Controls position="bottom-left" />
        </ReactFlow>
      )}

      {/* PLAYGROUND PANEL (full or playground-only mode) */}
      {(viewMode === 'full' || viewMode === 'playground-only') && (
        <div className={viewMode === 'playground-only' ? 'h-full flex flex-col overflow-hidden' : 'absolute top-0 right-0'}>
          {/* Toggle button for full mode */}
          {viewMode === 'full' && (
            <button
              onClick={() => setShowPlayground(!showPlayground)}
              className="absolute top-4 right-4 z-20 bg-blue-600 text-white px-4 py-2 rounded-xl hover:bg-blue-700"
            >
              <span>{showPlayground ? '✕' : '▶'}</span>
              <span className="ml-2">{showPlayground ? 'Close' : 'Playground'}</span>
            </button>
          )}
          
          {/* Playground content */}
          {(viewMode === 'playground-only' || showPlayground) && (
            <div className={viewMode === 'playground-only' ? 'h-full flex flex-col overflow-hidden bg-gradient-to-br from-indigo-50 to-blue-50' : 'absolute top-16 right-4 w-96 bg-white rounded-xl z-10 max-h-[calc(100vh-10rem)] overflow-y-auto p-8 border border-gray-100'}>
              {/* Input Form */}
              <div className="flex-shrink-0 p-6">
              <div className="flex justify-between items-center mb-6">
                {workflowConfig.trigger_type === 'text_query' ? (
                  <h3 className="text-lg font-semibold text-gray-800">Agent Playground</h3>
                ) : (
                  <h3 className="text-lg font-semibold text-gray-800">Execute Agent</h3>
                )}
                <button
                  onClick={() => setShowInputForm(!showInputForm)}
                  className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-2 font-medium"
                >
                  {showInputForm ? 'Hide' : 'Show'} Playground
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={showInputForm ? 'M5 15l7-7 7 7' : 'M19 9l-7 7-7-7'} />
                  </svg>
                </button>
              </div>
              {showInputForm && (
              <div className='shadow-xl rounded-xl p-6'>
              {workflowConfig.trigger_type === 'text_query' ? (
                
                <form onSubmit={handleExecute} className="space-y-6">
                  <div>
                    <label htmlFor="query" className="block text-sm font-medium text-gray-700 mb-2">
                      Your Query
                    </label>
                    <textarea
                      id="query"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      rows={4}
                      className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-blue-500 focus:border-blue-500"
                      placeholder="Ask the agent to perform a task..."
                      disabled={executing}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={executing || !query.trim()}
                    className="w-full bg-blue-600 text-white px-6 py-3 rounded-xl hover:bg-blue-700 disabled:opacity-50 font-medium"
                  >
                    {executing ? 'Executing...' : 'Execute'}
                  </button>
                </form>
              ) : (
                <DynamicPlayground
                  triggerType={workflowConfig.trigger_type}
                  inputFields={workflowConfig.input_fields}
                  onExecute={handleDynamicExecute}
                  loading={executing}
                />
              )}
              </div>
              )}
              </div>

              {/* Error Display */}
              {error && (
                <div className="my-2 bg-red-50 border border-red-100 text-red-700 px-6 py-4 rounded-xl flex-shrink-0">
                  {error}
                </div>
              )}

              {/* Results Section with Scroll */}
              <div className="flex-1 overflow-y-auto mt-2 bg-indigo-50 rounded-xl">
              {result && (
                <div className="space-y-4 bg-indigo-50">
                  <div className="px-6">
                  <div className="flex justify-between items-center mb-6">
                    <h4 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">Execution Results</h4>
                    {result.success && (
                      <button
                        onClick={handleDownloadPDF}
                        className="bg-green-600 text-white px-3 py-2 rounded-xl hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 flex items-center gap-2"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        Download PDF
                      </button>
                    )}
                  </div>
                  </div>
                  <div ref={resultRef}>
                  {result.success ? (
                    <div className="space-y-4">
                      {/* Success indicator */}
                      <div className="space-y-8 p-6">
                      <div className="bg-gradient-to-br from-green-50 to-emerald-50 border-1 border-green-200 rounded-xl p-4">
                        <div className="flex items-start gap-3">
                          <span className="text-green-600 text-xl">✓</span>
                          <span className="text-sm font-medium text-green-700 mt-1">Execution Successful</span>
                        </div>
                        
                        {/* Auto-saved query notification */}
                        {result.query_auto_saved && (
                          <div className="mt-3 pt-3 border-t border-green-200">
                            <div className="flex items-start gap-2">
                              <span className="text-green-600">💾</span>
                              <div className="flex-1">
                                <p className="text-xs font-semibold text-green-700 mt-1">Query Auto-Saved</p>
                                <p className="text-xs text-green-600 mt-1">
                                  This successful query has been saved to the agent. Future executions will be faster!
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                        
                        {/* Query correction notification */}
                        {result.query_corrected && (
                          <div className="mt-3 pt-3 border-t border-green-200">
                            <div className="flex items-start gap-2">
                              <span className="text-green-600">🔧</span>
                              <div className="flex-1">
                                <p className="text-xs font-semibold text-green-700">Query Corrected & Saved</p>
                                <p className="text-xs text-green-600 mt-1">
                                  AI corrected the query and saved it for future use. Attempt {result.query_attempts || 'N/A'}.
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                      
                      {/* Text output */}
                      {result.output && (
                        <div className="bg-gradient-to-br from-white to-indigo-50 border-1 border-indigo-100 rounded-xl p-8">
                          <div className="mb-6">
                            <h4 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">Output</h4>
                            <p className="text-sm text-gray-600 mt-1">Agent response and analysis</p>
                          </div>
                          <MarkdownRenderer content={result.output} />
                        </div>
                      )}
                      </div>
                      {/* Data Visualization */}
                      <div>
                        <ResultDataVisualization data={result} />
                      </div>
                      
                      {/* Approve & Cache Query Button */}
                      {executedQuery && !(result as unknown as Record<string, unknown>).cached_execution && workflowConfig.trigger_type !== 'text_query' && (
                        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border-1 border-blue-200 rounded-xl p-6">
                          <div className="mb-4">
                            <h4 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">Save Query Template</h4>
                            <p className="text-sm text-blue-600 mt-1">
                              💡 Would you like to save this query for instant future execution?
                            </p>
                          </div>
                          <button
                            onClick={handleApproveAndCacheQuery}
                            disabled={cachingQuery}
                            className="bg-blue-600 text-white px-6 py-2.5 rounded-xl hover:bg-blue-700 disabled:opacity-50 font-medium"
                          >
                            {cachingQuery ? '⏳ Loading...' : '✅ Approve'}
                          </button>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="bg-gradient-to-br from-red-50 to-pink-50 border-1 border-red-200 rounded-xl p-6">
                      <div className="flex items-start gap-3 mb-3">
                        <span className="text-red-600 text-xl">✗</span>
                        <span className="text-sm font-medium text-red-700">Execution Failed</span>
                      </div>
                      <div className="text-red-700">{result.error || 'Execution failed'}</div>
                    </div>
                  )}
                  </div>
                </div>
              )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TOOL CONFIGURATION MODAL */}
      {showConfigModal && (
        <div className="fixed inset-0 bg-black bg-opacity-20 flex items-center justify-center z-50" onClick={() => setShowConfigModal(false)}>
          <div className="bg-white rounded-xl  p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
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
