import { useEffect, useState, useCallback, useRef } from 'react';
import * as React from 'react';
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { nodeTypes } from './nodeTypes';
import { agentApi, type WorkflowGraph, type ExecuteAgentResponse, type WorkflowConfig } from '../services/api';
import { DynamicPlayground } from './DynamicPlayground';
import { DataVisualization } from './DataVisualization';
import ProgressPanel, { type ProgressStep } from './ProgressPanel';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SavedResultsManager from './SavedResultsManager';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';


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


function ResultDataVisualization({ data }: { data: unknown }) {
  // Extract visualization_config from result if available
  const resultData = data as ExecuteAgentResponse;
  const visualizationConfig = resultData?.visualization_config;

  return <DataVisualization data={data} title="Data Analysis" visualization_config={visualizationConfig} />;
}


interface WorkflowCanvasProps {
  agentId: string;
  viewMode?: 'full' | 'workflow-only' | 'playground-only';
}

export default function WorkflowCanvas({ agentId, viewMode = 'full' }: WorkflowCanvasProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPlayground, setShowPlayground] = useState(viewMode === 'playground-only');
  const [query, setQuery] = useState('');
  const [executing, setExecuting] = useState(false);
  const [executionStatus, setExecutionStatus] = useState<string>('Idle...');
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
  const [resultSaved, setResultSaved] = useState(true); // Track if current result is saved
  const resultRef = useRef<HTMLDivElement>(null);
  const [showInputForm, setShowInputForm] = useState(true);
  const [executionProgress, setExecutionProgress] = useState<ProgressStep[]>([]);
  const [visualizationPreferences, setVisualizationPreferences] = useState<string>('');
  const [selectedChartTypes, setSelectedChartTypes] = useState<string[]>([]);
  const [chartDropdownOpen, setChartDropdownOpen] = useState(false);

  const chartOptions = [
    { value: 'pie', label: 'Pie Chart', icon: '🥧' },
    { value: 'bar', label: 'Bar Chart', icon: '📊' },
    { value: 'line', label: 'Line Chart', icon: '📈' },
    { value: 'area', label: 'Area Chart', icon: '📉' },
    { value: 'scatter', label: 'Scatter Plot', icon: '🔍' },
    { value: 'radar', label: 'Radar Chart', icon: '🕸️' },
    { value: 'radialbar', label: 'Radial Bar', icon: '⭕' },
    { value: 'treemap', label: 'Treemap', icon: '🗺️' },
    { value: 'stacked_bar', label: 'Stacked Bar', icon: '📚' },
    { value: 'waterfall', label: 'Waterfall', icon: '🌊' },
    { value: 'candlestick', label: 'Candlestick', icon: '🕯️' },
    { value: 'bubble', label: 'Bubble Chart', icon: '🫧' },
    { value: 'heatmap', label: 'Heatmap', icon: '🔥' },
    { value: 'sankey', label: 'Sankey', icon: '🔀' },
    { value: 'funnel', label: 'Funnel', icon: '🌪️' },
    { value: 'composed', label: 'Composed Chart', icon: '📈' }
  ];

  // Convert selected chart types to string format for backend
  const getVisualizationPreferencesString = () => {
    if (selectedChartTypes.length === 0) {
      return visualizationPreferences || undefined;
    }
    // Convert array to comma-separated string: "pie, bar, line, area"
    return selectedChartTypes.join(', ');
  };


  const loadWorkflow = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const agentData = await agentApi.getAgent(agentId);

      if (agentData.workflow_config) {
        setWorkflowConfig(agentData.workflow_config);
      }

      // Load visualization preferences if stored in agent
      if (agentData.visualization_preferences) {
        setVisualizationPreferences(agentData.visualization_preferences);
        // Parse stored preferences to extract chart types
        const prefs = agentData.visualization_preferences.toLowerCase();
        const chartTypes = ['pie', 'bar', 'line', 'area', 'scatter', 'radar', 'radialbar', 'treemap',
          'stacked_bar', 'waterfall', 'candlestick', 'bubble', 'heatmap', 'sankey', 'funnel', 'composed'];
        const foundTypes = chartTypes.filter(type => prefs.includes(type));
        if (foundTypes.length > 0) {
          setSelectedChartTypes(foundTypes.slice(0, 4));
        }
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
      const enhancedEdges = (workflow.edges as Edge[]).map(edge => ({
        ...edge,
        type: 'default',
        animated: true,
        style: {
          stroke: '#8b5cf6', // Violet-500
          strokeWidth: 2,
          ...edge.style,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#8b5cf6',
        },
      }));
      setEdges(enhancedEdges);
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

  const reactFlowInstance = React.useRef<{ fitView: (options?: { padding?: number; maxZoom?: number }) => void } | null>(null);

  useEffect(() => {
    if (!reactFlowInstance.current) return;

    const handleResize = () => {
      setTimeout(() => {
        if (reactFlowInstance.current) {
          reactFlowInstance.current.fitView({ padding: 0.2, maxZoom: 1 });
        }
      }, 0);
    };

    const container = document.getElementById('workflow-container');
    let resizeObserver: ResizeObserver | null = null;

    if (container) {
      resizeObserver = new ResizeObserver(() => {
        handleResize();
      });
      resizeObserver.observe(container);
    }

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

      const imgWidth = 210;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;
      let position = 0;

      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
      heightLeft -= 297;

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
        eds.map((edge) => {
          const isRelated = edge.source === nodeId || edge.target === nodeId;
          return {
            ...edge,
            animated: true, // Keep animated
            style: {
              ...edge.style,
              stroke: isRelated ? '#3b82f6' : '#e0e7ff', // Blue active, heavy fade inactive
              strokeWidth: isRelated ? 3 : 1,
              opacity: isRelated ? 1 : 0.4,
              transition: 'all 0.4s ease',
              filter: isRelated ? 'drop-shadow(0 0 3px rgba(59, 130, 246, 0.5))' : 'none',
            },
            zIndex: isRelated ? 10 : 0,
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: isRelated ? '#3b82f6' : '#e0e7ff',
            },
          };
        })
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
        animated: true,
        style: {
          stroke: '#8b5cf6',
          strokeWidth: 2,
          opacity: 1,
          filter: 'none',
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#8b5cf6',
        },
        zIndex: 0,
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

  const handleSaveResult = async (resultName: string) => {
    if (!result) {
      alert('No result to save');
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/agents/${agentId}/results/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          result,
          name: resultName
        })
      });

      const data = await response.json();
      if (data.success) {
        setResultSaved(true);
        alert('✅ Result saved successfully!');
      } else {
        throw new Error(data.message || 'Failed to save result');
      }
    } catch (error) {
      console.error('Failed to save result:', error);
      alert('❌ Failed to save result');
    }
  };

  const handleLoadResult = async (resultId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/agents/${agentId}/results/${resultId}`);
      const data = await response.json();

      if (data.success && data.result) {
        setResult(data.result.data);
        setResultSaved(true);
        alert('✅ Result loaded successfully!');
      } else {
        throw new Error(data.message || 'Failed to load result');
      }
    } catch (error) {
      console.error('Failed to load result:', error);
      alert('❌ Failed to load result');
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
    setExecutionStatus('Initializing execution...');
    setExecuting(true);
    setError(null);
    setResult(null);

    // Initialize progress steps
    const steps: ProgressStep[] = [
      { id: '1', label: 'Preparing execution', status: 'pending' },
      { id: '2', label: 'Running tools', status: 'pending' },
      { id: '3', label: 'Processing results', status: 'pending' },
      { id: '4', label: 'Generating AI summary', status: 'pending' },
      { id: '5', label: 'Complete', status: 'pending' },
    ];
    setExecutionProgress(steps);

    try {
      setExecutionStatus('Highlighting input node...');
      highlightNode('input');
      await new Promise((resolve) => setTimeout(resolve, 400));

      setExecutionStatus('Activating agent...');
      highlightNode('agent', true);

      let queryString = '';
      if (inputData.query) {
        queryString = String(inputData.query);
      } else {
        queryString = JSON.stringify(inputData);
      }

      setExecutionStatus('Connecting to server...');
      // Use Server-Sent Events for real-time progress
      const response = await new Promise<ExecuteAgentResponse>((resolve, reject) => {
        fetch(`http://localhost:8000/api/agents/${agentId}/execute/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query: queryString,
            tool_configs: toolConfigs,
            input_data: inputData,
            visualization_preferences: getVisualizationPreferencesString()
          })
        })
          .then(response => {
            if (!response.ok) {
              setExecutionStatus('Server request failed');
              throw new Error('Streaming request failed');
            }

            setExecutionStatus('Streaming execution updates...');
            const reader = response.body?.getReader();
            if (!reader) throw new Error('No reader available');

            const decoder = new TextDecoder();

            const readStream = () => {
              reader.read().then(({ done, value }) => {
                if (done) return;

                const text = decoder.decode(value);
                const lines = text.split('\n');

                for (const line of lines) {
                  if (line.startsWith('data: ')) {
                    try {
                      const data = JSON.parse(line.substring(6));

                      if (data.type === 'progress') {
                        // Update execution status with current step
                        setExecutionStatus(data.message || `Step ${data.step}: ${data.status}`);

                        // Update progress step
                        const stepIndex = data.step - 1;
                        if (stepIndex >= 0 && stepIndex < steps.length) {
                          steps[stepIndex].status = data.status;
                          steps[stepIndex].label = data.message;
                          if (data.detail) {
                            steps[stepIndex].detail = data.detail;
                          }
                          // Handle substeps for AI progress
                          if (data.substeps) {
                            steps[stepIndex].substeps = data.substeps;
                          }
                          setExecutionProgress([...steps]);
                        }
                      } else if (data.type === 'result') {
                        // Execution complete - got final result
                        console.log('✅ Execution result received');
                        setExecutionStatus('Execution completed successfully');
                        resolve(data.data);
                        return;
                      } else if (data.type === 'error') {
                        setExecutionStatus(`Error: ${data.message}`);
                        reject(new Error(data.message));
                        return;
                      }
                    } catch (parseErr) {
                      console.error('Failed to parse SSE data:', parseErr);
                    }
                  }
                }

                readStream();
              }).catch((err) => {
                setExecutionStatus('Stream reading failed');
                reject(err);
              });
            };

            readStream();
          })
          .catch((err) => {
            setExecutionStatus('Connection error');
            reject(err);
          });

      });

      // Process response (same as before)
      setExecutionStatus('Processing response...');
      const usedToolIds = new Set<string>();
      const toolNodes = nodes.filter(n => n.type === 'tool');

      if (toolNodes.length > 0 && response.intermediate_steps && response.intermediate_steps.length > 0) {
        setExecutionStatus('Identifying used tools...');
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
        setExecutionStatus(`Highlighting ${usedToolIds.size} used tool(s)...`);
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

      setExecutionStatus('Highlighting output...');
      highlightNode('output');
      await new Promise((resolve) => setTimeout(resolve, 400));

      setResult(response);
      setResultSaved(false); // New result is not saved

      // Extract SQL query from intermediate steps
      setExecutionStatus('Extracting executed query...');
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

      setExecutionStatus('Finalizing...');
      await new Promise((resolve) => setTimeout(resolve, 300));
      resetNodeHighlights();
      setExecutionStatus('Execution complete');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to execute agent';
      setError(message);
      setExecutionStatus(`Error: ${message}`);

      // Mark current in-progress step as error
      const currentStep = steps.findIndex(s => s.status === 'in_progress');
      if (currentStep !== -1) {
        steps[currentStep].status = 'error';
        steps[currentStep].detail = message;
        setExecutionProgress([...steps]);
      }

      resetNodeHighlights();
    }
    finally {
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
          style={{ width: '100%', height: '100%', backgroundColor: '#f8fafc' }}
        >
          <Background color="#94a3b8" gap={20} size={2} />
          <Controls position="bottom-left" className="m-4 shadow-xl border-0 rounded-xl overflow-hidden" />
        </ReactFlow>
      )
      }

      {/* PLAYGROUND PANEL (full or playground-only mode) */}
      {
        (viewMode === 'full' || viewMode === 'playground-only') && (
          <div className={viewMode === 'playground-only' ? 'h-full flex flex-col overflow-hidden' : 'absolute top-0 right-0 pointer-events-none h-full w-full'}>
            {/* Toggle button for full mode */}
            {viewMode === 'full' && (
              <div className="absolute top-4 right-4 pointer-events-auto z-50">
                <button
                  onClick={() => setShowPlayground(!showPlayground)}
                  className="bg-white/80 backdrop-blur-md text-gray-700 px-4 py-2.5 rounded-2xl hover:bg-white hover:text-blue-600 shadow-lg hover:shadow-xl border border-white/20 transition-all duration-300 font-medium flex items-center gap-2"
                >
                  <span>{showPlayground ? '✕' : '▶'}</span>
                  <span>{showPlayground ? 'Close Panel' : 'Open Playground'}</span>
                </button>
              </div>
            )}

            {/* Playground content */}
            {(viewMode === 'playground-only' || showPlayground) && (
              <div className={viewMode === 'playground-only'
                ? 'h-full flex flex-col overflow-hidden bg-gradient-to-br from-indigo-50/50 to-blue-50/50'
                : 'absolute top-4 bottom-4 right-4 w-[450px] bg-white/95 backdrop-blur-xl rounded-3xl z-40 shadow-2xl border border-white/20 flex flex-col overflow-hidden pointer-events-auto transition-all duration-300 transform'
              }>
                {/* Input Form */}
                <div className="flex-shrink-0 p-6 border-b border-gray-100">
                  <div className="flex justify-between items-center mb-6">
                    <SavedResultsManager
                      agentId={agentId}
                      currentResult={result}
                      resultSaved={resultSaved}
                      onSaveResult={handleSaveResult}
                      onLoadResult={handleLoadResult}
                      handleDownloadPDF={handleDownloadPDF}
                    />
                    <button
                      onClick={() => setShowInputForm(!showInputForm)}
                      className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1.5 font-semibold bg-blue-50 px-3 py-1.5 rounded-lg transition-colors"
                    >
                      {showInputForm ? 'Hide' : 'Show'} Input
                      <svg className={`w-3.5 h-3.5 transition-transform ${showInputForm ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                  </div>
                  {showInputForm && (
                    <div className='bg-white rounded-2xl p-1'>
                      {workflowConfig.trigger_type === 'text_query' ? (

                        <form onSubmit={handleExecute} className="space-y-5">

                          <div>
                            <label htmlFor="query" className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 ml-1">
                              Mission Objective / Query
                            </label>
                            <textarea
                              id="query"
                              value={query}
                              onChange={(e) => setQuery(e.target.value)}
                              rows={3}
                              className="w-full px-4 py-3 bg-gray-50 border-0 rounded-xl focus:ring-2 focus:ring-blue-500/50 text-gray-800 placeholder-gray-400 resize-none transition-all"
                              placeholder="What should the agent do?"
                              disabled={executing}
                            />
                          </div>

                          {/* Visualization Preferences (Optional) */}
                          <div>
                            <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 ml-1">
                              Visuals <span className="text-gray-300 font-normal normal-case">(Max 4)</span>
                            </label>
                            {/* Unified Multi-Select Dropdown */}
                            <div className="relative">
                              <button
                                type="button"
                                onClick={() => setChartDropdownOpen(!chartDropdownOpen)}
                                disabled={executing}
                                className="w-full text-left px-4 py-3 bg-gray-50 border-0 rounded-xl hover:bg-gray-100 transition-colors flex justify-between items-center group"
                              >
                                <span className={`text-sm ${selectedChartTypes.length === 0 ? "text-gray-400" : "text-gray-800 font-medium"}`}>
                                  {selectedChartTypes.length === 0
                                    ? "Select charts..."
                                    : `${selectedChartTypes.length} selected`}
                                </span>
                                <svg className={`w-4 h-4 text-gray-400 group-hover:text-gray-600 transition-transform ${chartDropdownOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                              </button>

                              {chartDropdownOpen && (
                                <div className="absolute z-50 w-full bottom-full mb-2 bg-white border border-gray-100 rounded-2xl shadow-2xl max-h-64 overflow-y-auto custom-scrollbar">
                                  <div className="p-2 space-y-1">
                                    {chartOptions.map((chart) => (
                                      <label key={chart.value} className="flex items-center p-2.5 hover:bg-blue-50 rounded-xl cursor-pointer transition-colors">
                                        <input
                                          type="checkbox"
                                          className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                          checked={selectedChartTypes.includes(chart.value)}
                                          onChange={(e) => {
                                            if (executing) return;
                                            if (e.target.checked) {
                                              if (selectedChartTypes.length < 4) setSelectedChartTypes([...selectedChartTypes, chart.value]);
                                            } else {
                                              setSelectedChartTypes(selectedChartTypes.filter(t => t !== chart.value));
                                            }
                                          }}
                                          disabled={executing || (!selectedChartTypes.includes(chart.value) && selectedChartTypes.length >= 4)}
                                        />
                                        <span className="ml-3 text-sm text-gray-700 flex items-center gap-2.5 font-medium">
                                          <span className="text-base">{chart.icon}</span>
                                          {chart.label}
                                        </span>
                                      </label>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                            {chartDropdownOpen && <div className="fixed inset-0 z-40 bg-transparent" onClick={() => setChartDropdownOpen(false)}></div>}
                          </div>

                          <button
                            type="submit"
                            disabled={executing || !query.trim()}
                            className={`
                            w-full py-3.5 rounded-xl font-bold text-white shadow-lg transition-all duration-300 transform
                            ${executing
                                ? 'bg-gray-400 cursor-not-allowed scale-[0.98]'
                                : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 hover:shadow-blue-500/30 hover:-translate-y-0.5 active:scale-[0.98]'
                              }
                          `}
                          >
                            {executing ? (
                              <span className="flex items-center justify-center gap-2">
                                <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                                Processing...
                              </span>
                            ) : 'Run Agent'}
                          </button>
                        </form>
                      ) : (
                        <div className="space-y-4">
                          <DynamicPlayground
                            triggerType={workflowConfig.trigger_type}
                            inputFields={workflowConfig.input_fields}
                            onExecute={handleDynamicExecute}
                            loading={executing}
                          />

                          {/* Visualization Preferences for Dynamic Playground */}
                          <div>
                            <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2 ml-1">
                              Visuals <span className="text-gray-300 font-normal normal-case">(Max 4)</span>
                            </label>
                            {/* Unified Multi-Select Dropdown (Dynamic Playground) */}
                            <div className="relative">
                              <button
                                type="button"
                                onClick={() => setChartDropdownOpen(!chartDropdownOpen)}
                                disabled={executing}
                                className="w-full text-left px-4 py-3 bg-gray-50 border-0 rounded-xl hover:bg-gray-100 transition-colors flex justify-between items-center group"
                              >
                                <span className={`text-sm ${selectedChartTypes.length === 0 ? "text-gray-400" : "text-gray-800 font-medium"}`}>
                                  {selectedChartTypes.length === 0
                                    ? "Select charts..."
                                    : `${selectedChartTypes.length} selected`}
                                </span>
                                <svg className={`w-4 h-4 text-gray-400 group-hover:text-gray-600 transition-transform ${chartDropdownOpen ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                              </button>

                              {chartDropdownOpen && (
                                <div className="absolute z-50 w-full bottom-full mb-2 bg-white border border-gray-100 rounded-2xl shadow-2xl max-h-64 overflow-y-auto custom-scrollbar">
                                  <div className="p-2 space-y-1">
                                    {chartOptions.map((chart) => (
                                      <label key={chart.value} className="flex items-center p-2.5 hover:bg-blue-50 rounded-xl cursor-pointer transition-colors">
                                        <input
                                          type="checkbox"
                                          className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                          checked={selectedChartTypes.includes(chart.value)}
                                          onChange={(e) => {
                                            if (executing) return;
                                            if (e.target.checked) {
                                              if (selectedChartTypes.length < 4) setSelectedChartTypes([...selectedChartTypes, chart.value]);
                                            } else {
                                              setSelectedChartTypes(selectedChartTypes.filter(t => t !== chart.value));
                                            }
                                          }}
                                          disabled={executing || (!selectedChartTypes.includes(chart.value) && selectedChartTypes.length >= 4)}
                                        />
                                        <span className="ml-3 text-sm text-gray-700 flex items-center gap-2.5 font-medium">
                                          <span className="text-base">{chart.icon}</span>
                                          {chart.label}
                                        </span>
                                      </label>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                            {chartDropdownOpen && <div className="fixed inset-0 z-40 bg-transparent" onClick={() => setChartDropdownOpen(false)}></div>}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                </div>

                {/* Error Display */}
                {error && (
                  <div className="mx-6 my-2 bg-red-50/50 backdrop-blur border border-red-100/50 text-red-600 px-4 py-3 rounded-xl flex-shrink-0 text-sm">
                    <strong className="block font-semibold mb-1">Error</strong>
                    {error}
                  </div>
                )}

                {/* Results Section with Scroll */}
                <div className="flex-1 overflow-y-auto bg-gray-50/50 relative">
                  {executionProgress.length > 0 && (
                    <div className="my-4 px-6">
                      <ProgressPanel
                        title={executionStatus}
                        steps={executionProgress}
                      />
                    </div>
                  )}
                  {result && (
                    <div className="space-y-4 pb-8">
                      <div className="px-6">
                        <div className="flex justify-between items-center mb-4 mt-2">
                          <h4 className="text-lg font-bold text-gray-800">Results</h4>
                        </div>
                      </div>
                      <div ref={resultRef} className="px-6 space-y-4">
                        {result.success ? (
                          <div className="space-y-6">
                            {/* Text output */}
                            {result.output && (
                              <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                                <div className="prose prose-sm max-w-none text-gray-600">
                                  <MarkdownRenderer content={result.output || ''} />
                                </div>
                              </div>
                            )}

                            {/* Data Visualization */}
                            <div className="rounded-2xl overflow-hidden shadow-sm border border-gray-100 bg-white">
                              <ResultDataVisualization data={result} />
                            </div>

                            {/* Approve & Cache Query Button */}
                            {executedQuery && !(result as unknown as Record<string, unknown>).cached_execution && workflowConfig.trigger_type !== 'text_query' && (
                              <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-5 shadow-inner">
                                <div className="mb-4">
                                  <h4 className="text-sm font-bold text-blue-800">Save Query Template</h4>
                                  <p className="text-xs text-blue-600/80 mt-1">
                                    Save this logic for future One-Click executions?
                                  </p>
                                </div>
                                <button
                                  onClick={handleApproveAndCacheQuery}
                                  disabled={cachingQuery}
                                  className="w-full bg-white text-blue-600 border border-blue-200 px-4 py-2.5 rounded-lg hover:bg-blue-50 disabled:opacity-50 font-semibold text-sm transition-colors shadow-sm"
                                >
                                  {cachingQuery ? 'Saving...' : 'Approve & Save'}
                                </button>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="bg-red-50 border border-red-100 rounded-xl p-6">
                            <div className="flex items-start gap-3 mb-3">
                              <div className="p-2 bg-red-100 rounded-lg text-red-600">
                                ✗
                              </div>
                              <div>
                                <h4 className="font-bold text-red-800">Execution Failed</h4>
                                <p className="text-sm text-red-600 mt-1">{result.error || 'An unexpected error occurred.'}</p>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )
      }

      {/* TOOL CONFIGURATION MODAL */}
      {
        showConfigModal && (
          <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 animate-in fade-in duration-200" onClick={() => setShowConfigModal(false)}>
            <div className="bg-white rounded-3xl p-8 w-full max-w-md shadow-2xl scale-100 transform transition-all" onClick={(e) => e.stopPropagation()}>
              <h3 className="text-xl font-bold text-gray-900 mb-6">
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
        )
      }
    </div >
  );
}
