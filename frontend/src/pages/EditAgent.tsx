import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { agentApi, toolApi } from '../services/api';
import type { Agent, WorkflowConfig, ToolSchema } from '../services/api';
import ProgressPanel from '../components/ProgressPanel';
import type { ProgressStep } from '../components/ProgressPanel';

export default function EditAgent() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Loading States
  const [initialLoading, setInitialLoading] = useState(true);
  const [loading, setLoading] = useState(false);

  // Form Data
  const [prompt, setPrompt] = useState('');
  const [name, setName] = useState('');
  
  // Tool Analysis State
  const [error, setError] = useState<string | null>(null);
  const [matchedTools, setMatchedTools] = useState<string[]>([]);
  
  // Tool Management State
  const [availableTools, setAvailableTools] = useState<string[]>([]);
  const [showToolSelector, setShowToolSelector] = useState(false);
  const [showToolConfigModal, setShowToolConfigModal] = useState(false);
  const [configuringTool, setConfiguringTool] = useState<string>('');
  const [toolConfigs, setToolConfigs] = useState<Record<string, Record<string, string>>>({});

  // Workflow configuration state
  const [triggerType, setTriggerType] = useState<string>('text_query');
  const [outputFormat] = useState<string>('text');  // Standardized to 'text' for markdown output
  const [inputFields, setInputFields] = useState<WorkflowConfig['input_fields']>([]);
  
  // NEW: Progress tracking for agent editing
  const [editProgress, setEditProgress] = useState<ProgressStep[]>([]);
  const [updatedAgentId, setUpdatedAgentId] = useState<string | null>(null);

  // Navigate to workflow viewer when agent is updated
  useEffect(() => {
    if (updatedAgentId) {
      console.log('✅ Agent updated, navigating to:', `/agents/${updatedAgentId}/execute`);
      navigate(`/agents/${updatedAgentId}/execute`);
    }
  }, [updatedAgentId, navigate]);

  // 1. Load Agent Data on Mount
  useEffect(() => {
    if (id) {
      loadAgent();
      loadAvailableTools();
    }
  }, [id]);
  
  const loadAvailableTools = async () => {
    try {
      const tools = await toolApi.listTools();
      setAvailableTools(tools);
    } catch (err) {
      console.error('Failed to load available tools:', err);
    }
  };

  const loadAgent = async () => {
    try {
      setInitialLoading(true);
      const agent: Agent = await agentApi.getAgent(id!);
      
      console.log('📦 Loaded agent:', agent);
      console.log('🔧 Agent tools:', agent.selected_tools);
      console.log('🛠️ Agent tool configs:', agent.tool_configs);
      
      setName(agent.name);
      setPrompt(agent.prompt);
      
      // Load existing tools
      if (agent.selected_tools && agent.selected_tools.length > 0) {
        setMatchedTools(agent.selected_tools);
        console.log('✅ Set matched tools:', agent.selected_tools);
      } else {
        console.log('⚠️ No tools found for this agent');
      }
      
      // Load existing tool configs
      if (agent.tool_configs) {
        setToolConfigs(agent.tool_configs);
        console.log('✅ Set tool configs:', agent.tool_configs);
      }

      // Load Workflow Config
      if (agent.workflow_config) {
        setTriggerType(agent.workflow_config.trigger_type || 'text_query');
        setInputFields(agent.workflow_config.input_fields || []);
      }
    } catch (err) {
      const error = err as { message?: string };
      setError(error.message || 'Failed to load agent details');
      console.error('❌ Error loading agent:', err);
    } finally {
      setInitialLoading(false);
    }
  };

  // 2. Handle Update Submission (Save current state)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      console.log('💾 Saving agent updates...');
      console.log('📋 Current tools:', matchedTools);
      console.log('🔧 Tool configs:', toolConfigs);
      
      await updateAgentDirectly(matchedTools);
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(error.response?.data?.detail || error.message || 'Failed to update agent');
      setLoading(false);
    }
  };

  // 3. Update API Call
  const updateAgentDirectly = async (selectedTools?: string[]) => {
    try {
      const toolsToUse = selectedTools || matchedTools;
      
      const workflowConfig: WorkflowConfig = {
        trigger_type: triggerType,
        input_fields: inputFields,
        output_format: outputFormat,
      };
      
      // Initialize progress steps
      const steps: ProgressStep[] = [
        { id: '1', label: 'Loading agent configuration...', status: 'pending' },
        { id: '2', label: 'Analyzing tool requirements...', status: 'pending' },
        { id: '3', label: 'AI is analyzing changes...', status: 'pending' },
        { id: '4', label: 'Optimizing execution...', status: 'pending' },
        { id: '5', label: 'Saving changes...', status: 'pending' },
      ];
      setEditProgress(steps);
      
      // Use streaming API
      const response = await fetch(`http://localhost:8000/api/agents/${id}/stream`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt,
          name: name || undefined,
          selected_tools: toolsToUse.length > 0 ? toolsToUse : [],
          workflow_config: workflowConfig,
          tool_configs: toolConfigs,
        })
      });
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      
      const readStream = () => {
        reader!.read().then(({ done, value }) => {
          if (done) return;
          
          const text = decoder.decode(value);
          const lines = text.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.substring(6));
              
              if (data.type === 'progress') {
                // Update progress step
                const stepIndex = data.step - 1;
                steps[stepIndex].status = data.status;
                steps[stepIndex].label = data.message;
                if (data.detail) {
                  steps[stepIndex].detail = data.detail;
                }
                // Handle substeps for AI operations
                if (data.substeps) {
                  steps[stepIndex].substeps = data.substeps;
                }
                setEditProgress([...steps]);
              }
              else if (data.type === 'result') {
                // Agent updated successfully
                setUpdatedAgentId(data.data.id);
                setLoading(false);
              }
              else if (data.type === 'error') {
                setError(data.message);
                setLoading(false);
                return;
              }
            }
          }
          
          readStream();
        }).catch(err => {
          setError(err.message);
          setLoading(false);
        });
      };
      
      readStream();
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(error.response?.data?.detail || error.message || 'Failed to update agent');
      setLoading(false);
    }
  };

  // 4. Dynamic Field Helpers
  const addInputField = () => {
    setInputFields([...inputFields, { name: '', type: 'text', label: '' }]);
  };

  const updateInputField = (index: number, key: string, value: string | string[]) => {
    const updated = [...inputFields];
    updated[index] = { ...updated[index], [key]: value };
    setInputFields(updated);
  };

  const removeInputField = (index: number) => {
    setInputFields(inputFields.filter((_, i) => i !== index));
  };
  
  // 6. Tool Management Functions
  const addTool = (toolName: string) => {
    if (!matchedTools.includes(toolName)) {
      setMatchedTools([...matchedTools, toolName]);
    }
    setShowToolSelector(false);
  };
  
  const removeTool = (toolName: string) => {
    setMatchedTools(matchedTools.filter(t => t !== toolName));
    // Also remove config if exists
    const newConfigs = { ...toolConfigs };
    delete newConfigs[toolName];
    setToolConfigs(newConfigs);
  };
  
  const handleConfigureTool = (toolName: string) => {
    // Exclude postgres and qdrant
    const excludedTools = ['postgres_query', 'postgres_inspect_schema', 'qdrant_connector', 'qdrant_search', 'QdrantConnector', 'PostgresConnector'];
    if (excludedTools.some(excluded => toolName.toLowerCase().includes(excluded.toLowerCase()))) {
      return; // Don't show config modal
    }
    
    setConfiguringTool(toolName);
    setShowToolConfigModal(true);
  };
  
  const saveToolConfig = (config: Record<string, string>) => {
    setToolConfigs({
      ...toolConfigs,
      [configuringTool]: config
    });
    setShowToolConfigModal(false);
    setConfiguringTool('');
  };
  
  const getToolDisplayName = (toolName: string): string => {
    // Map specific tool names to user-friendly names
    const toolNameMap: Record<string, string> = {
      'postgres_query': 'DB Reader',
      'postgres_inspect_schema': 'DB Schema Analyzer',
      'postgres_write': 'DB Writer',
      'PostgresConnector': 'DB Reader',
      'PostgresWriter': 'DB Writer',
    };
    
    // Return mapped name if exists, otherwise format normally
    if (toolNameMap[toolName]) {
      return toolNameMap[toolName];
    }
    
    // Convert tool names to readable format
    return toolName
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .trim()
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  };
  
  const isToolConfigured = (toolName: string): boolean => {
    const excludedTools = ['postgres_query', 'postgres_inspect_schema', 'qdrant_connector', 'qdrant_search', 'QdrantConnector', 'PostgresConnector'];
    if (excludedTools.some(excluded => toolName.toLowerCase().includes(excluded.toLowerCase()))) {
      return true; // Always considered configured (uses .env)
    }
    return !!toolConfigs[toolName];
  };

  if (initialLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600 flex items-center gap-2">
          <svg className="animate-spin h-5 w-5 text-gray-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          Loading agent details...
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white shadow rounded-lg p-6">
          <div className="mb-6 flex justify-between items-center">
            <h1 className="text-3xl font-bold text-gray-900">Edit Agent</h1>
            <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-sm font-medium">
               ID: {id?.slice(0, 8)}...
            </span>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                Agent Name (Optional)
              </label>
              <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                placeholder="My Custom Agent"
              />
            </div>

            <div>
              <label htmlFor="prompt" className="block text-sm font-medium text-gray-700 mb-2">
                Agent Prompt *
              </label>
              <textarea
                id="prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={8}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                placeholder="Describe what this agent should do..."
              />
              <p className="mt-2 text-sm text-gray-500">
                Describe what you want this agent to accomplish.
              </p>
            </div>
            
            {/* Tool Management Section */}
            <div className="border-t pt-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">Tools</h3>
                  <p className="text-xs text-gray-500 mt-1">{matchedTools.length} tool(s) selected</p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowToolSelector(true)}
                  className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  Add Tool
                </button>
              </div>
              
              {matchedTools.length === 0 ? (
                <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                  <h4 className="mt-2 text-sm font-medium text-gray-900">No tools selected</h4>
                  <p className="mt-1 text-sm text-gray-500">Add tools to give your agent capabilities</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {matchedTools.map(tool => (
                    <div
                      key={tool}
                      className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h4 className="text-sm font-semibold text-gray-900">
                              {getToolDisplayName(tool)}
                            </h4>
                            {isToolConfigured(tool) && (
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                                </svg>
                                Configured
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-1">{tool}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeTool(tool)}
                          className="ml-2 text-red-600 hover:text-red-800 text-sm p-1"
                          title="Remove tool"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                      
                      {/* Configure button for third-party tools only */}
                      {!['postgres_query', 'postgres_inspect_schema', 'qdrant_connector', 'qdrant_search', 'QdrantConnector', 'PostgresConnector'].some(excluded => 
                        tool.toLowerCase().includes(excluded.toLowerCase())
                      ) && (
                        <button
                          type="button"
                          onClick={() => handleConfigureTool(tool)}
                          className="mt-3 w-full inline-flex items-center justify-center gap-2 px-3 py-1.5 bg-gray-100 text-gray-700 text-xs rounded hover:bg-gray-200 transition-colors"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          {isToolConfigured(tool) ? 'Edit Configuration' : 'Configure'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Workflow Configuration Section */}
            <div className="border-t pt-6 space-y-4">
              <h3 className="text-lg font-semibold text-gray-900">Workflow Configuration</h3>
              
              {/* Trigger Type Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  How should this workflow be triggered? *
                </label>
                <div className="space-y-2">
                  {[
                    { val: 'text_query', label: 'Text Query/Questions (user inputs questions)' },
                    { val: 'date_range', label: 'Date Range Selection (start date → end date)' },
                    { val: 'month_year', label: 'Month/Year Selection (monthly reports)' },
                    { val: 'year', label: 'Year Selection (yearly reports)' },
                    { val: 'conditions', label: 'Custom Conditions (define input fields)' },
                    { val: 'scheduled', label: 'Scheduled/Automatic (no user input needed)' }
                  ].map((opt) => (
                    <label key={opt.val} className="flex items-center">
                      <input
                        type="radio"
                        value={opt.val}
                        checked={triggerType === opt.val}
                        onChange={(e) => setTriggerType(e.target.value)}
                        className="mr-2"
                      />
                      <span className="text-sm">{opt.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Dynamic Input Fields Builder (for conditions trigger type) */}
              {triggerType === 'conditions' && (
                <div className="bg-gray-50 p-4 rounded-md">
                  <div className="flex items-center justify-between mb-3">
                    <label className="block text-sm font-medium text-gray-700">
                      Define Input Fields
                    </label>
                    <button
                      type="button"
                      onClick={addInputField}
                      className="text-sm px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                      + Add Field
                    </button>
                  </div>
                  
                  {inputFields.map((field, index) => (
                    <div key={index} className="bg-white p-3 rounded border border-gray-200 mb-2">
                      <div className="grid grid-cols-2 gap-3 mb-2">
                        <input
                          type="text"
                          placeholder="Field Name (e.g., amount)"
                          value={field.name}
                          onChange={(e) => updateInputField(index, 'name', e.target.value)}
                          className="px-3 py-1 text-sm border border-gray-300 rounded"
                        />
                        <input
                          type="text"
                          placeholder="Label (e.g., Invoice Amount)"
                          value={field.label}
                          onChange={(e) => updateInputField(index, 'label', e.target.value)}
                          className="px-3 py-1 text-sm border border-gray-300 rounded"
                        />
                      </div>
                      <div className="flex gap-3">
                        <select
                          value={field.type}
                          onChange={(e) => updateInputField(index, 'type', e.target.value)}
                          className="px-3 py-1 text-sm border border-gray-300 rounded"
                        >
                          <option value="text">Text</option>
                          <option value="number">Number</option>
                          <option value="date">Date</option>
                          <option value="select">Select/Dropdown</option>
                          <option value="checkbox">Checkbox</option>
                        </select>
                        {field.type === 'select' && (
                          <input
                            type="text"
                            placeholder="Options (comma-separated)"
                            value={field.options?.join(',') || ''}
                            onChange={(e) => updateInputField(index, 'options', e.target.value.split(','))}
                            className="flex-1 px-3 py-1 text-sm border border-gray-300 rounded"
                          />
                        )}
                        <button
                          type="button"
                          onClick={() => removeInputField(index)}
                          className="text-sm px-2 py-1 text-red-600 hover:bg-red-50 rounded"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  ))}
                  
                  {inputFields.length === 0 && (
                    <p className="text-sm text-gray-500 text-center py-2">
                      No input fields defined yet.
                    </p>
                  )}
                </div>
              )}
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}

            <div className="flex gap-4">
              <button
                type="submit"
                disabled={loading || !prompt.trim()}
                className="flex-1 bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Updating...' : 'Update Agent'}
              </button>
              <button
                type="button"
                onClick={() => navigate(`/agents/${id}/execute`)}
                className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                Cancel
              </button>
            </div>
          </form>
          
          {/* Progress Panel - Show during agent editing */}
          {loading && editProgress.length > 0 && (
            <div className="mt-6 space-y-4">
              <ProgressPanel
                title="Updating Agent..."
                steps={editProgress}
              />
            </div>
          )}
        </div>
      </div>
      
      {/* Tool Selector Modal */}
      {showToolSelector && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowToolSelector(false)}>
          <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-semibold text-gray-900 mb-4">Add Tools</h3>
            <div className="space-y-2">
              {availableTools
                .filter(tool => !matchedTools.includes(tool))
                .map(tool => (
                  <button
                    key={tool}
                    type="button"
                    onClick={() => addTool(tool)}
                    className="w-full text-left px-4 py-3 border border-gray-200 rounded-lg hover:bg-blue-50 hover:border-blue-300 transition-all"
                  >
                    <div className="font-medium text-gray-900">{getToolDisplayName(tool)}</div>
                    <div className="text-xs text-gray-500 mt-1">{tool}</div>
                  </button>
                ))
              }
              {availableTools.filter(tool => !matchedTools.includes(tool)).length === 0 && (
                <p className="text-center text-gray-500 py-8">All available tools have been added</p>
              )}
            </div>
            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => setShowToolSelector(false)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Tool Configuration Modal */}
      {showToolConfigModal && (
        <ToolConfigurationModal
          toolName={configuringTool}
          initialConfig={toolConfigs[configuringTool] || {}}
          onSave={saveToolConfig}
          onCancel={() => {
            setShowToolConfigModal(false);
            setConfiguringTool('');
          }}
        />
      )}
    </div>
  );
}

// Tool Configuration Modal Component
interface ToolConfigurationModalProps {
  toolName: string;
  initialConfig: Record<string, string>;
  onSave: (config: Record<string, string>) => void;
  onCancel: () => void;
}

function ToolConfigurationModal({ toolName, initialConfig, onSave, onCancel }: ToolConfigurationModalProps) {
  const [config, setConfig] = useState<Record<string, string>>(initialConfig);
  const [schema, setSchema] = useState<ToolSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const fetchSchema = async () => {
      try {
        setLoading(true);
        const toolSchema = await toolApi.getToolSchema(toolName);
        setSchema(toolSchema);
        console.log(`📋 Schema for ${toolName}:`, toolSchema);
        
        // Initialize showPassword state for all password fields
        const passwordFields: Record<string, boolean> = {};
        toolSchema.config_fields.forEach(field => {
          if (field.type === 'password') {
            passwordFields[field.name] = false;
          }
        });
        setShowPassword(passwordFields);
      } catch (err) {
        console.error('Failed to load tool schema:', err);
        setError('Failed to load configuration fields');
      } finally {
        setLoading(false);
      }
    };
    
    fetchSchema();
  }, [toolName]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(config);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Configure {toolName.replace(/_/g, ' ').replace(/([A-Z])/g, ' $1').trim()}
        </h3>
        
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="ml-3 text-gray-600">Loading configuration...</span>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {schema && schema.config_fields.length > 0 ? (
              schema.config_fields.map(field => (
                <div key={field.name}>
                  <label htmlFor={field.name} className="block text-sm font-medium text-gray-700 mb-1">
                    {field.label} {field.required && <span className="text-red-500">*</span>}
                  </label>
                  <div className="relative">
                    <input
                      type={field.type === 'password' && !showPassword[field.name] ? 'password' : 'text'}
                      id={field.name}
                      value={config[field.name] || ''}
                      onChange={(e) => setConfig({ ...config, [field.name]: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-sm pr-10"
                      placeholder={`Enter ${field.label.toLowerCase()}`}
                      required={field.required}
                    />
                    {field.type === 'password' && (
                      <button
                        type="button"
                        onClick={() => setShowPassword({ ...showPassword, [field.name]: !showPassword[field.name] })}
                        className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                      >
                        {showPassword[field.name] ? (
                          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                          </svg>
                        ) : (
                          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        )}
                      </button>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-gray-500">Environment: {field.env_var}</p>
                </div>
              ))
            ) : (
              <div className="text-center py-4 text-gray-500 text-sm">
                No configuration fields required for this tool.
              </div>
            )}
            
            <div className="flex gap-2 pt-2">
              <button
                type="submit"
                disabled={!schema || schema.config_fields.length === 0}
                className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
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
        )}
      </div>
    </div>
  );
}