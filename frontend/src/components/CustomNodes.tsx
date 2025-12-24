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
  bgColor: string;
  borderColor: string;
  textColor: string;
  descColor: string;
  handleColor: string;
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
        relative px-4 py-3 shadow-xl rounded-xl border-2 transition-all duration-300 ease-in-out cursor-pointer
        ${config.bgColor} ${config.borderColor} 
        /* Width logic: dynamic but constrained for readability */
        min-w-[220px] max-w-[400px] h-auto group
      `}
    >
      {/* Target Handle (Top) */}
      {type !== 'input' && (
        <Handle 
          type="target" 
          position={Position.Top} 
          className={`w-3 h-3 border-white ${config.handleColor}`} 
        />
      )}

      <div className="flex items-start gap-3">
        {/* Icon Container - flex-shrink-0 ensures icon doesn't squash */}
        <div className="text-2xl flex-shrink-0 mt-0.5 select-none">
          {config.icon}
        </div>

        {/* Text Content */}
        <div className="flex-1 min-w-0">
          {/* Label: Always shows completely now */}
          <div className={`
            font-bold leading-tight ${config.textColor} 
            whitespace-normal break-words
          `}>
            {data.label}
          </div>
          
          {data.description && (
            <div className={`
              text-xs mt-1.5 leading-relaxed ${config.descColor} 
              /* Description: Clamped unless clicked to expand */
              ${isExpanded ? 'block animate-in fade-in slide-in-from-top-1' : 'line-clamp-2'} 
              break-words
            `}>
              {data.description}
            </div>
          )}

          {/* Expanded Content Slot */}
          {isExpanded && children && (
            <div className="mt-3 pt-3 border-t border-black/5 animate-in zoom-in-95">
              {children}
            </div>
          )}
        </div>
      </div>

      {/* Source Handle (Bottom) */}
      {type !== 'output' && (
        <Handle 
          type="source" 
          position={Position.Bottom} 
          className={`w-3 h-3 border-white ${config.handleColor}`} 
        />
      )}
    </div>
  );
};

// --- Custom Node Definitions ---

export function InputNode({ data }: CustomNodeProps) {
  const label = data.label?.toLowerCase() || '';
  const config: NodeConfig = label.includes('date') 
    ? { icon: '📅', bgColor: 'bg-blue-50', borderColor: 'border-blue-400', textColor: 'text-blue-900', descColor: 'text-blue-700', handleColor: 'bg-blue-500' }
    : label.includes('month')
    ? { icon: '🗓️', bgColor: 'bg-indigo-50', borderColor: 'border-indigo-400', textColor: 'text-indigo-900', descColor: 'text-indigo-700', handleColor: 'bg-indigo-500' }
    : { icon: '📥', bgColor: 'bg-sky-50', borderColor: 'border-sky-400', textColor: 'text-sky-900', descColor: 'text-sky-700', handleColor: 'bg-sky-500' };

  return <BaseNode data={data} config={config} type="input" />;
}

export function AgentNode({ data }: CustomNodeProps) {
  const config: NodeConfig = { 
    icon: '🤖', bgColor: 'bg-purple-50', borderColor: 'border-purple-400', 
    textColor: 'text-purple-900', descColor: 'text-purple-700', handleColor: 'bg-purple-600' 
  };
  return (
    <BaseNode data={data} config={config} type="agent">
      <div className="space-y-1">
        <div className="text-[10px] font-bold text-purple-400 uppercase tracking-tighter">AI Core</div>
        <p className="text-[11px] text-purple-800 leading-tight">Capable of processing multi-step logic flows.</p>
      </div>
    </BaseNode>
  );
}

export function ToolNode({ data }: CustomNodeProps) {
  const name = String(data.tool_name || '').toLowerCase();
  // Tool icons based on your current technical skills: Qdrant, Postgres, or generic [cite: 22, 27, 33]
  const icon = name.includes('qdrant') ? '🔍' : name.includes('postgres') ? '🗄️' : '🔧';
  const config: NodeConfig = { 
    icon, bgColor: 'bg-emerald-50', borderColor: 'border-emerald-400', 
    textColor: 'text-emerald-900', descColor: 'text-emerald-700', handleColor: 'bg-emerald-600' 
  };
  
  return (
    <BaseNode data={data} config={config} type="tool">
      <div className="bg-white/50 rounded p-2 border border-emerald-100">
        <div className="text-[10px] font-mono text-emerald-600 break-all">ID: {data.tool_name || 'internal_tool'}</div>
      </div>
    </BaseNode>
  );
}

export function DecisionNode({ data }: CustomNodeProps) {
  const config: NodeConfig = { 
    icon: '🔀', bgColor: 'bg-amber-50', borderColor: 'border-amber-400', 
    textColor: 'text-amber-900', descColor: 'text-amber-700', handleColor: 'bg-amber-500' 
  };
  return <BaseNode data={data} config={config} type="decision" />;
}

export function OutputNode({ data }: CustomNodeProps) {
  const desc = data.description?.toLowerCase() || '';
  const config: NodeConfig = desc.includes('csv') 
    ? { icon: '📊', bgColor: 'bg-orange-50', borderColor: 'border-orange-400', textColor: 'text-orange-900', descColor: 'text-orange-700', handleColor: 'bg-orange-500' }
    : { icon: '📤', bgColor: 'bg-rose-50', borderColor: 'border-rose-400', textColor: 'text-rose-900', descColor: 'text-rose-700', handleColor: 'bg-rose-500' };

  return <BaseNode data={data} config={config} type="output" />;
}