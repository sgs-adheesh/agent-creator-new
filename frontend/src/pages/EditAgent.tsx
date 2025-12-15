import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { agentApi, type Agent } from '../services/api';

type ExecutionTrigger = 'user_text_input' | 'date_range' | 'month_year' | 'year' | 'custom_fields';
type OutputFormat = 'text' | 'csv' | 'json' | 'markdown' | 'table';

export default function EditAgent() {
  const { id } = useParams<{ id: string }>();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [executionTrigger, setExecutionTrigger] = useState<ExecutionTrigger>('user_text_input');
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('text');
  const [loading, setLoading] = useState(false);
  const [loadingAgent, setLoadingAgent] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (id) {
      loadAgent();
    }
  }, [id]);

  const loadAgent = async () => {
    try {
      const agent: Agent = await agentApi.getAgent(id!);
      setName(agent.name);
      
      // Parse configuration from prompt if exists
      const promptLines = agent.prompt.split('\n');
      const configIndex = promptLines.findIndex(line => line.includes('[Configuration]'));
      
      if (configIndex !== -1) {
        // Extract description (before configuration)
        const desc = promptLines.slice(0, configIndex).join('\n').trim();
        setDescription(desc);
        
        // Extract configuration
        const configLines = promptLines.slice(configIndex);
        configLines.forEach(line => {
          if (line.includes('Execution Trigger:')) {
            const trigger = line.split(':')[1]?.trim().toLowerCase().replace(/ /g, '_');
            if (['user_text_input', 'date_range', 'month_year', 'year', 'custom_fields'].includes(trigger)) {
              setExecutionTrigger(trigger as ExecutionTrigger);
            }
          }
          if (line.includes('Output Format:')) {
            const format = line.split(':')[1]?.trim().toLowerCase();
            if (['text', 'csv', 'json', 'markdown', 'table'].includes(format)) {
              setOutputFormat(format as OutputFormat);
            }
          }
        });
      } else {
        // No configuration found, use full prompt as description
        setDescription(agent.prompt);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load agent';
      setError(message);
    } finally {
      setLoadingAgent(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Create prompt with configuration embedded
      const prompt = `${description}

[Configuration]
- Execution Trigger: ${executionTrigger}
- Output Format: ${outputFormat}`;

      await agentApi.updateAgent(id!, {
        prompt,
        name: name,
      });
      navigate(`/agents/${id}/execute`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update agent';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  if (loadingAgent) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading agent...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white shadow rounded-lg p-8">
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-gray-900">Edit Agent</h1>
            <p className="text-gray-600 mt-2">Update your AI agent configuration</p>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Agent Name */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                Agent Name *
              </label>
              <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                placeholder="e.g., Customer Support Agent"
              />
            </div>

            {/* Agent Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
                Agent Description *
              </label>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                placeholder="Describe what this agent should do..."
              />
            </div>

            {/* How the agent should trigger? */}
            <div>
              <label htmlFor="executionTrigger" className="block text-sm font-medium text-gray-700 mb-2">
                How the agent should trigger?
              </label>
              <select
                id="executionTrigger"
                value={executionTrigger}
                onChange={(e) => setExecutionTrigger(e.target.value as ExecutionTrigger)}
                className="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="user_text_input">User Text Input</option>
                <option value="date_range">Date Range</option>
                <option value="month_year">Month & Year</option>
                <option value="year">Year</option>
                <option value="custom_fields">Custom Fields</option>
              </select>
            </div>

            {/* How the agent should give result? */}
            <div>
              <label htmlFor="outputFormat" className="block text-sm font-medium text-gray-700 mb-2">
                How the agent should give result?
              </label>
              <select
                id="outputFormat"
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value as OutputFormat)}
                className="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="text">Text</option>
                <option value="csv">CSV</option>
                <option value="json">JSON</option>
                <option value="markdown">Markdown</option>
                <option value="table">Table</option>
              </select>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
                {error}
              </div>
            )}

            <div className="flex gap-4 pt-4">
              <button
                type="submit"
                disabled={loading || !name.trim() || !description.trim()}
                className="flex-1 bg-blue-600 text-white px-6 py-3 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
              >
                {loading ? 'Updating...' : 'Update Agent'}
              </button>
              <button
                type="button"
                onClick={() => navigate(`/agents/${id}/execute`)}
                className="px-6 py-3 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 font-medium"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
