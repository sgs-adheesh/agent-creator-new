import { useState } from 'react';

interface ToolSpec {
  name: string;
  display_name: string;
  description: string;
  api_type: string;
  service: string;
}

interface ToolConfirmationModalProps {
  tools: ToolSpec[];
  reasoning: string;
  onConfirm: (approvedTools: ToolSpec[]) => void;
  onCancel: () => void;
}

export default function ToolConfirmationModal({
  tools,
  reasoning,
  onConfirm,
  onCancel,
}: ToolConfirmationModalProps) {
  const [toolStates, setToolStates] = useState<Map<string, {
    approved: boolean;
    editing: boolean;
    spec: ToolSpec;
  }>>(
    new Map(
      tools.map((tool) => [
        tool.name,
        { approved: true, editing: false, spec: tool },
      ])
    )
  );

  const handleToggleApproval = (toolName: string) => {
    setToolStates((prev) => {
      const newMap = new Map(prev);
      const state = newMap.get(toolName);
      if (state) {
        newMap.set(toolName, { ...state, approved: !state.approved });
      }
      return newMap;
    });
  };

  const handleEdit = (toolName: string) => {
    setToolStates((prev) => {
      const newMap = new Map(prev);
      const state = newMap.get(toolName);
      if (state) {
        newMap.set(toolName, { ...state, editing: true });
      }
      return newMap;
    });
  };

  const handleSaveEdit = (toolName: string, updatedSpec: Partial<ToolSpec>) => {
    setToolStates((prev) => {
      const newMap = new Map(prev);
      const state = newMap.get(toolName);
      if (state) {
        newMap.set(toolName, {
          ...state,
          spec: { ...state.spec, ...updatedSpec },
          editing: false,
        });
      }
      return newMap;
    });
  };

  const handleCancelEdit = (toolName: string) => {
    setToolStates((prev) => {
      const newMap = new Map(prev);
      const state = newMap.get(toolName);
      if (state) {
        newMap.set(toolName, { ...state, editing: false });
      }
      return newMap;
    });
  };

  const handleConfirm = () => {
    const approvedTools = Array.from(toolStates.values())
      .filter((state) => state.approved)
      .map((state) => state.spec);
    onConfirm(approvedTools);
  };

  const approvedCount = Array.from(toolStates.values()).filter(
    (state) => state.approved
  ).length;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-2xl font-bold text-gray-900">
            New Tools Required
          </h2>
          <p className="mt-2 text-sm text-gray-600">{reasoning}</p>
        </div>

        {/* Tool List */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <div className="space-y-4">
            {Array.from(toolStates.entries()).map(([toolName, state]) => (
              <div
                key={toolName}
                className={`border rounded-lg p-4 ${
                  state.approved
                    ? 'border-blue-300 bg-blue-50'
                    : 'border-gray-200 bg-gray-50'
                }`}
              >
                <div className="flex items-start gap-3">
                  {/* Checkbox */}
                  <input
                    type="checkbox"
                    checked={state.approved}
                    onChange={() => handleToggleApproval(toolName)}
                    className="mt-1 h-5 w-5 text-blue-600 rounded focus:ring-blue-500"
                  />

                  {/* Tool Details */}
                  <div className="flex-1">
                    {state.editing ? (
                      /* Edit Mode */
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Display Name
                          </label>
                          <input
                            type="text"
                            value={state.spec.display_name}
                            onChange={(e) =>
                              handleSaveEdit(toolName, {
                                display_name: e.target.value,
                              })
                            }
                            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Description
                          </label>
                          <textarea
                            value={state.spec.description}
                            onChange={(e) =>
                              handleSaveEdit(toolName, {
                                description: e.target.value,
                              })
                            }
                            rows={3}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
                          />
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleCancelEdit(toolName)}
                            className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
                          >
                            Done
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* View Mode */
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <h3 className="font-semibold text-gray-900">
                            {state.spec.display_name}
                          </h3>
                          <button
                            onClick={() => handleEdit(toolName)}
                            className="text-xs text-blue-600 hover:text-blue-700 underline"
                          >
                            Edit
                          </button>
                        </div>
                        <p className="text-sm text-gray-600 mb-2">
                          {state.spec.description}
                        </p>
                        <div className="flex gap-4 text-xs text-gray-500">
                          <span>
                            <strong>Service:</strong> {state.spec.service}
                          </span>
                          <span>
                            <strong>Type:</strong> {state.spec.api_type}
                          </span>
                          <span>
                            <strong>Tool ID:</strong>{' '}
                            <code className="bg-gray-200 px-1 rounded">
                              {toolName}
                            </code>
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              {approvedCount} of {tools.length} tool(s) approved
            </div>
            <div className="flex gap-3">
              <button
                onClick={onCancel}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirm}
                disabled={approvedCount === 0}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Generate {approvedCount} Tool(s)
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
