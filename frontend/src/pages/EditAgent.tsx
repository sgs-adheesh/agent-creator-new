import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { agentApi, toolApi } from '../services/api';
import type { Agent, ToolSpec, WorkflowConfig } from '../services/api';
import ToolConfirmationModal from '../components/ToolConfirmationModal';

export default function EditAgent() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Loading States
  const [initialLoading, setInitialLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [generatingTools, setGeneratingTools] = useState(false);

  // Form Data
  const [prompt, setPrompt] = useState('');
  const [name, setName] = useState('');
  
  // Tool Analysis State
  const [error, setError] = useState<string | null>(null);
  const [showToolModal, setShowToolModal] = useState(false);
  const [proposedTools, setProposedTools] = useState<ToolSpec[]>([]);
  const [toolReasoning, setToolReasoning] = useState('');
  const [dependencyWarnings, setDependencyWarnings] = useState<string[]>([]);
  const [matchedTools, setMatchedTools] = useState<string[]>([]);

  // Workflow configuration state
  const [triggerType, setTriggerType] = useState<string>('text_query');
  const [outputFormat, setOutputFormat] = useState<string>('text');
  const [inputFields, setInputFields] = useState<WorkflowConfig['input_fields']>([]);

  // 1. Load Agent Data on Mount
  useEffect(() => {
    if (id) {
      loadAgent();
    }
  }, [id]);

  const loadAgent = async () => {
    try {
      setInitialLoading(true);
      const agent: Agent = await agentApi.getAgent(id!);
      
      setName(agent.name);
      setPrompt(agent.prompt);
      
      // Load existing tools
      setMatchedTools(agent.selected_tools || []);

      // Load Workflow Config
      if (agent.workflow_config) {
        setTriggerType(agent.workflow_config.trigger_type || 'text_query');
        setOutputFormat(agent.workflow_config.output_format || 'text');
        setInputFields(agent.workflow_config.input_fields || []);
      }
    } catch (err) {
      const error = err as { message?: string };
      setError(error.message || 'Failed to load agent details');
    } finally {
      setInitialLoading(false);
    }
  };

  // 2. Handle Update Submission (Analyze Prompt First)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Step 1: Analyze prompt to see if requirements changed
      const analysis = await toolApi.analyzePrompt(prompt);

      if (!analysis.success) {
        throw new Error(analysis.error || 'Tool analysis failed');
      }

      // Merge currently existing tools (matched) with any potentially new ones
      const toolsForAgent = [...(analysis.matched_tools || [])];
      console.log('🎯 Matched existing tools:', analysis.matched_tools);
      
      // Step 2: If NEW tools are needed, show modal
      if (analysis.requires_user_confirmation && analysis.new_tools_needed && analysis.new_tools_needed.length > 0) {
        const newToolNames = analysis.new_tools_needed.map(t => t.name);
        
        // Update matched tools to include the new ones (pending creation)
        setMatchedTools([...toolsForAgent, ...newToolNames]);
        setProposedTools(analysis.new_tools_needed);
        setToolReasoning(analysis.reasoning || 'Updates to the prompt require new tools.');
        setShowToolModal(true);
        setLoading(false);
        return;
      }

      // Step 3: No new tools needed, update directly
      setMatchedTools(toolsForAgent);
      await updateAgentDirectly(toolsForAgent);
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

      await agentApi.updateAgent(id!, {
        prompt,
        name: name || undefined,
        selected_tools: toolsToUse.length > 0 ? toolsToUse : [],
        workflow_config: workflowConfig,
      });

      navigate(`/agents/${id}/execute`);
    } catch (err) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Failed to update agent');
      setLoading(false);
    }
  };

  // 4. Handle New Tool Generation
  const handleToolConfirmation = async (approvedTools: ToolSpec[]) => {
    setShowToolModal(false);
    setGeneratingTools(true);
    setLoading(true);
    setError(null);
    setDependencyWarnings([]);

    try {
      const allWarnings: string[] = [];
      
      for (const tool of approvedTools) {
        const result = await toolApi.generateTool(tool);
        if (!result.success) {
          throw new Error(`Failed to generate tool ${tool.display_name}: ${result.error}`);
        }
        
        if (result.warnings && result.warnings.length > 0) {
           const failedWarnings = result.warnings.filter((warning: string) => {
            return !result.installation_log?.some((log) => 
              log.success && warning.includes(log.package)
            );
          });
          allWarnings.push(...failedWarnings);
        }
      }
      
      if (allWarnings.length > 0) {
        setDependencyWarnings(allWarnings);
        setGeneratingTools(false);
        setLoading(false);
        return;
      }

      await updateAgentDirectly();
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
    await updateAgentDirectly();
  };

  // 5. Dynamic Field Helpers
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
                Modifying the prompt may trigger a re-analysis of required tools.
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

              {/* Output Format Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Output Format *
                </label>
                <div className="space-y-2">
                  {[
                    { val: 'text', label: 'Text/Markdown (formatted text response)' },
                    { val: 'csv', label: 'CSV Download (downloadable spreadsheet)' },
                    { val: 'json', label: 'JSON (structured data)' },
                    { val: 'table', label: 'Table/Grid (interactive data table)' }
                  ].map((opt) => (
                    <label key={opt.val} className="flex items-center">
                      <input
                        type="radio"
                        value={opt.val}
                        checked={outputFormat === opt.val}
                        onChange={(e) => setOutputFormat(e.target.value)}
                        className="mr-2"
                      />
                      <span className="text-sm">{opt.label}</span>
                    </label>
                  ))}
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
                  <div className="flex-shrink-0 text-yellow-600 text-xl">⚠️</div>
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
                    : 'Analyzing Updates...'
                  : 'Update Agent'}
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