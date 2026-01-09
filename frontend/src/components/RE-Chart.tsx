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
  Treemap
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
}

interface DashboardChartsProps {
  pieData: ChartData[];
  barData: ChartData[];
  lineData?: ChartData[];
  areaData?: ChartData[];
  scatterData?: ChartData[];
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
  lineData,
  areaData,
  scatterData,
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
  const wantsBar = hasConfig ? requested.some(t => t.includes('bar') && !t.includes('radial') && !t.includes('stack')) : true; // exclude radial/stack from bar check? naive check
  const wantsLine = requested.some(t => t.includes('line'));
  const wantsArea = requested.some(t => t.includes('area'));
  const wantsScatter = requested.some(t => t.includes('scatter'));
  const wantsRadar = requested.some(t => t.includes('radar'));
  const wantsRadialBar = requested.some(t => t.includes('radial'));
  const wantsComposed = requested.some(t => t.includes('composed') || t.includes('mixed'));
  const wantsFunnel = requested.some(t => t.includes('funnel'));
  const wantsTreemap = requested.some(t => t.includes('tree') || t.includes('treemap'));

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
      treemap: wantsTreemap
    }
  });

  return (
    <>
      <div className="space-y-8">

        {/* Pie Chart */}
        {pieData?.length > 0 && wantsPie && (() => {
          const meta = getChartMetadata('pie');
          return (
            <div className="bg-gradient-to-br from-white via-indigo-50 to-purple-50 p-8 rounded-2xl border-2 border-indigo-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-500">
                  {meta?.title || 'Distribution Analysis'}
                </h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">
                  {meta?.description || (pieData && pieData.length > 0 && pieData[0]._categoryField && pieData[0]._valueField
                    ? `${formatFieldName(pieData[0]._categoryField)} by ${formatFieldName(pieData[0]._valueField)}`
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
                      data={pieData}
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
          );
        })()}

        {/* Bar Chart */}
        {barData?.length > 0 && wantsBar && (() => {
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
                        onMouseEnter={(_data, _index, e) => {
                          if (e?.target) {
                            (e.target as SVGElement).style.opacity = '0.8';
                          }
                        }}
                        onMouseLeave={(_data, _index, e) => {
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
          );
        })()}

        {/* Line Chart (user-requested) */}
        {wantsLine && (lineData?.length > 0 || barData?.length > 0) && (
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
                <LineChart data={(lineData && lineData.length > 0) ? lineData : barData} margin={{ top: 10, right: 10, bottom: 100, left: 10 }} style={{ outline: 'none' }}>
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
        {wantsArea && (areaData?.length > 0 || barData?.length > 0) && (
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
                <AreaChart data={(areaData && areaData.length > 0) ? areaData : barData} margin={{ top: 10, right: 10, bottom: 40, left: 10 }} style={{ outline: 'none' }}>
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

        {/* Scatter Plot (relationship analysis) */}
        {wantsScatter && (scatterData?.length > 0 || barData?.length > 0) && (() => {
          const meta = getChartMetadata('scatter');
          // Get x_axis and y_axis from metadata or fall back to numericFields
          const xAxisField = meta?.data_source?.x_axis || (numericFields.length >= 1 ? numericFields[0] : 'name');
          const yAxisField = meta?.data_source?.y_axis || (numericFields.length >= 2 ? numericFields[1] : numericFields[0] || 'value');
          const hasNumericAxes = numericFields.length >= 2 || (meta?.data_source?.x_axis && meta?.data_source?.y_axis);

          return (
            <div className="bg-gradient-to-br from-white via-amber-50 to-orange-50 p-8 rounded-2xl border-2 border-amber-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <div className="mb-6">
                <h4 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-amber-600 via-orange-600 to-amber-500">
                  {meta?.title || 'Relationship Analysis (Scatter)'}
                </h4>
                <p className="text-sm text-gray-700 mt-2 font-medium">
                  {meta?.description || `Viewing top ${Math.min(10, rowCount)} entries`}
                </p>
                <p className="text-xs text-amber-600 mt-3 flex items-center gap-2 bg-amber-50 px-3 py-1.5 rounded-full w-fit">
                  <span className="text-base">👆</span> Hover to preview | Click to view full details
                </p>
              </div>

              <div style={{ width: '100%', height: 500 }} onClick={(e) => e.currentTarget.style.outline = 'none'}>
                <ResponsiveContainer>
                  <ScatterChart margin={{ top: 10, right: 10, bottom: 40, left: 10 }} style={{ outline: 'none' }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                    <XAxis
                      type={hasNumericAxes ? "number" : "category"}
                      dataKey={xAxisField}
                      name={formatFieldName(xAxisField)}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#9ca3af', fontSize: 10 }}
                      height={60}
                      label={hasNumericAxes ? { value: formatFieldName(xAxisField), position: 'insideBottom', offset: -10 } : undefined}
                    />
                    <YAxis
                      type="number"
                      dataKey={yAxisField}
                      name={formatFieldName(yAxisField)}
                      axisLine={false}
                      tickLine={false}
                      tick={{ fill: '#9ca3af', fontSize: 11 }}
                      label={{ value: formatFieldName(yAxisField), angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip
                      cursor={{ stroke: 'rgba(245, 158, 11, 0.4)', strokeWidth: 2 }}
                      wrapperStyle={{ pointerEvents: 'none' }}
                      allowEscapeViewBox={{ x: true, y: true }}
                      content={<HoverTooltip />}
                    />

                    <Scatter
                      data={(scatterData && scatterData.length > 0) ? scatterData : barData}
                      fill={MODERN_COLORS[0]}
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
        {barData?.length > 0 && wantsRadar && numericFields.length >= 2 && (() => {
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
                  <RadarChart data={barData.slice(0, 8)} style={{ outline: 'none' }}>
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

                    {numericFields.slice(0, 5).map((field, idx) => (
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
        {barData?.length > 0 && wantsRadialBar && (() => {
          const meta = getChartMetadata('radialbar');
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
                    data={barData.slice(0, 8).map((item, idx) => ({
                      ...item,
                      fill: MODERN_COLORS[idx % MODERN_COLORS.length]
                    }))}
                    startAngle={180}
                    endAngle={0}
                    style={{ outline: 'none' }}
                  >
                    <RadialBar
                      label={{ position: 'insideStart', fill: '#fff', fontSize: 11 }}
                      dataKey={numericFields[0]}
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
        {barData?.length > 0 && wantsComposed && numericFields.length >= 2 && (
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
                <ComposedChart data={barData} margin={{ top: 10, right: 10, bottom: 100, left: 10 }} style={{ outline: 'none' }}>
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
                    dataKey={numericFields[0]}
                    name={formatFieldName(numericFields[0])}
                    fill={MODERN_COLORS[0]}
                    radius={[8, 8, 0, 0]}
                    barSize={36}
                    onClick={(data) => {
                      const chartData = data as unknown as ChartData;
                      handleChartClick(chartData);
                    }}
                  />

                  {/* Second metric as line */}
                  {numericFields[1] && (
                    <Line
                      type="monotone"
                      dataKey={numericFields[1]}
                      name={formatFieldName(numericFields[1])}
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
                  {numericFields[2] && (
                    <Area
                      type="monotone"
                      dataKey={numericFields[2]}
                      name={formatFieldName(numericFields[2])}
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
        )}

        {/* Funnel Chart (conversion analysis) */}
        {barData?.length > 0 && wantsFunnel && (
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
                <FunnelChart style={{ outline: 'none' }}>
                  <Tooltip content={<HoverTooltip />} />
                  <Funnel
                    dataKey={numericFields[0]}
                    data={barData.slice(0, 6)}
                    isAnimationActive
                    onClick={(data) => {
                      const chartData = data as unknown as ChartData;
                      handleChartClick(chartData);
                    }}
                  >
                    <LabelList
                      position="right"
                      fill="#000"
                      stroke="none"
                      dataKey="name"
                      formatter={(value: any) => value ? formatFieldName(String(value)) : ''}
                    />
                    {barData.slice(0, 6).map((_, index) => (
                      <Cell key={`cell-${index}`} fill={MODERN_COLORS[index % MODERN_COLORS.length]} />
                    ))}
                  </Funnel>
                </FunnelChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Treemap Chart (hierarchical data) */}
        {barData?.length > 0 && wantsTreemap && (() => {
          const meta = getChartMetadata('treemap');
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
                    data={barData.slice(0, 12).map((item, idx) => ({
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
