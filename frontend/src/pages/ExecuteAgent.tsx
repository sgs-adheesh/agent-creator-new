import { useParams, useNavigate } from 'react-router-dom';
import { Panel, Group, Separator } from 'react-resizable-panels';
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
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div>
            <button
              onClick={() => navigate('/', { state: { activeTab: 'my-agents' } })}
              className="text-blue-600 hover:text-blue-800 text-sm font-medium mb-2 inline-flex items-center"
            >
              ← Back to Agents
            </button>
            <h1 className="text-2xl font-bold text-gray-900">Agent Workflow</h1>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => navigate(`/agents/${id}/edit`)}
              className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              Edit Agent
            </button>
          </div>
        </div>
      </div>

      {/* Split View with Resizable Panels: Workflow + Playground & Results */}
      <Group orientation="horizontal" className="flex-1 overflow-hidden">
        {/* Left Panel: Workflow Visualization */}
        <Panel defaultSize={50} minSize={30} className="h-full">
          <WorkflowCanvas agentId={id} viewMode="workflow-only" />
        </Panel>
        <>
          {/* Resize Handle */}
          <Separator className="w-1 bg-gray-300 hover:bg-blue-500 transition-colors cursor-col-resize" />

          {/* Right Panel: Playground & Results */}
          <Panel defaultSize={50} minSize={30} className="h-full">
            <WorkflowCanvas agentId={id} viewMode="playground-only" />
          </Panel>
        </>
      </Group>
    </div>
  );
}

