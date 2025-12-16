import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { agentApi, toolApi } from '../services/api';
import type { ToolSpec, WorkflowConfig } from '../services/api';
import ToolConfirmationModal from '../components/ToolConfirmationModal';

export default function CreateAgent() {
  const [prompt, setPrompt] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showToolModal, setShowToolModal] = useState(false);
  const [proposedTools, setProposedTools] = useState<ToolSpec[]>([]);
  const [toolReasoning, setToolReasoning] = useState('');
  const [generatingTools, setGeneratingTools] = useState(false);
  const [dependencyWarnings, setDependencyWarnings] = useState<string[]>([]);
  const [matchedTools, setMatchedTools] = useState<string[]>([]);  // Store matched tools from analysis
  
  // Workflow configuration state
  const [triggerType, setTriggerType] = useState<string>('text_query');
  const [outputFormat, setOutputFormat] = useState<string>('text');
  const [inputFields, setInputFields] = useState<WorkflowConfig['input_fields']>([]);
  
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Step 1: Analyze prompt for required tools
      const analysis = await toolApi.analyzePrompt(prompt);

      if (!analysis.success) {
        throw new Error(analysis.error || 'Tool analysis failed');
      }

      // Store matched tools for agent creation
      const toolsForAgent = [...(analysis.matched_tools || [])];
      console.log('🎯 Matched existing tools:', analysis.matched_tools);
      console.log('🆕 New tools needed:', analysis.new_tools_needed);

      // Step 2: If new tools needed, show confirmation modal
      if (analysis.requires_user_confirmation && analysis.new_tools_needed && analysis.new_tools_needed.length > 0) {
        // Add new tool names to the list
        const newToolNames = analysis.new_tools_needed.map(t => t.name);
        setMatchedTools([...toolsForAgent, ...newToolNames]);
        setProposedTools(analysis.new_tools_needed);
        setToolReasoning(analysis.reasoning || 'New tools are required for this agent');
        setShowToolModal(true);
        setLoading(false);
        return;
      }

      // Step 3: No new tools needed, create agent with matched tools only
      setMatchedTools(toolsForAgent);
      await createAgentDirectly(toolsForAgent);
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(error.response?.data?.detail || error.message || 'Failed to create agent');
      setLoading(false);
    }
  };

  const createAgentDirectly = async (selectedTools?: string[]) => {
    try {
      const toolsToUse = selectedTools || matchedTools;
      console.log('🚀 Creating agent with tools:', toolsToUse);
      
      // Build workflow configuration
      const workflowConfig: WorkflowConfig = {
        trigger_type: triggerType,
        input_fields: inputFields,
        output_format: outputFormat,
      };
      
      // If no tools were matched or selected, let the AI decide during execution
      // rather than assigning all tools
      const agent = await agentApi.createAgent({
        prompt,
        name: name || undefined,
        selected_tools: toolsToUse.length > 0 ? toolsToUse : [],  // Send empty array instead of undefined
        workflow_config: workflowConfig,
      });
      navigate(`/agents/${agent.id}/execute`);
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Failed to create agent');
      setLoading(false);
    }
  };

  const handleToolConfirmation = async (approvedTools: ToolSpec[]) => {
    setShowToolModal(false);
    setGeneratingTools(true);
    setLoading(true);
    setError(null);
    setDependencyWarnings([]);

    try {
      const allWarnings: string[] = [];
      let totalInstalled = 0;
      
      // Generate each approved tool sequentially
      for (const tool of approvedTools) {
        const result = await toolApi.generateTool(tool);
        if (!result.success) {
          throw new Error(`Failed to generate tool ${tool.display_name}: ${result.error}`);
        }
        
        // Count installed dependencies
        if (result.dependencies_installed) {
          totalInstalled += result.installation_log?.length || 0;
        }
        
        // Collect dependency warnings (only for failed installations)
        if (result.warnings && result.warnings.length > 0) {
          // Filter out warnings for successfully installed packages
          const failedWarnings = result.warnings.filter((warning: string) => {
            return !result.installation_log?.some((log) => 
              log.success && warning.includes(log.package)
            );
          });
          allWarnings.push(...failedWarnings);
        }
      }
      
      // Show success message if dependencies were installed
      if (totalInstalled > 0) {
        console.log(`✅ Successfully installed ${totalInstalled} dependencies`);
      }
      
      // Show dependency warnings only if there are unresolved issues
      if (allWarnings.length > 0) {
        setDependencyWarnings(allWarnings);
        setGeneratingTools(false);
        setLoading(false);
        return;
      }

      // All tools generated successfully, now create the agent
      await createAgentDirectly();
    } catch (err) {
      const error = err as { message?: string };
      setError(error.message || 'Failed to generate tools');
    } finally {
      setGeneratingTools(false);
      setLoading(false);
    }
  };

  const handleToolCancel = () => {
    setShowToolModal(false);
    setLoading(false);
    setProposedTools([]);
    setToolReasoning('');
  };
  
  const handleDismissWarnings = async () => {
    setDependencyWarnings([]);
    // Proceed to create agent anyway
    await createAgentDirectly();
  };

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

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="bg-white shadow rounded-lg p-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">Create New Agent</h1>
          
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
                placeholder="Describe what this agent should do. For example: 'Help users query the database to find customer information'"
              />
              <p className="mt-2 text-sm text-gray-500">
                Describe the agent's purpose and capabilities. The agent will have access to Postgres queries and QBO tools.
              </p>
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
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="text_query"
                      checked={triggerType === 'text_query'}
                      onChange={(e) => setTriggerType(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">Text Query/Questions (user inputs questions)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="date_range"
                      checked={triggerType === 'date_range'}
                      onChange={(e) => setTriggerType(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">Date Range Selection (start date → end date)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="month_year"
                      checked={triggerType === 'month_year'}
                      onChange={(e) => setTriggerType(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">Month/Year Selection (monthly reports)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="year"
                      checked={triggerType === 'year'}
                      onChange={(e) => setTriggerType(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">Year Selection (yearly reports)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="conditions"
                      checked={triggerType === 'conditions'}
                      onChange={(e) => setTriggerType(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">Custom Conditions (define input fields)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="scheduled"
                      checked={triggerType === 'scheduled'}
                      onChange={(e) => setTriggerType(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">Scheduled/Automatic (no user input needed)</span>
                  </label>
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
                      No input fields defined yet. Click "Add Field" to create custom input fields.
                    </p>
                  )}
                </div>
              )}

              {/* Output Format Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Output Format *
                </label>
                <div className="space-y-2">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="text"
                      checked={outputFormat === 'text'}
                      onChange={(e) => setOutputFormat(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">Text/Markdown (formatted text response)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="csv"
                      checked={outputFormat === 'csv'}
                      onChange={(e) => setOutputFormat(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">CSV Download (downloadable spreadsheet)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="json"
                      checked={outputFormat === 'json'}
                      onChange={(e) => setOutputFormat(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">JSON (structured data)</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      value="table"
                      checked={outputFormat === 'table'}
                      onChange={(e) => setOutputFormat(e.target.value)}
                      className="mr-2"
                    />
                    <span className="text-sm">Table/Grid (interactive data table)</span>
                  </label>
                </div>
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}

            {dependencyWarnings.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 text-yellow-600 text-xl">
                    ⚠️
                  </div>
                  <div className="flex-1">
                    <h3 className="text-sm font-semibold text-yellow-800 mb-2">
                      Missing Dependencies Detected
                    </h3>
                    <ul className="list-disc list-inside space-y-1 text-sm text-yellow-700 mb-3">
                      {dependencyWarnings.map((warning, idx) => (
                        <li key={idx}>{warning}</li>
                      ))}
                    </ul>
                    <div className="flex gap-3">
                      <button
                        onClick={handleDismissWarnings}
                        className="text-sm px-3 py-1 bg-yellow-600 text-white rounded hover:bg-yellow-700"
                      >
                        Continue Anyway
                      </button>
                      <button
                        onClick={() => setDependencyWarnings([])}
                        className="text-sm px-3 py-1 border border-yellow-300 rounded hover:bg-yellow-100"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-4">
              <button
                type="submit"
                disabled={loading || !prompt.trim()}
                className="flex-1 bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading
                  ? generatingTools
                    ? 'Generating Tools...'
                    : 'Analyzing...'
                  : 'Create Agent'}
              </button>
              <button
                type="button"
                onClick={() => navigate('/')}
                className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Tool Confirmation Modal */}
      {showToolModal && (
        <ToolConfirmationModal
          tools={proposedTools}
          reasoning={toolReasoning}
          onConfirm={handleToolConfirmation}
          onCancel={handleToolCancel}
        />
      )}
    </div>
  );
}

