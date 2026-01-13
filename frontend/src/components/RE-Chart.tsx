import React from 'react';
import ReactDOM from 'react-dom';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  LineChart, Line,
  AreaChart, Area,
  ScatterChart, Scatter,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  RadialBarChart, RadialBar,
  ComposedChart,
  FunnelChart, Funnel, LabelList,
  Treemap,
  Sankey,
  Rectangle,
  ZAxis
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

interface ChartMetadata {
  id: string;
  type: string;
  title: string;
  description: string;
  data_source?: {
    x_axis?: string;
    y_axis?: string;
    group_by?: string;
    aggregate?: string | { field?: string; function?: string };
    [key: string]: any; // Allow extra properties like metrics, categories, etc.
  };
  config?: Record<string, any>; // Visual configuration (colors, orientation, stackOffset, etc.)
}

interface DashboardChartsProps {
  pieData?: ChartData[];
  barData?: ChartData[];
  lineData?: ChartData[];
  areaData?: ChartData[];
  scatterData?: ChartData[];
  candleData?: ChartData[];
  waterfallData?: ChartData[];
  stackedData?: ChartData[];
  radarData?: ChartData[];
  treemapData?: ChartData[];
  funnelData?: ChartData[];
  radialData?: ChartData[];
  composedData?: ChartData[];
  sankeyData?: { nodes: any[], links: any[] };
  categoricalFields: string[];
  numericFields: string[];
  rowCount: number;
  requestedChartTypes?: string[];
  chartMetadata?: ChartMetadata[]; // Chart titles and descriptions from visualization_config
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

// Helper function to calculate luminance and determine if color is light or dark
const getLuminance = (hex: string): number => {
  const rgb = hex.match(/^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i);
  if (!rgb) return 0.5;
  const r = parseInt(rgb[1], 16) / 255;
  const g = parseInt(rgb[2], 16) / 255;
  const b = parseInt(rgb[3], 16) / 255;
  // Relative luminance formula
  const [rs, gs, bs] = [r, g, b].map(val => {
    return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
};

const getTextColor = (bgColor: string): string => {
  const luminance = getLuminance(bgColor);
  // Use white text on dark backgrounds (luminance < 0.5), dark text on light backgrounds
  return luminance < 0.5 ? '#ffffff' : '#1f2937';
};

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
  payload?: Array<{ name: string; value: number; payload?: ChartData }>;
  label?: string;
}

const HoverTooltip: React.FC<HoverTooltipProps & { xLabel?: string; yLabel?: string }> = ({ active, payload, label, xLabel, yLabel }) => {
  if (!active || !payload || payload.length === 0) return null;

  // Determine Title
  // For categorical charts (Bar, Line), 'label' is the X-axis category.
  // For Pie, 'label' might be undefined, and we want the slice name (payload[0].name).
  // For Scatter, 'label' might be valid or we use payload name.
  const firstItem = payload[0];
  const chartData = firstItem.payload;

  let title = label;
  if (!title && chartData.name) {
    title = chartData.name;
  } else if (!title && firstItem.name) {
    title = firstItem.name;
  }

  return (
    <div className="bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-300 rounded-xl p-3 text-xs shadow-lg backdrop-blur-sm bg-white/95 min-w-[150px] z-50">
      <p className="font-bold text-indigo-900 mb-2 text-sm border-b border-indigo-200 pb-1">
        {formatFieldName(String(title))}
      </p>
      <div className="space-y-1.5">
        {payload.map((entry: any, idx: number) => {
          const dataObj = entry.payload || {};

          // 1. Candlestick Logic: Show OHLC explicitly if available
          if ((entry.name === 'Open-Close' || entry.name === 'open') && dataObj.open !== undefined) {
            return (
              <div key={`ohlc-${idx}`} className="space-y-1 mt-1 border-b border-indigo-50 pb-1 mb-1 last:border-0 last:mb-0 last:pb-0">
                <div className="flex justify-between gap-4"><span className="text-gray-500 font-medium">Open:</span><span className="font-bold text-indigo-700">{Number(dataObj.open).toLocaleString()}</span></div>
                <div className="flex justify-between gap-4"><span className="text-gray-500 font-medium">Close:</span><span className="font-bold text-indigo-700">{Number(dataObj.close).toLocaleString()}</span></div>
                <div className="flex justify-between gap-4"><span className="text-gray-500 font-medium">High:</span><span className="font-bold text-green-600">{Number(dataObj.high).toLocaleString()}</span></div>
                <div className="flex justify-between gap-4"><span className="text-gray-500 font-medium">Low:</span><span className="font-bold text-red-500">{Number(dataObj.low).toLocaleString()}</span></div>
              </div>
            );
          }
          if (entry.name === 'wick' || entry.name === 'Range') return null;

          // 2. Scatter/Bubble Logic: Interpret X/Y/Z, using xLabel/yLabel if provided
          // If the entry represents a point and has coordinate data
          if ((entry.name === 'Data' || !entry.name) && (dataObj.x !== undefined || dataObj.y !== undefined)) {
            const xTitle = xLabel ? formatFieldName(xLabel) : 'X';
            const yTitle = yLabel ? formatFieldName(yLabel) : 'Y';
            return (
              <div key={`scatter-${idx}`} className="space-y-1 mt-1">
                {dataObj.x !== undefined && (
                  <div className="flex justify-between gap-4"><span className="text-gray-500 font-medium">{xTitle}:</span><span className="font-bold text-indigo-700">{Number(dataObj.x).toLocaleString()}</span></div>
                )}
                {dataObj.y !== undefined && (
                  <div className="flex justify-between gap-4"><span className="text-gray-500 font-medium">{yTitle}:</span><span className="font-bold text-indigo-700">{Number(dataObj.y).toLocaleString()}</span></div>
                )}
                {dataObj.z !== undefined && (
                  <div className="flex justify-between gap-4"><span className="text-gray-500 font-medium">Size:</span><span className="font-bold text-indigo-700">{Number(dataObj.z).toLocaleString()}</span></div>
                )}
              </div>
            );
          }

          // 3. Standard Logic for Bars, Lines, Areas, Waterfall
          // Rename generic 'Value' to 'Amount' for better UX
          let labelName = formatFieldName(entry.name);
          if (labelName === 'Value') labelName = 'Amount';

          let valDisplay = '';
          const rawVal = entry.value;

          if (Array.isArray(rawVal) && rawVal.length === 2 && typeof rawVal[0] === 'number') {
            // Waterfall Delta
            const delta = rawVal[1] - rawVal[0];
            valDisplay = Number(Math.abs(delta)).toLocaleString();
            if (delta < 0) valDisplay = `-${valDisplay}`;
          } else if (typeof rawVal === 'number') {
            valDisplay = rawVal.toLocaleString();
          } else {
            valDisplay = String(rawVal);
          }

          return (
            <div key={`item-${idx}`} className="flex justify-between items-center gap-4">
              <span className="text-gray-600 font-medium flex items-center gap-2">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color || entry.fill || '#6366f1' }}></span>
                {labelName}
              </span>
              <span className="font-bold text-indigo-700 tabular-nums">{valDisplay}</span>
            </div>
          );
        })}

        {chartData?.details && (
          <div className="text-indigo-600 text-[10px] italic mt-2 pt-2 border-t border-indigo-100 flex items-center gap-1">
            <span>👆</span> Click to see {chartData.details.length} record{chartData.details.length !== 1 ? 's' : ''}
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
  lineData,
  areaData,
  scatterData,
  candleData,
  waterfallData,
  stackedData,
  radarData,
  treemapData,
  funnelData,
  radialData,
  composedData,
  sankeyData,
  categoricalFields,
  numericFields,
  rowCount,
  requestedChartTypes = [],
  chartMetadata = []
}) => {

  // Helper to get chart metadata by type
  const getChartMetadata = (chartType: string): ChartMetadata | null => {
    return chartMetadata.find(m => m.type.toLowerCase() === chartType.toLowerCase()) || null;
  };
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

  const handleChartClick = (data: any) => {
    // 🛡️ Defensive Data Unwrapping
    // Recharts passes different structures (data object, or { payload: data }, or sometimes Event)

    let chartItem = data;

    // 1. If it's wrapped in 'payload' (Scatter, Line, Area often do this)
    if (chartItem && chartItem.payload) {
      chartItem = chartItem.payload;
    }

    // 2. Check if it's a DOM Event (we CANNOT use this as data)
    const isEvent = chartItem && (
      chartItem.nativeEvent ||
      chartItem.preventDefault ||
      chartItem.stopPropagation ||
      chartItem.type === 'click'
    );

    // 3. Validation: Must have data-like properties (name, details)
    const hasData = chartItem && (chartItem.name !== undefined || chartItem.details !== undefined);

    if (!isEvent && hasData) {
      console.log('✅ Chart Click Validated:', chartItem);
      setSelectedData(chartItem as ChartData);
      setIsModalOpen(true);
      setIsExpanded(false);
    } else {
      console.warn('⚠️ Chart Click Ignored (Invalid Data or Event detected):', data);
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setIsExpanded(false);
  };

  const handleToggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  const hasConfig = requestedChartTypes && requestedChartTypes.length > 0;
  const requested = requestedChartTypes.map(t => t.toLowerCase());

  // When config exists, ONLY show explicitly requested charts
  // When no config, show default charts (pie, bar)
  const wantsPie = hasConfig ? requested.some(t => t.includes('pie')) : true;
  // logic change: wantsBar only targets "standard" bars. Stacked is handled separately.
  const wantsBar = hasConfig ? requested.some(t => t.includes('bar') && !t.includes('radial') && !t.includes('stacked')) : true;
  const wantsStacked = requested.some(t => t.includes('stacked')); // Explicitly requested stacked
  const wantsLine = requested.some(t => t.includes('line'));
  const wantsArea = requested.some(t => t.includes('area'));
  const wantsScatter = requested.some(t => t.includes('scatter'));
  const wantsRadar = requested.some(t => t.includes('radar'));
  const wantsRadialBar = requested.some(t => t.includes('radial'));
  const wantsComposed = requested.some(t => t.includes('composed') || t.includes('mixed'));
  const wantsFunnel = requested.some(t => t.includes('funnel'));
  const wantsTreemap = requested.some(t => t.includes('tree') || t.includes('treemap'));
  const wantsSankey = requested.some(t => t.includes('sankey'));
  const wantsHeatmap = requested.some(t => t.includes('heatmap'));
  const wantsWaterfall = requested.some(t => t.includes('waterfall'));
  const wantsCandlestick = requested.some(t => t.includes('candle'));
  const wantsBubble = requested.some(t => t.includes('bubble'));

  console.log('📊 Chart rendering config:', {
    hasConfig,
    requestedChartTypes,
    chartsToShow: {
      pie: wantsPie,
      bar: wantsBar,
      line: wantsLine,
      area: wantsArea,
      scatter: wantsScatter,
      radar: wantsRadar,
      radialBar: wantsRadialBar,
      composed: wantsComposed,
      funnel: wantsFunnel,
      treemap: wantsTreemap,
      sankey: wantsSankey,
      heatmap: wantsHeatmap,
      waterfall: wantsWaterfall,
      candlestick: wantsCandlestick,
      stacked: wantsStacked,
      bubble: wantsBubble
    }
  });

  return (
    <>
      <div className="space-y-8">

        {/* Pie Chart */}
        {/* Pie Chart */}
        {((pieData?.length ?? 0) > 0) && wantsPie && (() => {
          const meta = getChartMetadata('pie');
          // We know pieData is defined and has items here due to the check above
          const safeData = pieData!;

          return (
            <div className="bg-gradient-to-br from-white via-indigo-50 to-purple-50 p-8 rounded-2xl border-2 border-indigo-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-500">
                  {meta?.title || 'Distribution Analysis'}
                </h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">
                  {meta?.description || (safeData[0]._categoryField && safeData[0]._valueField
                    ? `${formatFieldName(safeData[0]._categoryField)} by ${formatFieldName(safeData[0]._valueField)}`
                    : categoricalFields && categoricalFields.length > 0 && numericFields && numericFields.length > 0
                      ? `${formatFieldName(categoricalFields[0])} by ${formatFieldName(numericFields[0])}`
                      : 'Data distribution by category')}
                </p>
                <p className="text-xs text-indigo-600 mt-3 flex items-center gap-2 bg-indigo-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to preview | Click to view full details
                </p>
              </div>

              <div style={{ width: '100%', height: 450 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
                <ResponsiveContainer>
                  <PieChart style={{ outline: 'none' }}>
                    <Pie
                      data={safeData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={100}
                      outerRadius={140}
                      paddingAngle={2}
                      stroke="none"
                      onClick={(data) => {
                        const chartData = data as unknown as ChartData;
                        handleChartClick(chartData);
                      }}
                    >
                      {safeData.map((_, index) => (
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
          );
        })()}

        {/* Standard Bar Chart */}
        {((barData?.length ?? 0) > 0 && wantsBar) && (() => {
          const meta = getChartMetadata('bar');

          return (
            <div className="bg-gradient-to-br from-white via-purple-50 to-sky-50 p-8 rounded-2xl border-2 border-purple-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-600 via-sky-600 to-purple-500">
                  {meta?.title || 'Top Records Comparison'}
                </h4>
                {meta?.description && (
                  <p className="text-sm text-gray-700 mt-2 font-medium">{meta.description}</p>
                )}
                <p className="text-sm text-gray-700 mt-2 font-medium">Viewing top {Math.min(10, rowCount)} entries</p>
                <p className="text-xs text-purple-600 mt-3 flex items-center gap-2 bg-purple-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to preview | Click to view full details
                </p>
              </div>

              <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
                <ResponsiveContainer>
                  <BarChart data={barData} margin={{ top: 10, right: 10, bottom: 100, left: 10 }} style={{ outline: 'none' }}>
                    <defs>
                      {MODERN_COLORS.map((color, i) => (
                        <linearGradient key={`grad-${i}`} id={`colorGrad-${i}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={color} stopOpacity={0.9} />
                          <stop offset="95%" stopColor={color} stopOpacity={0.7} />
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
                      tickLine={false}
                      tick={{ fill: '#9ca3af', fontSize: 11 }}
                      domain={['auto', 'auto']}
                    />
                    <Tooltip
                      content={<HoverTooltip />}
                      cursor={{ fill: 'rgba(147, 51, 234, 0.1)' }}
                      wrapperStyle={{ pointerEvents: 'none' }}
                      allowEscapeViewBox={{ x: true, y: true }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />

                    {/* Standard Bar Rendering */}
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
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}

        {/* Stacked Bar Chart (Dedicated Block) */}
        {((stackedData?.length ?? 0) > 0 || (barData?.length ?? 0) > 0) && wantsStacked && (() => {
          const meta = getChartMetadata('stacked_bar');
          // Prefer stackedData, fallback to barData
          const plotData = (stackedData?.length ?? 0) > 0 ? stackedData : barData;

          return (
            <div className="bg-gradient-to-br from-white via-indigo-50 to-blue-50 p-8 rounded-2xl border-2 border-indigo-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-blue-600 to-indigo-500">
                  {meta?.title || 'Stacked Bar Analysis'}
                </h4>
                {meta?.description && (
                  <p className="text-sm text-gray-700 mt-2 font-medium">{meta.description}</p>
                )}
                <p className="text-xs text-indigo-600 mt-3 flex items-center gap-2 bg-indigo-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to preview segments
                </p>
              </div>
              <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
                <ResponsiveContainer>
                  <BarChart data={plotData} margin={{ top: 10, right: 10, bottom: 100, left: 10 }} style={{ outline: 'none' }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                    <XAxis
                      dataKey="name"
                      angle={-35}
                      textAnchor="end"
                      height={70}
                      tick={{ fill: '#9ca3af', fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                      interval={0}
                    />
                    <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<HoverTooltip />} cursor={{ fill: 'rgba(99, 102, 241, 0.05)' }} />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />

                    {numericFields.map((field, idx) => (
                      <Bar
                        key={field}
                        dataKey={field}
                        name={formatFieldName(field)}
                        stackId="a"
                        fill={MODERN_COLORS[idx % MODERN_COLORS.length]}
                        barSize={40}
                        onClick={(data) => {
                          // Type-safe click handler
                          const chartData = (data.payload || data) as unknown as ChartData;
                          handleChartClick(chartData);
                        }}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}

        {/* Waterfall Chart (Separated) */}
        {wantsWaterfall && ((waterfallData?.length ?? 0) > 0) && (() => {
          const meta = getChartMetadata('waterfall');
          return (
            <div className="bg-gradient-to-br from-white via-emerald-50 to-teal-50 p-8 rounded-2xl border-2 border-emerald-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-600 via-teal-600 to-emerald-500">
                  {meta?.title || 'Waterfall Analysis'}
                </h4>
                {meta?.description && <p className="text-sm text-gray-700 mt-2 font-medium">{meta.description}</p>}
              </div>
              <div style={{ width: '100%', height: 500 }}>
                <ResponsiveContainer>
                  <BarChart data={waterfallData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
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
                      domain={['auto', 'auto']}
                    />
                    <Tooltip content={<HoverTooltip />} cursor={{ fill: 'rgba(16, 185, 129, 0.1)' }} />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />
                    <Bar dataKey="value" name="Value" radius={[4, 4, 4, 4]} barSize={40}>
                      {waterfallData!.map((entry, index) => {
                        const val = entry.value;
                        let color = '#94a3b8';
                        if (Array.isArray(val) && val.length === 2) {
                          color = val[1] > val[0] ? '#10b981' : (val[1] < val[0] ? '#f43f5e' : '#94a3b8');
                        }
                        return <Cell key={`cell-${index}`} fill={color} />;
                      })}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}

        {/* Line Chart (user-requested) */}
        {wantsLine && ((lineData?.length ?? 0) > 0 || (barData?.length ?? 0) > 0) && (
          <div className="bg-gradient-to-br from-white via-blue-50 to-sky-50 p-8 rounded-2xl border-2 border-blue-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
            <div className="mb-6">
              <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-sky-600 to-blue-500">Trend Analysis (Line)</h4>
              <p className="text-sm text-gray-700 mt-2 font-medium">Viewing top {Math.min(10, rowCount)} entries</p>
              <p className="text-xs text-blue-600 mt-3 flex items-center gap-2 bg-blue-50 px-3 py-1.5 rounded-full w-fit">
                <span className="text-base">👆</span> Hover to preview | Click to view full details
              </p>
            </div>

            <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
              <ResponsiveContainer>
                <LineChart data={((lineData?.length ?? 0) > 0) ? lineData : barData} margin={{ top: 10, right: 10, bottom: 100, left: 10 }} style={{ outline: 'none' }}>
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
                    cursor={{ stroke: 'rgba(37, 99, 235, 0.4)', strokeWidth: 2 }}
                    wrapperStyle={{ pointerEvents: 'none' }}
                    allowEscapeViewBox={{ x: true, y: true }}
                  />
                  <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />

                  {numericFields.map((field, idx) => (
                    <Line
                      key={field}
                      type="monotone"
                      dataKey={field}
                      name={formatFieldName(field)}
                      stroke={MODERN_COLORS[idx % MODERN_COLORS.length]}
                      strokeWidth={2}
                      dot={{ r: 2 }}
                      activeDot={{ r: 4 }}
                      onClick={(data: any) => {
                        const chartData = (data.payload || data) as ChartData;
                        handleChartClick(chartData);
                      }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Area Chart (user-requested) */}
        {wantsArea && ((areaData?.length ?? 0) > 0 || (barData?.length ?? 0) > 0) && (
          <div className="bg-gradient-to-br from-white via-purple-50 to-indigo-50 p-8 rounded-2xl border-2 border-purple-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
            <div className="mb-6">
              <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-600 via-indigo-600 to-purple-500">Accumulation Analysis (Area)</h4>
              <p className="text-sm text-gray-700 mt-2 font-medium">Viewing top {Math.min(10, rowCount)} entries</p>
              <p className="text-xs text-purple-600 mt-3 flex items-center gap-2 bg-purple-50 px-3 py-1.5 rounded-full w-fit">
                <span className="text-base">👆</span> Hover to preview | Click to view full details
              </p>
            </div>

            <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
              <ResponsiveContainer>
                <AreaChart data={((areaData?.length ?? 0) > 0) ? areaData : barData} margin={{ top: 10, right: 10, bottom: 40, left: 10 }} style={{ outline: 'none' }}>
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
                    cursor={{ stroke: 'rgba(16, 185, 129, 0.4)', strokeWidth: 2 }}
                    wrapperStyle={{ pointerEvents: 'none' }}
                    allowEscapeViewBox={{ x: true, y: true }}
                  />
                  <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />

                  {numericFields.map((field, idx) => (
                    <Area
                      key={field}
                      type="monotone"
                      dataKey={field}
                      name={formatFieldName(field)}
                      stroke={MODERN_COLORS[idx % MODERN_COLORS.length]}
                      fill={MODERN_COLORS[idx % MODERN_COLORS.length]}
                      fillOpacity={0.35}
                      strokeWidth={2}
                      onClick={(data: any) => {
                        const chartData = (data.payload || data) as ChartData;
                        handleChartClick(chartData);
                      }}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Scatter / Bubble Plot */}
        {/* Scatter / Bubble Plot */}
        {(wantsScatter || wantsBubble) && ((scatterData?.length ?? 0) > 0 || (barData?.length ?? 0) > 0) && (() => {
          const meta = getChartMetadata(wantsBubble ? 'bubble' : 'scatter');

          // Determine actual data keys by inspecting first data item
          const dataToRender = ((scatterData?.length ?? 0) > 0) ? scatterData : barData;
          const firstItem = dataToRender?.[0] as any;

          // Default X-Axis Logic
          let xKey = meta?.data_source?.x_axis || (numericFields.length >= 1 ? numericFields[0] : 'name');

          // Default Y-Axis Logic: Prefer specific Y-axis config, then second numeric field, then 'y'
          let yKey = meta?.data_source?.y_axis || (numericFields.length >= 2 ? numericFields[1] : (numericFields[0] !== xKey ? numericFields[0] : 'y'));

          // For Bubble, we need a 3rd numeric field for Z-axis, or use value/size
          const zAxisField = wantsBubble && numericFields.length >= 3 ? numericFields[2] : (numericFields.includes('size') ? 'size' : (numericFields.includes('z') ? 'z' : undefined));

          // Auto-detect keys if explicit x/y/z present (Priority 1)
          if (firstItem && ('x' in firstItem) && ('y' in firstItem)) {
            xKey = 'x';
            yKey = 'y';
          }

          let zKey = wantsBubble && numericFields.length >= 3 ? numericFields[2] : undefined;
          if (firstItem && 'z' in firstItem) zKey = 'z';
          if (firstItem && 'size' in firstItem) zKey = 'size';

          const isCategoricalX = typeof firstItem?.[xKey] === 'string';

          // Heuristic to fix swapped labels (Total vs Count)
          let xLabel = meta?.data_source?.x_axis || formatFieldName(xKey);
          let yLabel = meta?.data_source?.y_axis || formatFieldName(yKey);

          if (!isCategoricalX && (dataToRender?.length || 0) > 0) {
            const count = dataToRender.length;
            const avgX = dataToRender.reduce((sum: number, item: any) => sum + (Number(item[xKey]) || 0), 0) / count;
            const avgY = dataToRender.reduce((sum: number, item: any) => sum + (Number(item[yKey]) || 0), 0) / count;

            const xLower = String(xLabel).toLowerCase();
            const yLower = String(yLabel).toLowerCase();

            const xM = xLower.match(/(count|num|qty)/);
            const yM = yLower.match(/(total|amount|cost|sum)/);

            // If X is big (Total) but labeled Count, and Y is small (Count) but labeled Total
            if (avgX > avgY * 2 && xM && yM) {
              // console.log('🔄 Swapping Scatter Axis Labels based on heuristic');
              const temp = xLabel;
              xLabel = yLabel;
              yLabel = temp;
            }
          }

          return (
            <div className="bg-gradient-to-br from-white via-amber-50 to-orange-50 p-8 rounded-2xl border-2 border-amber-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-orange-600 via-amber-600 to-orange-500">
                  {meta?.title || (wantsBubble ? 'Bubble Analysis' : 'Scatter Distribution')}
                </h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">{meta?.description || `Analysis of ${xLabel} vs ${yLabel}`}</p>
                <p className="text-xs text-orange-600 mt-3 flex items-center gap-2 bg-orange-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to view details
                </p>
              </div>
              <div style={{ width: '100%', height: 500 }}>
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                    <XAxis
                      dataKey={xKey}
                      type={isCategoricalX ? "category" : "number"}
                      name={xLabel}
                      domain={isCategoricalX ? undefined : ['auto', 'auto']}
                      allowDuplicatedCategory={isCategoricalX ? false : true}
                      angle={isCategoricalX ? -35 : 0}
                      textAnchor={isCategoricalX ? 'end' : 'middle'}
                      height={70}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#9ca3af', fontSize: 10 }}
                    />
                    <YAxis
                      dataKey={yKey}
                      type="number"
                      name={yLabel}
                      domain={['auto', 'auto']}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#9ca3af', fontSize: 11 }}
                    />

                    {zKey && <ZAxis dataKey={zKey} range={[60, 600]} name={formatFieldName(zKey)} />}
                    <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<HoverTooltip xLabel={xLabel} yLabel={yLabel} />} />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />
                    <Scatter
                      name={meta?.title || "Data Points"}
                      data={dataToRender}
                      fill={MODERN_COLORS[6]}
                      onClick={(data: any) => {
                        const chartData = (data.payload || data) as ChartData;
                        handleChartClick(chartData);
                      }}
                    />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}

        {/* Radar Chart (multi-metric comparison) */}
        {((radarData?.length ?? 0) > 0 || (barData?.length ?? 0) > 0) && wantsRadar && numericFields.length >= 2 && (() => {
          const dataToRender = (radarData?.length ?? 0) > 0 ? radarData : barData;
          console.log('🕸️ Radar chart rendering');
          return (
            <div className="bg-gradient-to-br from-white via-green-50 to-emerald-50 p-8 rounded-2xl border-2 border-green-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-green-600 via-emerald-600 to-green-500">
                  Multi-Metric Analysis (Radar)
                </h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">Comparing multiple metrics across categories</p>
                <p className="text-xs text-green-600 mt-3 flex items-center gap-2 bg-green-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to preview | Click to view full details
                </p>
              </div>

              <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
                <ResponsiveContainer>
                  <RadarChart data={dataToRender!.slice(0, 8)} style={{ outline: 'none' }}>
                    <PolarGrid stroke="#d1fae5" />
                    <PolarAngleAxis
                      dataKey="name"
                      tick={{ fill: '#9ca3af', fontSize: 11 }}
                    />
                    <PolarRadiusAxis
                      angle={90}
                      tick={{ fill: '#9ca3af', fontSize: 10 }}
                    />
                    <Tooltip
                      content={<HoverTooltip />}
                      wrapperStyle={{ pointerEvents: 'none' }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />

                    {numericFields
                      .filter(field => {
                        // Only include fields that actually exist in the data being rendered
                        const dataSample = (radarData?.length ?? 0) > 0 ? radarData![0] : (barData?.[0]);
                        return dataSample && typeof dataSample[field as keyof ChartData] === 'number';
                      })
                      .slice(0, 5)
                      .map((field, idx) => (
                        <Radar
                          key={field}
                          name={formatFieldName(field)}
                          dataKey={field}
                          stroke={MODERN_COLORS[idx % MODERN_COLORS.length]}
                          fill={MODERN_COLORS[idx % MODERN_COLORS.length]}
                          fillOpacity={0.3}
                          onClick={(data) => {
                            const chartData = data as unknown as ChartData;
                            handleChartClick(chartData);
                          }}
                        />
                      ))}
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}

        {/* Radial Bar Chart (circular progress) */}
        {((radialData?.length ?? 0) > 0 || (barData?.length ?? 0) > 0) && wantsRadialBar && (() => {
          const meta = getChartMetadata('radialbar');
          const dataToRender = (radialData?.length ?? 0) > 0 ? radialData : barData;
          return (
            <div className="bg-gradient-to-br from-white via-violet-50 to-purple-50 p-8 rounded-2xl border-2 border-violet-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-violet-600 via-purple-600 to-violet-500">
                  {meta?.title || 'Progress Analysis (Radial)'}
                </h4>
                {meta?.description && (
                  <p className="text-sm text-gray-700 mt-2 font-medium">{meta.description}</p>
                )}
                <p className="text-sm text-gray-700 mt-2 font-medium">Circular progress visualization</p>
                <p className="text-xs text-violet-600 mt-3 flex items-center gap-2 bg-violet-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to preview | Click to view full details
                </p>
              </div>

              <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
                <ResponsiveContainer>
                  <RadialBarChart
                    innerRadius="10%"
                    outerRadius="90%"
                    data={dataToRender!.slice(0, 8).map((item, idx) => ({
                      ...item,
                      fill: MODERN_COLORS[idx % MODERN_COLORS.length]
                    }))}
                    startAngle={180}
                    endAngle={0}
                    style={{ outline: 'none' }}
                  >
                    <RadialBar
                      label={{ position: 'insideStart', fill: '#fff', fontSize: 11 }}
                      dataKey={(() => {
                        // Find the first numeric field that actually exists in this data
                        const dataSample = dataToRender![0];
                        return numericFields.find(f => dataSample && typeof dataSample[f as keyof ChartData] === 'number') || numericFields[0];
                      })()}
                      onClick={(data) => {
                        const chartData = data as unknown as ChartData;
                        handleChartClick(chartData);
                      }}
                    />
                    <Legend
                      iconSize={10}
                      layout="vertical"
                      verticalAlign="middle"
                      align="right"
                      wrapperStyle={{ fontSize: '11px' }}
                      formatter={(value, entry: any) => {
                        const name = entry.payload?.name || value;
                        return formatFieldName(String(name));
                      }}
                    />
                    <Tooltip content={<HoverTooltip />} />
                  </RadialBarChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}

        {/* Composed Chart (mixed types) */}
        {((composedData?.length ?? 0) > 0 || (barData?.length ?? 0) > 0) && wantsComposed && (() => {
          const dataToRender = (composedData?.length ?? 0) > 0 ? composedData : barData;
          const validFields = numericFields.filter(f => dataToRender![0] && typeof dataToRender![0][f as keyof ChartData] === 'number');
          if (validFields.length < 1) return null;

          return (
            <div className="bg-gradient-to-br from-white via-cyan-50 to-blue-50 p-8 rounded-2xl border-2 border-cyan-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-cyan-600 via-blue-600 to-cyan-500">Combined Analysis (Mixed Chart)</h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">Multiple visualization types in one view</p>
                <p className="text-xs text-cyan-600 mt-3 flex items-center gap-2 bg-cyan-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to preview | Click to view full details
                </p>
              </div>

              <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
                <ResponsiveContainer>
                  <ComposedChart data={dataToRender} margin={{ top: 10, right: 10, bottom: 100, left: 10 }} style={{ outline: 'none' }}>
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
                      cursor={{ fill: 'rgba(6, 182, 212, 0.1)' }}
                      wrapperStyle={{ pointerEvents: 'none' }}
                    />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />

                    {/* First metric as bars */}
                    <Bar
                      dataKey={validFields[0]}
                      name={formatFieldName(validFields[0])}
                      fill={MODERN_COLORS[0]}
                      radius={[8, 8, 0, 0]}
                      barSize={36}
                      onClick={(data) => {
                        const chartData = data as unknown as ChartData;
                        handleChartClick(chartData);
                      }}
                    />

                    {/* Second metric as line */}
                    {validFields[1] && (
                      <Line
                        type="monotone"
                        dataKey={validFields[1]}
                        name={formatFieldName(validFields[1])}
                        stroke={MODERN_COLORS[1]}
                        strokeWidth={2}
                        dot={{ r: 4 }}
                        onClick={(data) => {
                          const chartData = data as unknown as ChartData;
                          handleChartClick(chartData);
                        }}
                      />
                    )}

                    {/* Third metric as area (if exists) */}
                    {validFields[2] && (
                      <Area
                        type="monotone"
                        dataKey={validFields[2]}
                        name={formatFieldName(validFields[2])}
                        fill={MODERN_COLORS[2]}
                        stroke={MODERN_COLORS[2]}
                        fillOpacity={0.3}
                        onClick={(data) => {
                          const chartData = data as unknown as ChartData;
                          handleChartClick(chartData);
                        }}
                      />
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()
        }

        {/* Funnel Chart (conversion analysis) */}
        {((funnelData?.length ?? 0) > 0 || (barData?.length ?? 0) > 0) && wantsFunnel && (() => {
          const dataToRender = (funnelData?.length ?? 0) > 0 ? funnelData : barData;
          return (
            <div className="bg-gradient-to-br from-white via-orange-50 to-red-50 p-8 rounded-2xl border-2 border-orange-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-orange-600 via-red-600 to-orange-500">Conversion Funnel</h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">Step-by-step conversion analysis</p>
                <p className="text-xs text-orange-600 mt-3 flex items-center gap-2 bg-orange-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to preview | Click to view full details
                </p>
              </div>

              <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
                <ResponsiveContainer>
                  <FunnelChart style={{ outline: 'none' }} margin={{ top: 20, bottom: 20, left: 20, right: 200 }}>
                    <Tooltip content={<HoverTooltip />} />
                    <Funnel
                      dataKey="value"
                      nameKey="name"
                      data={dataToRender}
                      isAnimationActive
                      onClick={(data) => {
                        const chartData = data as unknown as ChartData;
                        handleChartClick(chartData);
                      }}
                    >
                      <LabelList
                        position="right"
                        fill="#374151"
                        stroke="none"
                        dataKey="name"
                        content={(props) => {
                          const { x, y, width, height, value } = props;
                          // If value is missing/empty, don't render
                          if (!value) return null;

                          // Position strictly outside to the right of the funnel shape
                          const labelX = Number(x) + Number(width) + 15;

                          return (
                            <text
                              x={labelX}
                              y={Number(y) + Number(height) / 2}
                              fill="#374151"
                              textAnchor="start"
                              dominantBaseline="middle"
                              style={{ fontSize: '11px', fontWeight: 600 }}
                            >
                              {String(value).length > 30 ? String(value).substring(0, 28) + '...' : String(value)}
                            </text>
                          );
                        }}
                      />
                      {dataToRender!.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={MODERN_COLORS[index % MODERN_COLORS.length]} />
                      ))}
                    </Funnel>
                  </FunnelChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}

        {/* Treemap Chart (hierarchical data) */}
        {((treemapData?.length ?? 0) > 0 || (barData?.length ?? 0) > 0) && wantsTreemap && (() => {
          const meta = getChartMetadata('treemap');
          const dataToRender = (treemapData?.length ?? 0) > 0 ? treemapData : barData;
          return (
            <div className="bg-gradient-to-br from-white via-rose-50 to-pink-50 p-8 rounded-2xl border-2 border-rose-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-rose-600 via-pink-600 to-rose-500">
                  {meta?.title || 'Hierarchical View (Treemap)'}
                </h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">
                  {meta?.description || 'Proportional data visualization showing relative sizes'}
                </p>
                <p className="text-xs text-rose-600 mt-3 flex items-center gap-2 bg-rose-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to preview | Click to view full details
                </p>
              </div>

              <div
                style={{ width: '100%', height: 550 }}
                className="bg-white rounded-xl p-4 shadow-inner"
                onClick={(e) => e.currentTarget.style.outline = 'none'}
              >
                <ResponsiveContainer>
                  <Treemap
                    data={dataToRender!.slice(0, 12).map((item, idx) => ({
                      ...item,
                      size: typeof item[numericFields[0]] === 'number' ? item[numericFields[0]] : (typeof item.value === 'number' ? item.value : 0),
                      fill: MODERN_COLORS[idx % MODERN_COLORS.length]
                    }))}
                    dataKey="size"
                    aspectRatio={4 / 3}
                    stroke="#ffffff"
                    onClick={(data) => {
                      const chartData = data as unknown as ChartData;
                      handleChartClick(chartData);
                    }}
                    content={({ x, y, width, height, name, value, fill }) => {
                      if (!name || width < 50 || height < 30) return <></>;
                      const textColor = fill ? getTextColor(fill) : '#1f2937';
                      const fontSize = Math.min(14, Math.max(11, width / 12));
                      const valueFontSize = Math.min(12, Math.max(10, width / 15));

                      // Truncate long names to fit
                      const displayName = String(name).length > 20
                        ? String(name).substring(0, 18) + '...'
                        : String(name);

                      return (
                        <g>
                          {/* Background overlay for better text readability */}
                          <rect
                            x={x}
                            y={y}
                            width={width}
                            height={height}
                            fill={fill || '#6366f1'}
                            opacity={0.95}
                          />
                          {/* Semi-transparent overlay for text area if needed */}
                          {height > 50 && (
                            <rect
                              x={x}
                              y={y + height / 2 - 15}
                              width={width}
                              height={30}
                              fill={textColor === '#ffffff' ? 'rgba(0,0,0,0.2)' : 'rgba(255,255,255,0.3)'}
                              opacity={0.6}
                            />
                          )}
                          {/* Name text with better visibility */}
                          <text
                            x={x + width / 2}
                            y={y + height / 2 - 8}
                            textAnchor="middle"
                            fill={textColor}
                            fontSize={fontSize}
                            fontWeight="bold"
                            dominantBaseline="middle"
                          >
                            <tspan
                              x={x + width / 2}
                              dy="0"
                              fill={textColor}
                              stroke={textColor === '#ffffff' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)'}
                              strokeWidth={textColor === '#ffffff' ? '0.5px' : '0.3px'}
                              strokeLinejoin="round"
                            >
                              {formatFieldName(displayName)}
                            </tspan>
                          </text>
                          {/* Value text with better visibility */}
                          <text
                            x={x + width / 2}
                            y={y + height / 2 + 12}
                            textAnchor="middle"
                            fill={textColor}
                            fontSize={valueFontSize}
                            fontWeight="600"
                            dominantBaseline="middle"
                          >
                            <tspan
                              x={x + width / 2}
                              dy="0"
                              fill={textColor}
                              stroke={textColor === '#ffffff' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)'}
                              strokeWidth={textColor === '#ffffff' ? '0.5px' : '0.3px'}
                              strokeLinejoin="round"
                            >
                              {typeof value === 'number' ? value.toLocaleString() : String(value)}
                            </tspan>
                          </text>
                        </g>
                      );
                    }}
                  />
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}
        {/* Sankey Chart (Flow) */}
        {(sankeyData || (barData?.length ?? 0) > 0) && wantsSankey && (() => {
          // Sankey data is usually one object { nodes: [], links: [] } inside barData[0] or passed via special prop.
          // Since we unwrapped array in DataVisualization, if header was single object, barData[0] might be it.
          // Or if user provided array of objects (unlikely for sankey)


          let validData;
          if (sankeyData) {
            validData = sankeyData;
          } else if (barData && barData.length > 0) {
            validData = barData[0] as unknown as { nodes: any[], links: any[] };
          }

          if (!validData) return null;
          const { nodes, links } = validData;
          const validSankey = Array.isArray(nodes) && Array.isArray(links);

          if (!validSankey) return null;

          const meta = getChartMetadata('sankey');
          return (
            <div className="bg-gradient-to-br from-white via-teal-50 to-green-50 p-8 rounded-2xl border-2 border-teal-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-teal-600 via-green-600 to-teal-500">
                  {meta?.title || 'Flow Analysis (Sankey)'}
                </h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">{meta?.description || 'Data flow and volume distribution'}</p>
                <p className="text-xs text-teal-600 mt-3 flex items-center gap-2 bg-teal-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to view flow volumes
                </p>
              </div>
              <div style={{ width: '100%', height: 500 }}>
                <ResponsiveContainer>
                  <Sankey
                    data={validData}
                    node={{ stroke: '#11867e', strokeWidth: 0, fill: '#14b8a6', width: 10 }}
                    link={{ stroke: '#2db7ae', strokeOpacity: 0.3 }}
                  >
                    <Tooltip content={<HoverTooltip />} />
                  </Sankey>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}

        {(scatterData?.length ?? 0) > 0 && wantsHeatmap && (() => {
          const meta = getChartMetadata('heatmap');
          // For heatmap, we treat Y as standard numeric if parsed, or category
          // Data: x: vendor, y: value
          return (
            <div className="bg-gradient-to-br from-white via-orange-50 to-amber-50 p-8 rounded-2xl border-2 border-orange-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-orange-600 via-amber-600 to-orange-500">
                  {meta?.title || 'Density Analysis (Heatmap)'}
                </h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">{meta?.description || 'Data concentration and patterns'}</p>
                <p className="text-xs text-orange-600 mt-3 flex items-center gap-2 bg-orange-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to view details
                </p>
              </div>
              <div style={{ width: '100%', height: 500 }}>
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 20, right: 30, bottom: 60, left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                    <XAxis
                      dataKey="x"
                      type="category"
                      name={meta?.data_source?.group_by || "Category"}
                      angle={-35}
                      textAnchor="end"
                      height={60}
                      interval={0}
                      tick={{ fontSize: 10 }}
                    />
                    <YAxis
                      dataKey="y"
                      type="number"
                      name={meta?.data_source?.aggregate?.field || "Value"}
                      domain={['auto', 'auto']}
                    />
                    <ZAxis range={[150, 150]} />
                    <Tooltip content={<HoverTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                    <Legend />
                    <Scatter name={meta?.title || "Value"} data={scatterData} fill="#f97316" shape="square" />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}

        {/* Candlestick Chart */}
        {/* Candlestick Chart */}
        {wantsCandlestick && ((candleData?.length ?? 0) > 0) && (() => {
          // Pre-process candlestick data
          const processedCandles = candleData!.map(d => {
            const item = d as any;

            // Safer Property Access: Check lowercase keys specifically
            const getVal = (keys: string[]) => {
              for (const k of keys) {
                if (item[k] !== undefined && item[k] !== null) return Number(item[k]);
              }
              return undefined;
            };

            const open = getVal(['open', 'Open', 'o', 'OPEN']) ?? 0;
            const close = getVal(['close', 'Close', 'c', 'CLOSE']) ?? 0;
            const high = getVal(['high', 'High', 'h', 'HIGH']) ?? Math.max(open, close);
            const low = getVal(['low', 'Low', 'l', 'LOW']) ?? Math.min(open, close);

            const o = Number(open);
            const c = Number(close);
            const h = Number(high);
            const l = Number(low);

            return {
              name: d.name,
              open: o,
              close: c,
              high: h,
              low: l,
              wick: [l, h],
              body: [Math.min(o, c), Math.max(o, c)],
              color: c >= o ? '#10b981' : '#f43f5e'
            };
          });

          const meta = getChartMetadata('candlestick');
          return (
            <div className="bg-gradient-to-br from-white via-slate-50 to-gray-50 p-8 rounded-2xl border-2 border-slate-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-slate-600 via-gray-600 to-slate-500">
                  {meta?.title || 'Market Trends (Candlestick)'}
                </h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">{meta?.description || 'OHLC Financial Data'}</p>
              </div>
              <div style={{ width: '100%', height: 500 }}>
                <ResponsiveContainer>
                  <BarChart data={processedCandles}>
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
                      domain={['auto', 'auto']}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#9ca3af', fontSize: 11 }}
                    />
                    <Tooltip content={<HoverTooltip />} cursor={{ fill: 'rgba(100, 116, 139, 0.1)' }} />
                    <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px', fontSize: '12px', fontWeight: '500' }} formatter={(value) => formatFieldName(value)} />

                    {/* Wick: rendered as a thin bar from low to high */}
                    <Bar dataKey="wick" name="Range" barSize={4} fill="#475569" />
                    <Bar
                      dataKey="body"
                      name="Open-Close"
                      barSize={24}
                      shape={(props: any) => {
                        const { x, y, width, height, payload } = props;
                        // Ensure height is not zero to be visible (Doji handling)
                        const safeHeight = height <= 1 ? 2 : height;
                        return <Rectangle x={x} y={y} width={width} height={safeHeight} fill={payload.color} radius={[2, 2, 2, 2]} />;
                      }}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          );
        })()}
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
