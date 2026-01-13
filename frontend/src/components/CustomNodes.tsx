import React, { useState } from 'react';
import { Handle, Position } from 'reactflow';

// --- Types ---
interface NodeData {
  label: string;
  description?: string;
  tool_name?: string;
  [key: string]: unknown;
}

interface CustomNodeProps {
  data: NodeData;
}

interface NodeConfig {
  icon: string;
  headerColor: string; // Solid color for the header (e.g., 'bg-blue-600')
  headerBorder: string; // Border color for header (e.g., 'border-blue-700')
  handleColor: string; // Color for connection handles
}

// --- Reusable Wrapper Component ---
const BaseNode = ({
  data,
  config,
  type,
  children
}: {
  data: NodeData;
  config: NodeConfig;
  type: 'input' | 'output' | 'agent' | 'tool' | 'decision';
  children?: React.ReactNode;
}) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      onClick={() => setIsExpanded(!isExpanded)}
      className={`
        relative group
        min-w-[240px] max-w-[320px]
        rounded-xl
        transition-all duration-300 ease-out
        cursor-pointer
        shadow-sm hover:shadow-xl
        ${isExpanded ? 'scale-105 z-50' : 'hover:-translate-y-1 hover:scale-[1.02]'}
      `}
    >
      {/* Container holding Header + Body */}
      <div className="rounded-xl overflow-hidden bg-white border border-gray-200/60 transition-colors">

        {/* COLORED HEADER */}
        <div className={`
          px-4 py-3 
          ${config.headerColor} 
          border-b ${config.headerBorder}
          flex items-center gap-3
        `}>
          {/* Icon Circle */}
          <div className="
            w-8 h-8 rounded-lg bg-white/20 backdrop-blur-sm 
            flex items-center justify-center 
            text-lg shadow-inner
          ">
            {config.icon}
          </div>

          {/* Title & Type */}
          <div className="flex-1 min-w-0">
            <h3 className="text-white font-bold text-sm truncate leading-tight drop-shadow-sm">
              {data.label}
            </h3>
            <p className="text-white/80 text-[10px] font-medium uppercase tracking-wider">
              {type} Node
            </p>
          </div>

          {/* Expand Chevron */}
          <div className={`text-white/60 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`}>
            <svg width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 1L5 5L9 1" /></svg>
          </div>
        </div>

        {/* WHITE BODY */}
        <div className="p-4 bg-white relative">
          {data.description && (
            <p className={`
              text-xs leading-relaxed text-gray-600
              ${isExpanded ? 'block animate-in fade-in' : 'line-clamp-2'}
            `}>
              {data.description}
            </p>
          )}

          {/* Expanded Content Area */}
          {isExpanded && children && (
            <div
              className="
                mt-4 pt-3 border-t border-gray-100
                animate-in zoom-in-95 fade-in duration-200
              "
            >
              {children}
            </div>
          )}
        </div>
      </div>

      {/* Handles */}
      {type !== 'input' && (
        <Handle
          type="target"
          position={Position.Top}
          className={`
            w-3 h-3 rounded-full
            border-2 border-white 
            ${config.handleColor}
            transition-all duration-300
            hover:scale-150
            -mt-[5px]
          `}
        />
      )}

      {type !== 'output' && (
        <Handle
          type="source"
          position={Position.Bottom}
          className={`
            w-3 h-3 rounded-full
            border-2 border-white 
            ${config.handleColor}
            transition-all duration-300
            hover:scale-150
            -mb-[5px]
          `}
        />
      )}
    </div>
  );
};

// --- Custom Node Definitions ---

export function InputNode({ data }: CustomNodeProps) {
  const label = data.label?.toLowerCase() || '';

  // Default: Blue
  let config: NodeConfig = {
    icon: '📥',
    headerColor: 'bg-blue-600',
    headerBorder: 'border-blue-700',
    handleColor: 'bg-blue-600'
  };

  if (label.includes('date')) {
    config = {
      ...config,
      icon: '📅', // Cyan/Teal
      headerColor: 'bg-cyan-600',
      headerBorder: 'border-cyan-700',
      handleColor: 'bg-cyan-600'
    };
  } else if (label.includes('month')) {
    config = {
      ...config,
      icon: '🗓️', // Indigo
      headerColor: 'bg-indigo-600',
      headerBorder: 'border-indigo-700',
      handleColor: 'bg-indigo-600'
    };
  }

  return <BaseNode data={data} config={config} type="input" />;
}

