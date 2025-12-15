import { Handle, Position } from 'reactflow';

interface NodeData {
  label: string;
  description?: string;
  [key: string]: unknown;
}

interface CustomNodeProps {
  data: NodeData;
}

export function InputNode({ data }: CustomNodeProps) {
  // Get appropriate icon and styling based on input type
  const getInputConfig = () => {
    const label = data.label?.toLowerCase() || '';
    
    if (label.includes('date')) {
      return { 
        icon: '📅', 
        bgColor: 'bg-blue-50', 
        borderColor: 'border-blue-400',
        textColor: 'text-blue-900',
        descColor: 'text-blue-700'
      };
    }
    
    if (label.includes('month')) {
      return { 
        icon: '🗓️', 
        bgColor: 'bg-indigo-50', 
        borderColor: 'border-indigo-400',
        textColor: 'text-indigo-900',
        descColor: 'text-indigo-700'
      };
    }
    
    if (label.includes('year')) {
      return { 
        icon: '📆', 
        bgColor: 'bg-purple-50', 
        borderColor: 'border-purple-400',
        textColor: 'text-purple-900',
        descColor: 'text-purple-700'
      };
    }
    
    if (label.includes('form') || label.includes('custom')) {
      return { 
        icon: '📋', 
        bgColor: 'bg-teal-50', 
        borderColor: 'border-teal-400',
        textColor: 'text-teal-900',
        descColor: 'text-teal-700'
      };
    }
    
    // Default text input
    return { 
      icon: '📥', 
      bgColor: 'bg-blue-50', 
      borderColor: 'border-blue-400',
      textColor: 'text-blue-900',
      descColor: 'text-blue-700'
    };
  };
  
  const config = getInputConfig();
  
  return (
    <div className={`px-4 py-3 shadow-lg rounded-lg ${config.bgColor} border-2 ${config.borderColor} min-w-[150px]`}>
      <div className="flex items-center gap-2">
        <div className="text-2xl">{config.icon}</div>
        <div>
          <div className={`font-bold ${config.textColor}`}>{data.label}</div>
          {data.description && (
            <div className={`text-xs ${config.descColor} mt-1`}>{data.description}</div>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-blue-500" />
    </div>
  );
}

export function AgentNode({ data }: CustomNodeProps) {
  return (
    <div className="px-4 py-3 shadow-lg rounded-lg bg-purple-50 border-2 border-purple-500 min-w-[200px]">
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-purple-500" />
      <div className="flex items-center gap-2">
        <div className="text-2xl">🤖</div>
        <div className="flex-1">
          <div className="font-bold text-purple-900">{data.label}</div>
          {data.description && (
            <div className="text-xs text-purple-700 mt-1 line-clamp-2">{data.description}</div>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-purple-500" />
    </div>
  );
}

export function ToolNode({ data }: CustomNodeProps) {
  const getToolIcon = (toolName?: string) => {
    const name = String(toolName || '').toLowerCase();
    if (name.includes('qdrant')) return '🔍';
    if (name.includes('qbo') || name.includes('quickbooks')) return '💼';
    if (name.includes('postgres') || name.includes('database')) return '🗄️';
    return '🔧';
  };

  return (
    <div className="px-4 py-3 shadow-lg rounded-lg bg-green-50 border-2 border-green-500 min-w-[160px]">
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-green-500" />
      <div className="flex items-center gap-2">
        <div className="text-2xl">{getToolIcon(data.tool_name as string)}</div>
        <div className="flex-1">
          <div className="font-bold text-green-900">{data.label}</div>
          {data.description && (
            <div className="text-xs text-green-700 mt-1 line-clamp-2">{data.description}</div>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-green-500" />
    </div>
  );
}

export function OutputNode({ data }: CustomNodeProps) {
  // Get appropriate icon and styling based on output format
  const getOutputConfig = () => {
    const description = data.description?.toLowerCase() || '';
    
    if (description.includes('csv')) {
      return { 
        icon: '📊', 
        bgColor: 'bg-orange-50', 
        borderColor: 'border-orange-400',
        textColor: 'text-orange-900',
        descColor: 'text-orange-700'
      };
    }
    
    if (description.includes('json')) {
      return { 
        icon: '{}', 
        bgColor: 'bg-amber-50', 
        borderColor: 'border-amber-400',
        textColor: 'text-amber-900',
        descColor: 'text-amber-700'
      };
    }
    
    if (description.includes('markdown')) {
      return { 
        icon: '📝', 
        bgColor: 'bg-yellow-50', 
        borderColor: 'border-yellow-400',
        textColor: 'text-yellow-900',
        descColor: 'text-yellow-700'
      };
    }
    
    if (description.includes('table')) {
      return { 
        icon: '📋', 
        bgColor: 'bg-emerald-50', 
        borderColor: 'border-emerald-400',
        textColor: 'text-emerald-900',
        descColor: 'text-emerald-700'
      };
    }
    
    // Default text output
    return { 
      icon: '📤', 
      bgColor: 'bg-orange-50', 
      borderColor: 'border-orange-400',
      textColor: 'text-orange-900',
      descColor: 'text-orange-700'
    };
  };
  
  const config = getOutputConfig();
  
  return (
    <div className={`px-4 py-3 shadow-lg rounded-lg ${config.bgColor} border-2 ${config.borderColor} min-w-[150px]`}>
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-orange-500" />
      <div className="flex items-center gap-2">
        <div className="text-2xl">{config.icon}</div>
        <div>
          <div className={`font-bold ${config.textColor}`}>{data.label}</div>
          {data.description && (
            <div className={`text-xs ${config.descColor} mt-1`}>{data.description}</div>
          )}
        </div>
      </div>
    </div>
  );
}

export function DecisionNode({ data }: CustomNodeProps) {
  return (
    <div className="px-4 py-3 shadow-lg rounded-lg bg-yellow-50 border-2 border-yellow-500 min-w-[180px]">
      <Handle type="target" position={Position.Top} className="w-3 h-3 bg-yellow-500" />
      <div className="flex items-center gap-2">
        <div className="text-2xl">🔀</div>
        <div className="flex-1">
          <div className="font-bold text-yellow-900">{data.label}</div>
          {data.description && (
            <div className="text-xs text-yellow-700 mt-1 line-clamp-2">{data.description}</div>
          )}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="w-3 h-3 bg-yellow-500" />
    </div>
  );
}
