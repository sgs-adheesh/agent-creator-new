import React from 'react';
import ReactDOM from 'react-dom';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts';

// 1. Define Interfaces for Type Safety
interface ChartData {
  name: string;
  value?: number;
  details?: Record<string, unknown>[]; // Include original rows for detailed tooltip
  _categoryField?: string; // Field used for pie chart grouping
  _valueField?: string; // Field used for pie chart values
  [key: string]: string | number | undefined | Record<string, unknown>[];
}

interface DashboardChartsProps {
  pieData: ChartData[];
  barData: ChartData[];
  categoricalFields: string[];
  numericFields: string[];
  rowCount: number;
}

const MODERN_COLORS = [
  '#6366f1', // Indigo
  '#8b5cf6', // Purple
  '#ec4899', // Pink
  '#f43f5e', // Rose
  '#f59e0b', // Amber
  '#10b981', // Emerald
  '#3b82f6', // Blue
  '#14b8a6', // Teal
];

// Helper function to format field names (remove underscores, capitalize)
const formatFieldName = (fieldName: string): string => {
  if (!fieldName) return '';
  return fieldName
    .replace(/_/g, ' ') // Replace underscores with spaces
    .replace(/\b\w/g, l => l.toUpperCase()); // Capitalize first letter of each word
};

// Hover Tooltip Component (Simple preview before clicking)
interface HoverTooltipProps {
  active?: boolean;
  payload?: Array<{name: string; value: number; payload?: ChartData}>;
  label?: string;
}

const HoverTooltip: React.FC<HoverTooltipProps> = ({ active, payload }) => {
  if (!active || !payload || payload.length === 0) return null;

  const data = payload[0];
  const chartData = data.payload;

  return (
    <div className="bg-gradient-to-br from-indigo-50 to-purple-50 border-1 border-indigo-300 rounded-xl p-3 text-xs">
      <p className="font-bold text-indigo-900 mb-2 text-sm">{formatFieldName(data.name)}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-3">
          <span className="text-gray-600">Value:</span>
          <span className="font-bold text-indigo-700">{data.value.toLocaleString()}</span>
        </div>
        {chartData?.details && (
          <div className="text-indigo-600 text-xs italic mt-2 pt-2 border-t border-indigo-200">
            💡 Click to see {chartData.details.length} detailed record{chartData.details.length > 1 ? 's' : ''}
          </div>
        )}
      </div>
    </div>
  );
};

// Custom Modal Tooltip Component
interface ModalTooltipProps {
  data: ChartData | null;
  isOpen: boolean;
  onClose: () => void;
  isExpanded: boolean;
  onToggleExpand: () => void;
}