export function AgentNode({ data }: CustomNodeProps) {
  // Purple/Violet for AI
  const config: NodeConfig = {
    icon: '🤖',
    headerColor: 'bg-violet-600',
    headerBorder: 'border-violet-700',
    handleColor: 'bg-violet-600'
  };

  return (
    <BaseNode data={data} config={config} type="agent">
      <div className="bg-violet-50 rounded-lg p-2.5 border border-violet-100 mt-2">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-1.5 h-1.5 rounded-full bg-violet-500 animate-pulse"></div>
          <span className="text-[10px] font-bold text-violet-700 uppercase tracking-wider">AI Core</span>
        </div>
        <p className="text-[11px] text-violet-900/80 leading-relaxed font-medium">
          Autonomous Execution
        </p>
      </div>
    </BaseNode>
  );
}

export function ToolNode({ data }: CustomNodeProps) {
  const name = String(data.tool_name || '').toLowerCase();

  const getDisplayLabel = (): string => {
    const mappings: Record<string, string> = {
      postgres_query: 'Database Reader',
      postgres_inspect_schema: 'Schema Inspector',
      postgres_write: 'Database Writer',
      gmail_send: 'Email Sender',
      slack_msg: 'Slack Notifier'
    };
    const originalName = String(data.tool_name || '');
    return mappings[originalName] || data.label;
  };

  let icon = '🔧';
  // Default: Emerald (Green)
  let headerColor = 'bg-emerald-600';
  let headerBorder = 'border-emerald-700';
  let handleColor = 'bg-emerald-600';

  if (name.includes('qdrant')) {
    icon = '🔍';
    // Orange for Search/Vector
    headerColor = 'bg-orange-600';
    headerBorder = 'border-orange-700';
    handleColor = 'bg-orange-600';
  } else if (name.includes('postgres')) {
    icon = '🗄️';
    // Slate/BlueGray for DB
    headerColor = 'bg-slate-600';
    headerBorder = 'border-slate-700';
    handleColor = 'bg-slate-600';
  }

  const config: NodeConfig = {
    icon,
    headerColor,
    headerBorder,
    handleColor
  };

  const displayData = { ...data, label: getDisplayLabel() };

  return (
    <BaseNode data={displayData} config={config} type="tool">
      <div className="bg-gray-50 rounded p-2 border border-gray-200 mt-2">
        <div className="flex justify-between items-center text-[10px]">
          <span className="text-gray-500 font-medium">System ID</span>
          <code className="font-mono text-gray-700">{data.tool_name}</code>
        </div>
      </div>
    </BaseNode>
  );
}

export function DecisionNode({ data }: CustomNodeProps) {
  // Amber/Yellow for Logic
  const config: NodeConfig = {
    icon: '🔀',
    headerColor: 'bg-amber-500',
    headerBorder: 'border-amber-600',
    handleColor: 'bg-amber-500'
  };

  return <BaseNode data={data} config={config} type="decision" />;
}

export function OutputNode({ data }: CustomNodeProps) {
  const desc = data.description?.toLowerCase() || '';

  let icon = '📤';
  // Rose/Pink for Output
  let headerColor = 'bg-rose-600';
  let headerBorder = 'border-rose-700';
  let handleColor = 'bg-rose-600';

  if (desc.includes('csv')) {
    icon = '📊';
    // Green for Data/Excel
    headerColor = 'bg-green-600';
    headerBorder = 'border-green-700';
    handleColor = 'bg-green-600';
  }

  const config: NodeConfig = {
    icon,
    headerColor,
    headerBorder,
    handleColor
  };

  return <BaseNode data={data} config={config} type="output" />;
}
