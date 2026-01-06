import { useState } from 'react';

export interface ProgressStep {
  id: string;
  label: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error';
  detail?: string;
}

interface ProgressPanelProps {
  title: string;
  steps: ProgressStep[];
  isExpanded?: boolean;
  onToggle?: () => void;
}

const ProgressPanel = ({ title, steps, isExpanded = true, onToggle }: ProgressPanelProps) => {
  const [expanded, setExpanded] = useState(isExpanded);

  const handleToggle = () => {
    setExpanded(!expanded);
    if (onToggle) onToggle();
  };

  const getStatusIcon = (status: ProgressStep['status']) => {
    switch (status) {
      case 'completed':
        return <span className="text-green-600">✅</span>;
      case 'in_progress':
        return (
          <span className="inline-block animate-spin text-blue-600">⏳</span>
        );
      case 'error':
        return <span className="text-red-600">❌</span>;
      case 'pending':
        return <span className="text-gray-400">⏸️</span>;
      default:
        return null;
    }
  };

  // Determine overall status for title styling
  const hasError = steps.some(step => step.status === 'error');
  const allCompleted = steps.every(step => step.status === 'completed');
  const inProgress = steps.some(step => step.status === 'in_progress');

  const getTitleIcon = () => {
    if (hasError) return '❌';
    if (allCompleted) return '✅';
    if (inProgress) return '🔄';
    return '🔄';
  };

  const getTitleColor = () => {
    if (hasError) return 'text-red-700 bg-red-50 border-red-200';
    if (allCompleted) return 'text-green-700 bg-green-50 border-green-200';
    return 'text-blue-700 bg-blue-50 border-blue-200';
  };

  return (
    <div className={`border rounded-lg shadow-sm mb-4 ${getTitleColor()}`}>
      {/* Header */}
      <div
        className="flex items-center justify-between p-3 cursor-pointer hover:bg-opacity-80 transition-colors"
        onClick={handleToggle}
      >
        <div className="flex items-center gap-2 font-medium">
          <span>{getTitleIcon()}</span>
          <span>{title}</span>
        </div>
        <button
          className="text-sm px-2 py-1 rounded hover:bg-white hover:bg-opacity-50 transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            handleToggle();
          }}
        >
          {expanded ? '▼ Hide' : '▶ Show'}
        </button>
      </div>

      {/* Progress Steps */}
      {expanded && (
        <div className="border-t bg-white p-3 space-y-2">
          {steps.map((step) => (
            <div key={step.id} className="flex items-start gap-2">
              <div className="flex-shrink-0 mt-0.5">
                {getStatusIcon(step.status)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-800">
                  {step.label}
                </div>
                {step.detail && (
                  <div className="text-xs text-gray-600 mt-0.5">
                    {step.detail}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ProgressPanel;
