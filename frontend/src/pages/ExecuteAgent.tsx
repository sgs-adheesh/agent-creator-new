import { useParams, useNavigate } from 'react-router-dom';
import WorkflowCanvas from '../components/WorkflowCanvas';

export default function ExecuteAgent() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  if (!id) {
    return (
      <div className="min-h-screen bg-red-50 flex items-center justify-center">
        <div className="text-red-700">No agent ID provided</div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div>
            <button
              onClick={() => navigate('/')}
              className="text-blue-600 hover:text-blue-800 text-sm font-medium mb-2 inline-flex items-center"
            >
              ← Back to Agents
            </button>
            <h1 className="text-2xl font-bold text-gray-900">Agent Workflow</h1>
          </div>
          <button
            onClick={() => navigate(`/agents/${id}/edit`)}
            className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
          >
            Edit Agent
          </button>
        </div>
      </div>

      {/* Split View: 50% Workflow + 50% Playground & Results */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Half: Workflow Visualization */}
        <div className="w-1/2 border-r border-gray-200">
          <WorkflowCanvas agentId={id} viewMode="workflow-only" />
        </div>
        
        {/* Right Half: Playground & Results */}
        <div className="w-1/2">
          <WorkflowCanvas agentId={id} viewMode="playground-only" />
        </div>
      </div>
    </div>
  );
}