const ModalTooltip: React.FC<ModalTooltipProps> = ({ data, isOpen, onClose, isExpanded, onToggleExpand }) => {
  if (!isOpen || !data) return null;

  const details = data.details || [];
  
  // Helper function to extract value from JSONB or direct value
  const extractValue = (val: unknown): string => {
    if (val && typeof val === 'object' && 'value' in val) {
      return String((val as Record<string, unknown>).value || '');
    }
    return String(val || '');
  };

  // Get numeric fields from data (excluding name, details, and internal chart properties)
  const internalProps = [
    // Basic identifiers
    'name', 'details', 'payload', 'index',
    // Internal metadata fields (prefixed with _)
    '_categoryField', '_valueField',
    // Position coordinates
    'x', 'y', 'cx', 'cy', 'tooltipPosition', 'tooltipPayload',
    // Dimensions
    'width', 'height', 'radius', 'innerRadius', 'outerRadius', 'middleRadius', 'maxRadius',
    // Angles and positioning
    'startAngle', 'endAngle', 'midAngle', 'paddingAngle', 'percent',
    // Visual styling
    'fill', 'stroke', 'strokeWidth', 'color',
    // Pie chart specific
    'value', 'name', 'cx', 'cy', 'innerRadius', 'outerRadius',
    'startAngle', 'endAngle', 'paddingAngle', 'percent',
    // Bar chart specific
    'stackedBarStart', 'background', 'minPointSize', 'isAnimationActive'
  ];
  
  const numericEntries = Object.entries(data).filter(([key, value]) => 
    !internalProps.includes(key) && 
    typeof value === 'number' && 
    key !== 'value' // Exclude 'value' as it's the pie slice value itself
  );

  const modalContent = (
    <>
      {/* Subtle Backdrop - very light opacity */}
      <div 
        className="fixed inset-0 bg-black bg-opacity-20 z-[9999]"
        onClick={onClose}
      />
      
      {/* Modal Tooltip */}
      <div 
        className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-white border-1 border-indigo-400 rounded-xl text-xs z-[10000] transition-all duration-300"
        style={{ 
          maxWidth: isExpanded ? '600px' : '320px',
          maxHeight: '80vh',
          width: isExpanded ? '90%' : 'auto'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4">
          {/* Header with close and expand buttons */}
          <div className="flex items-center justify-between mb-3 border-b pb-3">
            <h3 className="font-bold text-gray-900 text-base">{formatFieldName(data.name)}</h3>
            <div className="flex gap-2">
              <button 
                className="text-indigo-600 hover:text-indigo-800 font-semibold text-xs px-3 py-1.5 rounded-lg hover:bg-indigo-50 transition-colors border border-indigo-200"
                onClick={onToggleExpand}
              >
                {isExpanded ? '◀ Minimize' : '▶ View Details'}
              </button>
              <button 
                className="text-gray-500 hover:text-gray-700 font-bold text-lg px-2 py-1 rounded-lg hover:bg-gray-100 transition-colors"
                onClick={onClose}
              >
                ×
              </button>
            </div>
          </div>
          
          {/* Summary (always visible) */}
          <div className="space-y-2 mb-3">
            <p className="text-gray-500 font-semibold text-xs uppercase">Summary</p>
            {numericEntries.map(([key, value]) => (
              <div key={key} className="flex items-center justify-between gap-4 py-1">
                <span className="text-gray-600 font-medium">{formatFieldName(key)}:</span>
                <span className="font-bold text-gray-900 text-sm">
                  {typeof value === 'number' ? value.toLocaleString() : String(value)}
                </span>
              </div>
            ))}
          </div>
          
          {/* Detailed breakdown (only when expanded) */}
          {isExpanded && details.length > 0 && (
            <div className="border-t pt-3 mt-3">
              <p className="text-gray-600 font-semibold mb-3 text-xs uppercase">
                Detailed Records ({details.length} total)
              </p>
              <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                {details.map((row, idx) => (
                  <div key={`detail-${idx}`} className="bg-gray-50 p-3 rounded-lg border border-gray-200">
                    <div className="text-xs text-indigo-600 mb-2 font-bold">Record {idx + 1}</div>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(row).map(([key, val]) => {
                        const displayValue = extractValue(val);
                        if (!displayValue || displayValue === 'undefined') return null;
                        
                        return (
                          <div key={`${idx}-${key}`} className="flex flex-col">
                            <span className="text-gray-500 text-xs font-medium">{formatFieldName(key)}</span>
                            <span className="text-gray-900 text-sm font-semibold">{displayValue}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Hint to expand */}
          {!isExpanded && details.length > 0 && (
            <div className="text-center pt-2 mt-2 border-t">
              <p className="text-gray-400 text-xs italic">
                Click "View Details" to see {details.length} detailed record{details.length > 1 ? 's' : ''}
              </p>
            </div>
          )}
        </div>
      </div>
    </>
  );

  // Render using portal to ensure it's at the top level of the DOM
  return ReactDOM.createPortal(modalContent, document.body);
};

const DashboardCharts: React.FC<DashboardChartsProps> = ({ 
  pieData, 
  barData, 
  categoricalFields, 
  numericFields, 
  rowCount 
}) => {
  const [selectedData, setSelectedData] = React.useState<ChartData | null>(null);
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [isExpanded, setIsExpanded] = React.useState(false);

  // Add global style to remove all focus outlines from SVG elements
  React.useEffect(() => {
    const style = document.createElement('style');
    style.textContent = `
      svg, svg *, .recharts-wrapper, .recharts-surface {
        outline: none !important;
      }
      svg:focus, svg *:focus {
        outline: none !important;
      }
    `;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  const handleChartClick = (data: ChartData) => {
    setSelectedData(data);
    setIsModalOpen(true);
    setIsExpanded(false);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setIsExpanded(false);
  };

  const handleToggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  return (
    <>
      <div className="space-y-8">
        
        {/* Pie Chart */}
        {pieData?.length > 0 && (
          <div className="bg-gradient-to-br from-white to-indigo-50 p-8 rounded-xl border-1 border-indigo-100">
            <div className="mb-6">
              <h4 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">Distribution Analysis</h4>
              <p className="text-sm text-gray-600 mt-1">
                {pieData && pieData.length > 0 && pieData[0]._categoryField && pieData[0]._valueField
                  ? `${formatFieldName(pieData[0]._categoryField)} by ${formatFieldName(pieData[0]._valueField)}`
                  : categoricalFields && categoricalFields.length > 0 && numericFields && numericFields.length > 0
                  ? `${formatFieldName(categoricalFields[0])} by ${formatFieldName(numericFields[0])}`
                  : 'Data distribution by category'}
              </p>
              <p className="text-xs text-indigo-600 mt-2 flex items-center gap-1">
                <span className="text-lg">👆</span> Hover to preview | Click to view full details
              </p>
            </div>
            
            <div style={{ width: '100%', height: 450 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
              <ResponsiveContainer>
                <PieChart style={{ outline: 'none' }}>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={100}
                    outerRadius={140}
                    paddingAngle={2}
                    stroke="none"
                    onClick={(data) => handleChartClick(data)}
                    style={{ cursor: 'pointer', outline: 'none' }}
                  >
                    {pieData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={MODERN_COLORS[index % MODERN_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    content={<HoverTooltip />}
                    cursor={{ fill: 'rgba(99, 102, 241, 0.1)' }}
                    wrapperStyle={{ pointerEvents: 'none' }}
                    allowEscapeViewBox={{ x: true, y: true }}
                  />
                  <Legend verticalAlign="bottom" height={50} iconType="circle" wrapperStyle={{ fontSize: '12px', fontWeight: '500' }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Bar Chart */}
        {barData?.length > 0 && (
          <div className="bg-gradient-to-br from-white to-purple-50 p-8 rounded-xl border-1 border-purple-100 ">
            <div className="mb-6">
              <h4 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-pink-600">Top Records Comparison</h4>
              <p className="text-sm text-gray-600 mt-1">Viewing top {Math.min(10, rowCount)} entries</p>
              <p className="text-xs text-purple-600 mt-2 flex items-center gap-1">
                <span className="text-lg">👆</span> Hover to preview | Click to view full details
              </p>
            </div>

            <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
              <ResponsiveContainer>
                <BarChart data={barData} margin={{ top: 10, right: 10, bottom: 100, left: 10 }} style={{ outline: 'none' }}>
                  <defs>
                    {MODERN_COLORS.map((color, i) => (
                      <linearGradient key={`grad-${i}`} id={`colorGrad-${i}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={color} stopOpacity={0.9}/>
                        <stop offset="95%" stopColor={color} stopOpacity={0.7}/>
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                  <XAxis 
                    dataKey="name" 
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#9ca3af', fontSize: 10 }}
                    height={70}
                    angle={-35}
                    textAnchor="end"
                    interval={0}
                  />
                  <YAxis 
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#9ca3af', fontSize: 11 }}
                  />
                  <Tooltip 
                    content={<HoverTooltip />}
                    cursor={{ fill: 'rgba(147, 51, 234, 0.1)' }}
                    wrapperStyle={{ pointerEvents: 'none' }}
                    allowEscapeViewBox={{ x: true, y: true }}
                  />
                  <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />
                  
                  {numericFields.map((field, idx) => (
                    <Bar 
                      key={field} 
                      dataKey={field}
                      name={formatFieldName(field)}
                      fill={`url(#colorGrad-${idx})`} 
                      radius={[8, 8, 0, 0]} 
                      barSize={36}
                      onClick={(data) => {
                        const chartData = data as unknown as ChartData;
                        handleChartClick(chartData);
                      }}
                      style={{ cursor: 'pointer', outline: 'none' }}
                      onMouseEnter={(data, index, e) => {
                        if (e?.target) {
                          (e.target as SVGElement).style.opacity = '0.8';
                        }
                      }}
                      onMouseLeave={(data, index, e) => {
                        if (e?.target) {
                          (e.target as SVGElement).style.opacity = '1';
                        }
                      }}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* Modal Tooltip */}
      <ModalTooltip 
        data={selectedData}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        isExpanded={isExpanded}
        onToggleExpand={handleToggleExpand}
      />
    </>
  );
};

export default DashboardCharts;
