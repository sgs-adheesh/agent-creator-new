import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { agentApi, type Agent } from '../services/api';
import { IconRenderer } from '../components/IconRenderer';
import { Tooltip } from '../components/Tooltip';

interface AgentTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  use_cases: string[];
}

export default function AgentList() {
  const location = useLocation();
  const [activeTab, setActiveTab] = useState<'templates' | 'my-agents'>((location.state as any)?.activeTab || 'templates');
  const [agents, setAgents] = useState<Agent[]>([]);
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [creatingTemplate, setCreatingTemplate] = useState<string | null>(null);
  const [showVizModal, setShowVizModal] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [visualizationPreferences, setVisualizationPreferences] = useState<string>('');
  const [selectedChartTypes, setSelectedChartTypes] = useState<string[]>([]);

  // Search & Filter State
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'newest' | 'oldest' | 'name_asc' | 'name_desc'>('newest');
  const [filterTrigger, setFilterTrigger] = useState<string>('all');

  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, [activeTab]);

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'my-agents') {
        const data = await agentApi.listAgents();
        setAgents(data);
      } else {
        const response = await fetch('http://localhost:8000/api/templates');
        const data = await response.json();
        setTemplates(data.templates || []);
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this agent?')) {
      return;
    }

    try {
      await agentApi.deleteAgent(id);
      setAgents(agents.filter(agent => agent.id !== id));
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      alert(error.response?.data?.detail || 'Failed to delete agent');
    }
  };

  const handleUseTemplate = (templateId: string) => {
    // Show modal to ask for visualization preferences
    setSelectedTemplateId(templateId);
    setVisualizationPreferences('');
    setSelectedChartTypes([]);
    setShowVizModal(true);
  };

  const handleConfirmTemplate = async () => {
    if (!selectedTemplateId) return;

    setCreatingTemplate(selectedTemplateId);
    setShowVizModal(false);

    // Convert selected chart types to string format
    const vizPrefsString = selectedChartTypes.length > 0
      ? selectedChartTypes.join(', ')
      : (visualizationPreferences || undefined);

    try {
      const response = await fetch(`http://localhost:8000/api/templates/${selectedTemplateId}/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visualization_preferences: vizPrefsString
        })
      });

      if (!response.ok) throw new Error('Failed to create agent from template');

      const agent = await response.json();
      navigate(`/agents/${agent.id}/execute`);
    } catch {
      alert('Failed to create agent from template');
      setCreatingTemplate(null);
    } finally {
      setSelectedTemplateId(null);
      setVisualizationPreferences('');
    }
  };

  const handleSkipVizModal = async () => {
    // Use default (no preferences)
    setSelectedChartTypes([]);
    setVisualizationPreferences('');
    await handleConfirmTemplate();
  };

  const categories = ['All', ...Array.from(new Set(templates.map(t => t.category)))];
  const filteredTemplates = selectedCategory === 'All'
    ? templates
    : templates.filter(t => t.category === selectedCategory);

  const filteredAgents = agents
    .filter(agent => {
      const lowerSearch = searchTerm.toLowerCase();
      const matchesSearch = (agent.name?.toLowerCase() || '').includes(lowerSearch) ||
        (agent.prompt?.toLowerCase() || '').includes(lowerSearch);

      if (filterTrigger === 'all') return matchesSearch;
      return matchesSearch && agent.workflow_config?.trigger_type === filterTrigger;
    })
    .sort((a, b) => {
      if (sortBy === 'newest') return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      if (sortBy === 'oldest') return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      if (sortBy === 'name_asc') return (a.name || '').localeCompare(b.name || '');
      if (sortBy === 'name_desc') return (b.name || '').localeCompare(a.name || '');
      return 0;
    });

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">AI Agents</h1>
          <p className="text-gray-600">Choose from templates or create your own custom agents</p>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-8">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('templates')}
              className={`${activeTab === 'templates'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors`}
            >
              <div className="flex items-center gap-2">
                <IconRenderer iconName="LayoutTemplate" size={16} />
                Agent Templates
              </div>
            </button>
            <button
              onClick={() => setActiveTab('my-agents')}
              className={`${activeTab === 'my-agents'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors`}
            >
              <div className="flex items-center gap-2">
                <IconRenderer iconName="Bot" size={16} />
                My Agents ({agents.length})
              </div>
            </button>
          </nav>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {/* Templates Tab */}
        {activeTab === 'templates' && (
          <div>
            {/* Category Filter */}
            <div className="mb-6 flex gap-2 flex-wrap">
              {categories.map(category => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`${selectedCategory === category
                    ? 'bg-blue-600 text-white'
                    : 'bg-white text-gray-700 hover:bg-gray-50'
                    } px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-gray-200`}
                >
                  {category}
                </button>
              ))}
            </div>

            {/* Templates Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredTemplates.map((template) => (
                <div
                  key={template.id}
                  className="bg-white shadow rounded-lg p-6 hover:shadow-lg transition-shadow border border-gray-200"
                >
                  <div className="flex items-start mb-4">
                    <div className="text-blue-600 mr-3">
                      <IconRenderer iconName={template.icon} size={32} />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-gray-900 mb-1">
                        {template.name}
                      </h3>
                      <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                        {template.category}
                      </span>
                    </div>
                  </div>

                  <p className="text-gray-600 text-sm mb-4 line-clamp-3">
                    {template.description}
                  </p>

                  <div className="mb-4">
                    <p className="text-xs font-medium text-gray-700 mb-2">Use Cases:</p>
                    <ul className="text-xs text-gray-600 space-y-1">
                      {template.use_cases.slice(0, 3).map((useCase, idx) => (
                        <li key={idx} className="flex items-start">
                          <span className="text-green-500 mr-1">✓</span>
                          {useCase}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <button
                    onClick={() => handleUseTemplate(template.id)}
                    disabled={creatingTemplate !== null}
                    className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {creatingTemplate === template.id ? (
                      <>
                        <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Creating...
                      </>
                    ) : (
                      'Use Template'
                    )}
                  </button>
                </div>
              ))}
            </div>

            {filteredTemplates.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                No templates found in this category
              </div>
            )}
          </div>
        )}

        {/* My Agents Tab */}
        {activeTab === 'my-agents' && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Your Custom Agents</h2>
              <button
                onClick={() => navigate('/agents/create')}
                className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                ✨ Create Custom Agent
              </button>
            </div>

            {/* Search, Sort, Filter Controls */}
            <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 mb-6 flex flex-col md:flex-row gap-4 items-center justify-between">
              {/* Search */}
              <div className="relative flex-1 w-full">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                  <IconRenderer iconName="Search" size={18} />
                </div>
                <input
                  type="text"
                  placeholder="Search agents..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 block w-full rounded-lg border-gray-300 bg-gray-50 focus:bg-white focus:ring-blue-500 focus:border-blue-500 sm:text-sm py-2 transition-colors border"
                />
              </div>

              <div className="flex gap-3 w-full md:w-auto">
                {/* Filter Trigger */}
                {/* Filter Trigger */}
                <select
                  value={filterTrigger}
                  onChange={(e) => setFilterTrigger(e.target.value)}
                  className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 shadow-sm"
                >
                  <option value="all">All Types</option>
                  <option value="text_query">Chat / Manual</option>
                  <option value="scheduled">Scheduled</option>
                  <option value="date_range">Date Range</option>
                  <option value="conditions">Conditional</option>
                  <option value="month_year">Monthly Report</option>
                </select>

                {/* Sort */}
                {/* Sort */}
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 shadow-sm"
                >
                  <option value="newest">Newest First</option>
                  <option value="oldest">Oldest First</option>
                  <option value="name_asc">Name (A-Z)</option>
                  <option value="name_desc">Name (Z-A)</option>
                </select>
              </div>
            </div>

            {filteredAgents.length === 0 ? (
              <div className="bg-white shadow rounded-lg p-12 text-center border border-gray-200">
                <div className="mx-auto h-12 w-12 text-gray-400 mb-4">
                  <IconRenderer iconName="Search" size={48} />
                </div>
                <p className="text-gray-500 mb-4">
                  {searchTerm || filterTrigger !== 'all' ? 'No agents match your search.' : 'No custom agents created yet.'}
                </p>
                {searchTerm || filterTrigger !== 'all' ? (
                  <button
                    onClick={() => { setSearchTerm(''); setFilterTrigger('all'); }}
                    className="text-blue-600 hover:text-blue-800 font-medium"
                  >
                    Clear Filters
                  </button>
                ) : null}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredAgents.map((agent) => (
                  <Tooltip
                    key={agent.id}
                    content={
                      <div className="text-left space-y-2">
                        <p className="font-bold text-white border-b border-gray-700 pb-1">{agent.name}</p>
                        <p className="text-xs text-gray-300 leading-relaxed line-clamp-6">{agent.prompt}</p>
                      </div>
                    }
                    className="w-full"
                    delay={500}
                  >
                    <div
                      onClick={() => navigate(`/agents/${agent.id}/execute`)}
                      className="bg-white shadow rounded-lg p-6 cursor-pointer hover:shadow-lg transition-shadow border border-gray-200 h-full"
                    >
                      <div className="flex justify-between items-start mb-4">
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <div className="text-violet-600 bg-violet-50 p-2 rounded-lg flex-shrink-0">
                            <IconRenderer iconName={agent.icon || 'Bot'} size={24} />
                          </div>
                          <h2 className="text-xl font-semibold text-gray-900 truncate pr-2" title={agent.name}>{agent.name}</h2>
                        </div>
                        <button
                          onClick={(e) => handleDelete(agent.id, e)}
                          className="text-red-600 hover:text-red-800 text-sm flex-shrink-0 px-2 py-1 hover:bg-red-50 rounded transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                      <p className="text-gray-600 text-sm mb-4 line-clamp-3">{agent.prompt}</p>
                      <div className="text-xs text-gray-400">
                        Created: {new Date(agent.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </Tooltip>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Visualization Preferences Modal */}
      {showVizModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-2xl">
            <h3 className="text-xl font-bold text-gray-900 mb-4">
              Configure Visualization Preferences
            </h3>

            <p className="text-sm text-gray-600 mb-4">
              How would you like the data to be visualized? You can specify chart types, grouping, or leave empty for auto-generated visualizations.
            </p>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Visualization Types <span className="text-gray-400 text-xs">(Optional, max 4)</span>
              </label>
              <div className="grid grid-cols-2 gap-3 p-3 border border-gray-300 rounded-lg bg-gray-50 max-h-64 overflow-y-auto">
                {[
                  { value: 'pie', label: 'Pie Chart', icon: 'PieChart' },
                  { value: 'bar', label: 'Bar Chart', icon: 'BarChart' },
                  { value: 'line', label: 'Line Chart', icon: 'LineChart' },
                  { value: 'area', label: 'Area Chart', icon: 'TrendingUp' },
                  { value: 'scatter', label: 'Scatter Plot', icon: 'Search' },
                  { value: 'radar', label: 'Radar Chart', icon: 'Radar' },
                  { value: 'radialbar', label: 'Radial Bar', icon: 'CircleDot' },
                  { value: 'treemap', label: 'Treemap', icon: 'LayoutGrid' }
                ].map((chart) => (
                  <label
                    key={chart.value}
                    className={`flex items-center space-x-2 p-2 rounded-lg cursor-pointer transition-all ${selectedChartTypes.includes(chart.value)
                      ? 'bg-blue-100 border-2 border-blue-500'
                      : 'bg-white border-2 border-transparent hover:bg-gray-100'
                      }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedChartTypes.includes(chart.value)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          if (selectedChartTypes.length < 4) {
                            setSelectedChartTypes([...selectedChartTypes, chart.value]);
                          }
                        } else {
                          setSelectedChartTypes(selectedChartTypes.filter(t => t !== chart.value));
                        }
                      }}
                      disabled={!selectedChartTypes.includes(chart.value) && selectedChartTypes.length >= 4}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <span className="text-sm font-medium text-gray-700 flex items-center">
                      <span className="mr-1">
                        <IconRenderer iconName={chart.icon} size={16} />
                      </span>
                      {chart.label}
                    </span>
                  </label>
                ))}
              </div>
              {selectedChartTypes.length > 0 && (
                <p className="mt-2 text-xs text-blue-600">
                  Selected: {selectedChartTypes.join(', ')} ({selectedChartTypes.length}/4)
                </p>
              )}
              <p className="mt-2 text-xs text-gray-500">
                Select up to 4 chart types. Leave empty for auto-generated visualizations.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleConfirmTemplate}
                className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium"
              >
                Continue with Preferences
              </button>
              <button
                onClick={handleSkipVizModal}
                className="flex-1 bg-gray-200 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-400 font-medium"
              >
                Use Default
              </button>
              <button
                onClick={() => {
                  setShowVizModal(false);
                  setSelectedTemplateId(null);
                  setVisualizationPreferences('');
                  setSelectedChartTypes([]);
                }}
                className="px-4 py-2 text-gray-600 hover:text-gray-800 focus:outline-none"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )
      }
    </div >
  );
}

