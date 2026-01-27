import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DashboardCharts from './RE-Chart';

interface VisualizationChart {
  id: string;
  type: string;
  title: string;
  description: string;
  data?: Array<Record<string, unknown>>; // LLM-generated chart data array
  data_source?: {
    group_by?: string;
    // Can be either a simple field name or an object with field + function
    aggregate?: string | {
      field?: string;
      function?: string;
    };
    x_axis?: string;
    y_axis?: string;
    // For table-type charts
    select?: string[];
  };
  config?: Record<string, unknown>;
}

interface VisualizationConfig {
  charts?: VisualizationChart[];
  insights?: string;
  recommended_view?: string;
}

interface DataVisualizationProps {
  data: unknown;
  title?: string;
  visualization_config?: VisualizationConfig;
}

// Helper to check if a field is an identifier (should not be used for grouping)
function isIdentifierField(fieldName: string): boolean {
  const identifierKeywords = ['number', 'id', 'uuid', 'code', 'ref', 'reference'];
  const fieldLower = fieldName.toLowerCase();
  return identifierKeywords.some(keyword => fieldLower.includes(keyword));
}

// Helper to check if a field is a good grouping field
function isGoodGroupingField(fieldName: string): boolean {
  const goodKeywords = ['name', 'category', 'type', 'status', 'group', 'class'];
  const fieldLower = fieldName.toLowerCase();
  return goodKeywords.some(keyword => fieldLower.includes(keyword)) && !isIdentifierField(fieldName);
}

// Helper to find best categorical field for grouping
function findBestCategoricalField(categoricalFields: string[]): string | null {
  // Priority 1: vendor_name or supplier_name
  for (const field of categoricalFields) {
    const fieldLower = field.toLowerCase();
    if ((fieldLower.includes('vendor') || fieldLower.includes('supplier')) && fieldLower.includes('name')) {
      return field;
    }
  }

  // Priority 2: Other name/category fields (not identifiers)
  for (const field of categoricalFields) {
    if (isGoodGroupingField(field)) {
      return field;
    }
  }

  // Priority 3: First non-identifier field
  for (const field of categoricalFields) {
    if (!isIdentifierField(field)) {
      return field;
    }
  }

  return null;
}

// Helper to extract numeric fields from data
function extractNumericFields(data: Record<string, unknown>[]): string[] {
  if (!data || data.length === 0) return [];

  const firstRow = data[0];
  const numericFields: string[] = [];

  // Keywords that indicate identifier fields (should be treated as strings)
  const identifierKeywords = ['number', 'id', 'uuid', 'code', 'ref', 'reference'];

  for (const [key, value] of Object.entries(firstRow)) {
    // Extract actual value from JSONB wrapper if present
    const actualValue = (typeof value === 'object' && value !== null && 'value' in value)
      ? (value as Record<string, unknown>).value
      : value;

    const keyLower = key.toLowerCase();

    // Check if this field is an identifier (should be treated as string/categorical)
    const isIdentifier = identifierKeywords.some(keyword => keyLower.includes(keyword));

    // Only treat as numeric if:
    // 1. It's actually numeric
    // 2. AND it's NOT an identifier field
    const isNumericValue = typeof actualValue === 'number' ||
      (typeof actualValue === 'string' && !isNaN(parseFloat(actualValue)) && isFinite(parseFloat(actualValue)));

    if (isNumericValue && !isIdentifier) {
      numericFields.push(key);
    }
  }

  // Prioritize quantity-based fields for bar charts
  const priorityKeywords = ['quantity', 'count', 'amount', 'total', 'sum', 'qty', 'volume', 'units', 'duplicate'];

  console.log('📊 Before sorting numeric fields:', numericFields);

  numericFields.sort((a, b) => {
    const aLower = a.toLowerCase();
    const bLower = b.toLowerCase();

    // Check if fields are quantity-based (highest priority)
    const aHasPriority = priorityKeywords.some(keyword => aLower.includes(keyword));
    const bHasPriority = priorityKeywords.some(keyword => bLower.includes(keyword));

    // Quantity fields come first
    if (aHasPriority && !bHasPriority) return -1;
    if (!aHasPriority && bHasPriority) return 1;

    // Otherwise maintain original order
    return 0;
  });

  console.log('📊 After sorting numeric fields:', numericFields);

  return numericFields;
}

// Helper to extract categorical fields (non-numeric, includes identifiers)
function extractCategoricalFields(data: Record<string, unknown>[]): string[] {
  if (!data || data.length === 0) return [];

  const firstRow = data[0];
  const categoricalFields: string[] = [];
  const identifierKeywords = ['number', 'id', 'uuid', 'code', 'ref', 'reference'];

  for (const [key, value] of Object.entries(firstRow)) {
    // Extract actual value from JSONB wrapper if present
    const actualValue = (typeof value === 'object' && value !== null && 'value' in value)
      ? (value as Record<string, unknown>).value
      : value;

    const keyLower = key.toLowerCase();

    // Include string values AND identifier fields (even if they look numeric)
    const isIdentifier = identifierKeywords.some(keyword => keyLower.includes(keyword));
    const isStringValue = typeof actualValue === 'string';

    // Check if it's a numeric string (like "93.50")
    const isNumericString = isStringValue && !isNaN(parseFloat(actualValue as string)) && isFinite(parseFloat(actualValue as string));

    // Exclude pure UUID/ID columns (internal system IDs)
    const isPureId = keyLower === 'id' || keyLower === 'uuid';

    // Include as categorical if:
    // 1. It's a string value BUT NOT a numeric string (unless it's an identifier)
    // 2. OR it's an identifier field (even if numeric)
    // 3. AND it's not a pure ID field
    if (!isPureId && ((isStringValue && !isNumericString) || isIdentifier)) {
      categoricalFields.push(key);
      console.log('🏷️ Detected categorical field:', key, '- value type:', typeof actualValue);
    }
  }

  console.log('📊 Total categorical fields found:', categoricalFields);

  return categoricalFields;
}

// Analyze data structure and prepare visualization data
function analyzeData(rawData: unknown) {
  console.log('📦 Raw data received:', rawData);

  // Handle different data formats
  let dataArray: Record<string, unknown>[] = [];
  const additionalFields: Record<string, unknown> = {};

  if (Array.isArray(rawData)) {
    dataArray = rawData as Record<string, unknown>[];
  } else if (typeof rawData === 'object' && rawData !== null) {
    const typedData = rawData as Record<string, unknown>;

    // Extract markdown/insight fields (only ai_summary)
    const insightFields = ['ai_summary'];
    insightFields.forEach(field => {
      if (typedData[field]) {
        additionalFields[field] = typedData[field];
      }
    });

    // Also check inside 'summary' object if it exists
    if (typedData.summary && typeof typedData.summary === 'object') {
      const summaryObj = typedData.summary as Record<string, unknown>;
      insightFields.forEach(field => {
        if (summaryObj[field]) {
          additionalFields[field] = summaryObj[field];
        }
      });
    }

    if (typedData.table_data && typeof typedData.table_data === 'object') {
      const tableData = typedData.table_data as Record<string, unknown>;
      if (Array.isArray(tableData.rows)) {
        dataArray = tableData.rows as Record<string, unknown>[];
      }
    } else if (typedData.json_data) {
      dataArray = Array.isArray(typedData.json_data)
        ? (typedData.json_data as Record<string, unknown>[])
        : [typedData.json_data as Record<string, unknown>];
    } else {
      dataArray = [typedData];
    }
  }

  if (dataArray.length === 0) return null;

  console.log('🗃️ Extracted dataArray:', dataArray);
  console.log('🔑 First row keys:', Object.keys(dataArray[0]));
  console.log('📊 First row data:', dataArray[0]);

  // Extract field types
  const numericFields = extractNumericFields(dataArray);
  const categoricalFields = extractCategoricalFields(dataArray);

  return {
    dataArray,
    numericFields,
    categoricalFields,
    rowCount: dataArray.length,
    additionalFields
  };
}

export function DataVisualization({ data, title, visualization_config }: DataVisualizationProps) {
  const analysis = useMemo(() => {
    const result = analyzeData(data);
    if (result) {
      console.log('🔍 Analysis Result:');
      console.log('  - Numeric fields:', result.numericFields);
      console.log('  - Categorical fields:', result.categoricalFields);
    }
    return result;
  }, [data]);

  // Check if we should use visualization_config
  const useConfigVisualization = visualization_config && visualization_config.charts && visualization_config.charts.length > 0;

  if (useConfigVisualization) {
    console.log('🎨 Using LLM-generated visualization config:', visualization_config);
  }

  // Generate chart data from visualization_config if available
  const configChartData = useMemo(() => {
    if (!useConfigVisualization || !analysis) return null;

    const { dataArray } = analysis;
    const pieData: Array<{ name: string; value: number; details: Record<string, unknown>[]; _categoryField?: string; _valueField?: string }> = [];
    const barData: Array<{ name: string;[key: string]: string | number | Record<string, unknown>[] | undefined; details: Record<string, unknown>[] }> = [];
    const lineData: typeof barData = [];
    const areaData: typeof barData = [];
    const scatterData: typeof barData = [];
    const waterfallData: typeof barData = [];
    const candleData: typeof barData = [];

    const stackedData: typeof barData = [];
    const radarData: typeof barData = [];
    const treemapData: typeof barData = [];
    const funnelData: typeof barData = [];
    const radialData: typeof barData = [];
    const composedData: typeof barData = [];
    // Sankey needs special handling (single object usually)
    let sankeyData: { nodes: any[], links: any[] } | undefined = undefined;

    visualization_config!.charts!.forEach((chart, index) => {
      // PRIORITY 1: Use LLM-generated data if available
      if (chart.data && (Array.isArray(chart.data) || typeof chart.data === 'object')) {
        const rawData = Array.isArray(chart.data) ? chart.data : [chart.data];
        if (rawData.length > 0) {
          console.log(`📊 Processing LLM-generated data for Chart ${index + 1}: ${chart.type} (${chart.title || 'Untitled'})`);
        }

        // Convert LLM data to our format
        const processedData = rawData.map((item: Record<string, unknown>) => {
          // 1. Identify Name/Category
          const name = String(item.name || item[Object.keys(item)[0]] || 'Unknown');

          // 2. Base Item
          const baseItem: any = { // Use 'any' to allow flexible property assignment
            name,
            details: [] // LLM data implies summarized data, so no drill-down details usually
          };

          // 3. Copy ALL properties (Preserve open, close, x, y, z, value, total, etc.)
          Object.entries(item).forEach(([key, val]) => {
            if (key !== 'name' && key !== 'details') {
              baseItem[key] = val;
            }
          });

          // 4. Ensure 'value' exists for charts that strictly need it (Pie/Treemap), if not present
          if (baseItem.value === undefined && typeof item.value === 'number') {
            baseItem.value = item.value;
          }

          // 5. Auto-convert specific numeric-looking strings to numbers (fixes "y": "4" issues)
          ['y', 'value', 'total', 'count', 'score', 'amount'].forEach(numKey => {
            if (typeof baseItem[numKey] === 'string' && !isNaN(Number(baseItem[numKey]))) {
              baseItem[numKey] = Number(baseItem[numKey]);
            }
          });

          return baseItem;
        });

        // 5. Assign STRICTLY to the correct dataset based on chart type
        const cType = chart.type.toLowerCase();

        if (cType.includes('pie')) {
          pieData.push(...processedData);
        } else if (cType.includes('line')) {
          lineData.push(...processedData);
        } else if (cType.includes('area')) {
          areaData.push(...processedData);
        } else if (cType.includes('scatter') || cType.includes('bubble') || cType.includes('heatmap')) {
          scatterData.push(...processedData);
        } else if (cType.includes('candle')) {
          candleData.push(...processedData);
        } else if (cType.includes('waterfall')) {
          // Waterfall Logic: Handle tuples vs deltas
          let accum = 0;
          const finalWaterfallData = processedData.map((item: any) => {
            // If value is already a tuple [start, end], use it directly
            if (Array.isArray(item.value) && item.value.length === 2) {
              return item;
            }
            // Otherwise, assume it's a delta and calculate running total
            const val = Number(item.value || 0);
            const start = accum;
            accum += val;
            return { ...item, value: [start, accum] };
          });
          waterfallData.push(...finalWaterfallData);
        } else if (cType.includes('stacked')) {
          stackedData.push(...processedData);
        } else if (cType.includes('radar')) {
          radarData.push(...processedData);
        } else if (cType.includes('tree')) { // treemap
          treemapData.push(...processedData);
        } else if (cType.includes('funnel')) {
          funnelData.push(...processedData);
        } else if (cType.includes('radial')) { // radialbar, radial_bar
          radialData.push(...processedData);
        } else if (cType.includes('composed') || cType.includes('mixed')) {
          composedData.push(...processedData);
        } else if (cType.includes('sankey')) {
          // Special case: Sankey data is usually a single object { nodes, links }
          const cData = chart.data as any;
          if (cData && !Array.isArray(cData) && cData.nodes && cData.links) {
            let nodes = [...cData.nodes];
            let links = [...cData.links];

            // Fix Self-Loops (Source == Target) which crash Recharts/Sankey
            // Determine if indices or names are used (Recharts uses indices)
            // Assuming indices for now based on LLM output pattern
            const hasSelfLoop = links.some(l => l.source === l.target);

            if (hasSelfLoop) {
              console.log('🔧 Fixing Sankey Self-Loops: creating bipartite graph flow');
              const initialNodeCount = nodes.length;
              // Create duplicate target nodes
              const targetNodes = nodes.map(n => ({ ...n, name: n.name + ' ' }));
              nodes = [...nodes, ...targetNodes];

              // Remap links to point to the new target nodes
              links = links.map(l => ({
                ...l,
                target: typeof l.target === 'number' ? l.target + initialNodeCount : l.target
              }));
            }

            sankeyData = { nodes, links };
          } else {
            console.warn(`⚠️ Sankey chart data is not in expected { nodes, links } format. Skipping.`);
          }
        } else if (cType.includes('bar')) {
          // ONLY for explicit bar charts
          barData.push(...processedData);
        } else {
          // Fallback for unknown types
          console.warn(`⚠️ Unknown chart type "${cType}", defaulting to Bar`);
          barData.push(...processedData);
        }

        return; // Done processing this chart, move to the next
      }

      // PRIORITY 2: Fall back to processing data_source (legacy support)
      console.log(`📊 Processing data_source for ${chart.type} chart (LLM data not provided)`);

      const { type, data_source: originalDataSource } = chart;
      if (!originalDataSource) {
        console.warn(`⚠️ Chart ${chart.id} has no data_source and no data array, skipping`);
        return;
      }
      let data_source = originalDataSource;

      // --- Normalization for diverse LLM schemas ---
      const sourceAny = data_source as any;

      // Handle Composed Chart (multiple_sources) -> Flatten first source logic
      if ((type === 'composed' || type === 'mixed') && sourceAny.multiple_sources && sourceAny.multiple_sources.length > 0) {
        data_source = { ...data_source, ...sourceAny.multiple_sources[0] };
        // Ensure aggregate is properly formatted if it's just a field string in the sub-source
        if (typeof (data_source as any).aggregate === 'string') {
          // force object format if string
        }
      }

      // Handle Radial/Treemap/RadialBar field mappings
      if (!data_source.group_by) {
        if (sourceAny.category) data_source = { ...data_source, group_by: sourceAny.category };
        else if (sourceAny.category_field) data_source = { ...data_source, group_by: sourceAny.category_field };
      }

      if (!data_source.aggregate) {
        if (sourceAny.numeric_field) data_source = { ...data_source, aggregate: { field: sourceAny.numeric_field, function: 'sum' } as any };
        else if (sourceAny.size_field) data_source = { ...data_source, aggregate: { field: sourceAny.size_field, function: 'sum' } as any };
      }

      // Handle Radar (metrics array)
      if (type === 'radar' && sourceAny.metrics && !data_source.aggregate) {
        // Use first metric for aggregation, default group_by to vendor if missing
        data_source = {
          ...data_source,
          aggregate: { field: sourceAny.metrics[0], function: 'sum' } as any,
          group_by: data_source.group_by || findBestCategoricalField(analysis.categoricalFields) || 'vendor_name'
        };
      }

      // Handle Funnel Explicit Data (Stages/Values)
      if (type === 'funnel' && sourceAny.stages && sourceAny.values) {
        console.log('📥 Using Explicit Funnel Data');
        const stages = sourceAny.stages as string[];
        const values = sourceAny.values as number[];
        stages.forEach((stage, idx) => {
          barData.push({
            name: stage,
            value: values[idx] || 0,
            details: []
          });
        });
        return; // Skip standard processing for this chart
      }

      // Determine target array based on chart type for DATA_SOURCE fallback
      let targetArray: typeof barData;
      if (type === 'line') targetArray = lineData;
      else if (type === 'area') targetArray = areaData;
      else if (type === 'scatter' || type === 'bubble') targetArray = scatterData;
      else if (type === 'candlestick') targetArray = candleData;
      else if (type === 'waterfall') targetArray = waterfallData;
      else if (type === 'stacked_bar') targetArray = stackedData;
      else if (type === 'radar') targetArray = radarData;
      else if (type === 'treemap') targetArray = treemapData;
      else if (type === 'funnel') targetArray = funnelData;
      else if (type === 'radialbar' || type === 'radial_bar' || type === 'radial') targetArray = radialData;
      else if (type === 'composed' || type === 'mixed') targetArray = composedData;
      else targetArray = barData;

      if (data_source.group_by || data_source.aggregate) {
        // ... (existing aggregation logic) ...
        // IMPORTANT: Update standard logic to use 'targetArray' instead of determining it inside logic
      }
      // ---------------------------------------------

      console.log(`📊 Processing chart ${index + 1}/${visualization_config!.charts!.length}:`, { type, data_source });

      // Handle pie chart with group_by + aggregate
      if (type === 'pie' && data_source.group_by && data_source.aggregate) {
        // Generate pie chart data
        let groupByField = data_source.group_by;

        // Validate group_by field
        const isMultiValue = dataArray.slice(0, 10).some(row => {
          let val = row[groupByField];
          if (typeof val === 'object' && val !== null && 'value' in val) val = (val as any).value;
          return typeof val === 'string' && val.includes(',') && val.length > 20;
        });

        if (isIdentifierField(groupByField) || isMultiValue) {
          console.warn(`⚠️ Chart config uses unsuitable field "${groupByField}" (identifier or multi-value) for grouping. Finding better field...`);
          const betterField = findBestCategoricalField(analysis.categoricalFields);
          if (betterField && betterField !== groupByField) {
            console.log(`✅ Replaced "${groupByField}" with "${betterField}" for grouping`);
            groupByField = betterField;
          } else {
            console.warn(`⚠️ No better field found, proceeding with "${groupByField}"`);
            // Don't skip - allow chart to render with identifier field
          }
        }

        const aggregateDef = data_source.aggregate as unknown;
        let aggregateField: string | undefined;
        let aggregateFunc = 'sum';

        if (typeof aggregateDef === 'string') {
          // Simple form: aggregate: "fieldName"
          aggregateField = aggregateDef;
        } else if (aggregateDef && typeof aggregateDef === 'object') {
          const aggObj = aggregateDef as { field?: string; function?: string };
          aggregateField = aggObj.field;
          if (aggObj.function) {
            aggregateFunc = aggObj.function;
          }
        }

        if (!aggregateField) {
          console.warn('⚠️ visualization_config pie chart missing valid aggregate field, skipping:', chart);
          return;
        }

        const aggregated: Record<string, { total: number; rows: Record<string, unknown>[] }> = {};

        dataArray.forEach(row => {
          const categoryValue = row[groupByField];
          let category = 'Unknown';

          // Extract value from JSONB wrapper if present
          if (typeof categoryValue === 'object' && categoryValue !== null && 'value' in categoryValue) {
            const extracted = (categoryValue as Record<string, unknown>).value;
            if (extracted !== null && extracted !== undefined && String(extracted) !== 'undefined') {
              category = String(extracted);
            }
          } else if (categoryValue !== null && categoryValue !== undefined && String(categoryValue) !== 'undefined') {
            category = String(categoryValue);
          }

          const fieldValue = row[aggregateField as string];
          const actualValue = (typeof fieldValue === 'object' && fieldValue !== null && 'value' in fieldValue)
            ? (fieldValue as Record<string, unknown>).value
            : fieldValue;
          const numValue = parseFloat(String(actualValue || 0)) || 0;

          if (!aggregated[category]) {
            aggregated[category] = { total: 0, rows: [] };
          }

          if (aggregateFunc === 'sum') {
            aggregated[category].total += numValue;
          } else if (aggregateFunc === 'count') {
            aggregated[category].total += 1;
          } else if (aggregateFunc === 'avg') {
            aggregated[category].total += numValue;
          }

          aggregated[category].rows.push(row);
        });

        // Convert to pie chart format
        Object.entries(aggregated).forEach(([name, data]) => {
          const value = aggregateFunc === 'avg' ? data.total / data.rows.length : data.total;
          pieData.push({
            name,
            value,
            details: data.rows,
            _categoryField: groupByField,
            _valueField: aggregateField
          });
        });

        // Handle bar/line/area/scatter/etc with group_by + aggregate
      } else if (
        ['bar', 'line', 'area', 'scatter', 'radar', 'radial', 'radialbar', 'radial_bar', 'funnel', 'treemap', 'composed', 'bubble', 'waterfall', 'candlestick', 'stacked_bar', 'heatmap', 'sankey'].includes(type) &&
        data_source.group_by &&
        data_source.aggregate
      ) {
        let groupByField = data_source.group_by;

        // Validate group_by field
        const isMultiValue = dataArray.slice(0, 10).some(row => {
          let val = row[groupByField];
          if (typeof val === 'object' && val !== null && 'value' in val) val = (val as any).value;
          return typeof val === 'string' && val.includes(',') && val.length > 20;
        });

        if (isIdentifierField(groupByField) || isMultiValue) {
          console.warn(`⚠️ Chart config uses unsuitable field "${groupByField}" (identifier or multi-value) for grouping. Finding better field...`);
          const betterField = findBestCategoricalField(analysis.categoricalFields);
          if (betterField && betterField !== groupByField) {
            console.log(`✅ Replaced "${groupByField}" with "${betterField}" for grouping`);
            groupByField = betterField;
          } else {
            console.warn(`⚠️ No better field found, proceeding with "${groupByField}"`);
            // Don't skip - allow chart to render
          }
        }

        const aggregateDef = data_source.aggregate as unknown;
        let aggregateField: string | undefined;
        let aggregateFunc = 'sum';

        if (typeof aggregateDef === 'string') {
          aggregateField = aggregateDef;
        } else if (aggregateDef && typeof aggregateDef === 'object') {
          const aggObj = aggregateDef as { field?: string; function?: string };
          aggregateField = aggObj.field;
          if (aggObj.function) {
            aggregateFunc = aggObj.function;
          }
        }

        if (!aggregateField) {
          console.warn('⚠️ visualization_config bar/line/area/scatter chart missing valid aggregate field, skipping:', chart);
          return;
        }

        const aggregated: Record<string, { total: number; rows: Record<string, unknown>[] }> = {};

        dataArray.forEach(row => {
          const categoryValue = row[groupByField];
          let category = 'Unknown';

          if (typeof categoryValue === 'object' && categoryValue !== null && 'value' in categoryValue) {
            const extracted = (categoryValue as Record<string, unknown>).value;
            if (extracted !== null && extracted !== undefined && String(extracted) !== 'undefined') {
              category = String(extracted);
            }
          } else if (categoryValue !== null && categoryValue !== undefined && String(categoryValue) !== 'undefined') {
            category = String(categoryValue);
          }

          const fieldValue = row[aggregateField as string];
          const actualValue = (typeof fieldValue === 'object' && fieldValue !== null && 'value' in fieldValue)
            ? (fieldValue as Record<string, unknown>).value
            : fieldValue;
          const numValue = parseFloat(String(actualValue || 0)) || 0;

          if (!aggregated[category]) {
            aggregated[category] = { total: 0, rows: [] };
          }

          if (aggregateFunc === 'sum') {
            aggregated[category].total += numValue;
          } else if (aggregateFunc === 'count') {
            aggregated[category].total += 1;
          } else if (aggregateFunc === 'avg') {
            aggregated[category].total += numValue;
          }

          aggregated[category].rows.push(row);
        });

        // Initialize accumulator for waterfall charts
        let waterfallAccumulator = 0;

        Object.entries(aggregated).forEach(([name, data]) => {
          const rawValue = aggregateFunc === 'avg' ? data.total / data.rows.length : data.total;
          let finalValue: number | [number, number] = rawValue;

          if (type === 'waterfall') {
            const prev = waterfallAccumulator;
            waterfallAccumulator += rawValue;
            finalValue = [prev, waterfallAccumulator];
            console.log(`💧 Waterfall step for ${name}: [${prev}, ${waterfallAccumulator}]`);
          }

          // Determine target array based on chart type
          let targetArray: typeof barData;
          if (type === 'line') targetArray = lineData;
          else if (type === 'area') targetArray = areaData;
          else if (type === 'scatter' || type === 'bubble') targetArray = scatterData;
          else if (type === 'candlestick') targetArray = candleData;
          else if (type === 'waterfall') targetArray = waterfallData;
          else if (type === 'stacked_bar') {
            targetArray = stackedData;
          }
          else if (type === 'radar') targetArray = radarData;
          else if (type === 'treemap') targetArray = treemapData;
          else if (type === 'funnel') targetArray = funnelData;
          else if (type === 'radial' || type === 'radialbar') targetArray = radialData;
          else if (type === 'composed') targetArray = composedData;
          else targetArray = barData;

          // Create data point with proper structure
          const dataPoint: typeof barData[0] = {
            name,
            value: finalValue as any,  // Cast to any to satisfy the complex type union
            details: data.rows,
            _categoryField: groupByField,
            _valueField: aggregateField
          } as typeof barData[0];

          // Add field name as key dynamically
          if (aggregateField) {
            (dataPoint as Record<string, unknown>)[aggregateField] = finalValue;
          }

          targetArray.push(dataPoint);
          if (type === 'stacked_bar') {
            // separated, no push to barData
          }
          console.log(`✅ Added ${type} chart data point:`, { name, value: finalValue, field: aggregateField });
        });
      } else if (
        ['bar', 'line', 'area', 'scatter', 'radar', 'radial', 'radialbar', 'radial_bar', 'funnel', 'treemap', 'composed', 'bubble', 'waterfall', 'candlestick', 'stacked_bar', 'heatmap'].includes(type) &&
        data_source.x_axis &&
        data_source.y_axis
      ) {
        console.log(`🔷 Processing ${type} chart with X/Y axes:`, data_source);
        // Generate bar/line/area/scatter chart data
        let xAxisField = data_source.x_axis;

        // Validate x_axis field
        const isMultiValue = dataArray.slice(0, 10).some(row => {
          let val = row[xAxisField];
          if (typeof val === 'object' && val !== null && 'value' in val) val = (val as any).value;
          return typeof val === 'string' && val.includes(',') && val.length > 20;
        });

        if (isIdentifierField(xAxisField) || isMultiValue) {
          console.warn(`⚠️ Chart config uses unsuitable field "${xAxisField}" (identifier or multi-value) for x-axis. Finding better field...`);
          const betterField = findBestCategoricalField(analysis.categoricalFields);
          if (betterField && betterField !== xAxisField) {
            console.log(`✅ Replaced "${xAxisField}" with "${betterField}" for x-axis`);
            xAxisField = betterField;
          } else {
            console.warn(`⚠️ No better field found, proceeding with "${xAxisField}"`);
            // Don't skip - allow chart to render
          }
        }

        const yAxisField = data_source.y_axis;
        const groupByField = data_source.group_by;

        const aggregated: Record<string, { values: Record<string, number>; rows: Record<string, unknown>[] }> = {};

        dataArray.forEach(row => {
          const xValue = row[xAxisField];
          let xLabel = 'Unknown';

          if (typeof xValue === 'object' && xValue !== null && 'value' in xValue) {
            const extracted = (xValue as Record<string, unknown>).value;
            if (extracted !== null && extracted !== undefined && String(extracted) !== 'undefined') {
              xLabel = String(extracted);
            }
          } else if (xValue !== null && xValue !== undefined && String(xValue) !== 'undefined') {
            xLabel = String(xValue);
          }

          const yValue = row[yAxisField];
          const actualYValue = (typeof yValue === 'object' && yValue !== null && 'value' in yValue)
            ? (yValue as Record<string, unknown>).value
            : yValue;
          const numYValue = parseFloat(String(actualYValue || 0)) || 0;

          if (!aggregated[xLabel]) {
            aggregated[xLabel] = { values: {}, rows: [] };
          }

          const seriesKey = groupByField ? (row[groupByField] as string || 'default') : yAxisField;
          aggregated[xLabel].values[seriesKey] = (aggregated[xLabel].values[seriesKey] || 0) + numYValue;
          aggregated[xLabel].rows.push(row);
        });

        // Convert to chart format based on type
        Object.entries(aggregated).forEach(([name, data]) => {
          // Determine target array based on chart type
          let targetArray: typeof barData;
          if (type === 'line') targetArray = lineData;
          else if (type === 'area') targetArray = areaData;
          else if (type === 'scatter' || type === 'bubble' || type === 'heatmap') targetArray = scatterData;
          else if (type === 'candlestick') targetArray = candleData;
          else if (type === 'waterfall') targetArray = waterfallData;
          else if (type === 'stacked_bar') {
            targetArray = stackedData;
          }
          else if (type === 'radar') targetArray = radarData;
          else if (type === 'treemap') targetArray = treemapData;
          else if (type === 'funnel') targetArray = funnelData;
          else if (type === 'radial' || type === 'radialbar') targetArray = radialData;
          else if (type === 'composed') targetArray = composedData;
          else targetArray = barData;

          // For scatter charts, both x and y should be numeric
          // For other charts, parse name as number if it looks like one
          const numericName = parseFloat(name);
          const xValue = !isNaN(numericName) ? numericName : name;

          // For scatter: ensure both axes are numeric
          let scatterXValue = xValue;
          let scatterYValue = 0;
          if (type === 'scatter') {
            // Try to get numeric value from x-axis field
            if (typeof xValue === 'string') {
              scatterXValue = parseFloat(xValue) || 0;
            }
            // Get y-axis value from the aggregated values
            const yValues = Object.values(data.values);
            scatterYValue = yValues.length > 0 ? (typeof yValues[0] === 'number' ? yValues[0] : parseFloat(String(yValues[0])) || 0) : 0;
          }

          const dataPoint: typeof barData[0] = {
            name,
            ...(type === 'scatter' ? {
              [xAxisField]: scatterXValue,
              [yAxisField]: scatterYValue
            } : {
              [xAxisField]: xValue,
              ...data.values
            }),
            details: data.rows
          } as typeof barData[0];

          targetArray.push(dataPoint);
          if (type === 'stacked_bar') {
            // separated
          }
          console.log(`✅ Added ${type} chart data point (x/y axes):`, {
            name,
            xAxisField,
            yAxisField,
            xValue: type === 'scatter' ? scatterXValue : xValue,
            yValue: type === 'scatter' ? scatterYValue : data.values,
            rowCount: data.rows.length
          });
        });
      }
    });



    // Helper to deduplicate data
    const deduplicateData = (data: typeof barData) => {
      const dataMap = new Map<string, typeof barData[0]>();
      data.forEach(item => {
        const existing = dataMap.get(item.name);
        if (existing) {
          if (existing.details && item.details) {
            existing.details = [...existing.details, ...item.details];
          }
          Object.keys(item).forEach(key => {
            if (key !== 'name' && key !== 'details' && typeof item[key] === 'number') {
              const existingVal = existing[key];
              const newVal = item[key];
              if (typeof existingVal === 'number' && typeof newVal === 'number') {
                existing[key] = Math.max(existingVal, newVal);
              }
            }
          });
        } else {
          dataMap.set(item.name, { ...item });
        }
      });
      return Array.from(dataMap.values());
    };

    const uniqueBarData = deduplicateData(barData);
    const uniqueLineData = deduplicateData(lineData);
    const uniqueAreaData = deduplicateData(areaData);
    const uniqueScatterData = deduplicateData(scatterData);
    const uniqueRadarData = deduplicateData(radarData);
    const uniqueTreemapData = deduplicateData(treemapData);
    const uniqueFunnelData = deduplicateData(funnelData);
    const uniqueRadialData = deduplicateData(radialData);
    const uniqueComposedData = deduplicateData(composedData);

    console.log('✅ Generated chart data from config:', {
      pieDataCount: pieData.length,
      barDataCount: uniqueBarData.length,
      lineDataCount: uniqueLineData.length,
      areaDataCount: uniqueAreaData.length,
      scatterDataCount: uniqueScatterData.length,
      sampleBar: uniqueBarData.slice(0, 1),
      sampleLine: uniqueLineData.slice(0, 1)
    });

    return {
      pieData,
      barData: uniqueBarData,
      lineData: uniqueLineData,
      areaData: uniqueAreaData,
      scatterData: uniqueScatterData,
      waterfallData,
      candleData,
      stackedData,
      radarData: uniqueRadarData,
      treemapData: uniqueTreemapData,
      funnelData: uniqueFunnelData,
      radialData: uniqueRadialData,
      composedData: uniqueComposedData,
      sankeyData
    };
  }, [useConfigVisualization, analysis, visualization_config]);

  // Requested chart types from config (normalized to lowercase)
  const requestedChartTypes = useMemo(
    () =>
      visualization_config?.charts?.map((c) => c.type.toLowerCase()) ?? [],
    [visualization_config]
  );

  // Derive numeric fields from config-based chart data (check all data arrays)
  const configNumericFields = useMemo(() => {
    if (!useConfigVisualization || !configChartData) return [];

    // Collect numeric fields from all chart data arrays
    const allDataArrays = [
      ...(configChartData.barData || []),
      ...(configChartData.pieData || []),
      ...(configChartData.lineData || []),
      ...(configChartData.areaData || []),
      ...(configChartData.scatterData || []),
      ...(configChartData.stackedData || []),
      ...(configChartData.radarData || []),
      ...(configChartData.treemapData || []),
      ...(configChartData.funnelData || []),
      ...(configChartData.radialData || []),
      ...(configChartData.composedData || []),
      ...(configChartData.waterfallData || []),
      ...(configChartData.candleData || [])
    ];

    if (allDataArrays.length === 0) return [];

    // Get all unique numeric field names from all data items
    const numericFieldsSet = new Set<string>();
    allDataArrays.forEach(item => {
      const row = item as Record<string, unknown>;
      Object.keys(row).forEach(k => {
        if (k !== 'name' && k !== 'details' && !k.startsWith('_')) {
          const val = row[k];
          if (typeof val === 'number') {
            numericFieldsSet.add(k);
          }
        }
      });
    });

    return Array.from(numericFieldsSet);
  }, [useConfigVisualization, configChartData]);

  console.log('🔢 Numeric fields comparison:', {
    originalNumericFields: analysis?.numericFields,
    configNumericFields,
    usingConfig: useConfigVisualization && configChartData
  });

  // Prepare pie chart data (aggregate by best categorical field)
  const pieData = useMemo(() => {
    if (!analysis || analysis.categoricalFields.length === 0 || analysis.numericFields.length === 0) return null;

    const { dataArray, categoricalFields, numericFields } = analysis;

    // Select best category field (ONLY use vendor_name for grouping, NOT invoice_number)
    let categoryField: string | null = null;

    console.log('🔍 Available categorical fields:', categoricalFields);

    // Priority 1: vendor_name or supplier_name (ONLY these for chart grouping)
    for (const field of categoricalFields) {
      const fieldLower = field.toLowerCase();
      if ((fieldLower.includes('vendor') || fieldLower.includes('supplier')) && fieldLower.includes('name')) {
        categoryField = field;
        console.log('✅ Selected vendor/supplier field:', field);
        break;
      }
    }

    // Priority 2: other name/description fields (NOT invoice_number/order_number)
    if (!categoryField) {
      for (const field of categoricalFields) {
        const fieldLower = field.toLowerCase();
        // Skip identifier fields (invoice_number, order_number, etc.)
        const isIdentifier = fieldLower.includes('number') || fieldLower.includes('id') ||
          fieldLower.includes('code') || fieldLower.includes('reference');
        if (!isIdentifier && (fieldLower.includes('name') || fieldLower.includes('description'))) {
          categoryField = field;
          break;
        }
      }
    }

    // Priority 3: fallback to first non-identifier categorical field
    if (!categoryField) {
      for (const field of categoricalFields) {
        const fieldLower = field.toLowerCase();
        const isIdentifier = fieldLower.includes('number') || fieldLower.includes('id') ||
          fieldLower.includes('code') || fieldLower.includes('reference');
        if (!isIdentifier) {
          categoryField = field;
          break;
        }
      }
    }

    // Fallback to first categorical field
    if (!categoryField) {
      categoryField = categoricalFields[0];
    }

    const valueField = numericFields[0];

    console.log('🥧 Pie chart using:', { categoryField, valueField });

    // Aggregate values by category AND keep track of all related rows
    const aggregated = dataArray.reduce((acc: Record<string, { total: number; rows: Record<string, unknown>[] }>, row: Record<string, unknown>) => {
      const categoryValue = row[categoryField as string];
      const numericValue = row[valueField];

      console.log('🔍 Processing row:', {
        categoryField,
        categoryValue,
        rawValue: categoryValue,
        type: typeof categoryValue,
        isObject: typeof categoryValue === 'object',
        hasValue: categoryValue && typeof categoryValue === 'object' && 'value' in categoryValue
      });

      // Extract actual values from JSONB wrapper if present
      let category = 'Unknown';

      if (typeof categoryValue === 'object' && categoryValue !== null) {
        // Handle JSONB structure like { value: "Acme Corp" }
        if ('value' in categoryValue) {
          const extracted = (categoryValue as Record<string, unknown>).value;
          if (extracted !== null && extracted !== undefined && String(extracted) !== 'undefined') {
            category = String(extracted);
          }
        }
        // Handle nested object structure
        else if (Object.keys(categoryValue).length > 0) {
          const firstValue = Object.values(categoryValue)[0];
          if (firstValue !== null && firstValue !== undefined && String(firstValue) !== 'undefined') {
            category = String(firstValue);
          }
        }
      } else if (categoryValue !== null && categoryValue !== undefined && String(categoryValue) !== 'undefined') {
        category = String(categoryValue);
      }

      console.log('📝 Final category:', category);

      const value = parseFloat(String(
        (typeof numericValue === 'object' && numericValue !== null && 'value' in numericValue)
          ? (numericValue as Record<string, unknown>).value
          : numericValue || 0
      )) || 0;

      if (!acc[category]) {
        acc[category] = { total: 0, rows: [] };
      }

      acc[category].total += value;
      acc[category].rows.push(row);
      return acc;
    }, {});

    return Object.entries(aggregated).map(([name, data]) => ({
      name,
      value: data.total,
      details: data.rows, // Include all related rows for tooltip
      _categoryField: categoryField || undefined, // Include for heading display
      _valueField: valueField // Include for heading display
    }));
  }, [analysis]);

  // Prepare bar chart data (use first few rows or aggregated data)
  const barData = useMemo(() => {
    if (!analysis || analysis.numericFields.length === 0) return null;

    const { dataArray, numericFields, categoricalFields } = analysis;

    // Filter numeric fields for bar chart: ONLY show quantity/count/amount/total fields
    // Exclude identifier fields (invoice_number, id, etc.)
    const priorityKeywords = ['quantity', 'count', 'amount', 'total', 'sum', 'qty', 'volume', 'units', 'duplicate'];
    const identifierKeywords = ['number', 'id', 'uuid', 'code'];

    const barChartFields = numericFields.filter(field => {
      const fieldLower = field.toLowerCase();
      const hasPriority = priorityKeywords.some(keyword => fieldLower.includes(keyword));
      const isIdentifier = identifierKeywords.some(keyword => fieldLower.includes(keyword));

      // Include ONLY priority fields, exclude identifiers
      return hasPriority && !isIdentifier;
    });

    // If no priority fields found, fall back to first non-identifier numeric field
    if (barChartFields.length === 0) {
      const fallbackField = numericFields.find(field => {
        const fieldLower = field.toLowerCase();
        return !identifierKeywords.some(keyword => fieldLower.includes(keyword));
      });
      if (fallbackField) barChartFields.push(fallbackField);
    }

    console.log('📊 Bar chart will display these fields:', barChartFields);

    if (barChartFields.length === 0) return null;

    // Find the label field (vendor_name or similar)
    let labelField: string | null = null;

    // Priority 1: Look for vendor_name or supplier_name
    for (const field of categoricalFields) {
      const fieldLower = field.toLowerCase();
      if ((fieldLower.includes('vendor') || fieldLower.includes('supplier')) && fieldLower.includes('name')) {
        labelField = field;
        break;
      }
    }

    // Priority 2: Look for other name/description fields (NOT identifiers)
    if (!labelField) {
      for (const field of categoricalFields) {
        const fieldLower = field.toLowerCase();
        const isIdentifier = fieldLower.includes('number') || fieldLower.includes('id') ||
          fieldLower.includes('code') || fieldLower.includes('reference');
        if (!isIdentifier && (fieldLower.includes('name') || fieldLower.includes('description'))) {
          labelField = field;
          break;
        }
      }
    }

    // Priority 3: Fallback to first non-identifier field
    if (!labelField) {
      for (const field of categoricalFields) {
        const fieldLower = field.toLowerCase();
        const isIdentifier = fieldLower.includes('number') || fieldLower.includes('id') ||
          fieldLower.includes('code') || fieldLower.includes('reference');
        if (!isIdentifier) {
          labelField = field;
          break;
        }
      }
    }

    if (!labelField) return null;

    console.log('📊 Bar chart aggregating by:', labelField);

    // Aggregate data by label field (e.g., vendor_name) AND keep all related rows
    const aggregated: Record<string, { values: Record<string, number>; rows: Record<string, unknown>[] }> = {};

    dataArray.forEach(row => {
      // Extract category name
      const categoryValue = row[labelField as string];
      let category = 'Unknown';

      if (typeof categoryValue === 'object' && categoryValue !== null) {
        if ('value' in categoryValue) {
          const extracted = (categoryValue as Record<string, unknown>).value;
          if (extracted !== null && extracted !== undefined && String(extracted) !== 'undefined') {
            category = String(extracted);
          }
        } else if (Object.keys(categoryValue).length > 0) {
          const firstValue = Object.values(categoryValue)[0];
          if (firstValue !== null && firstValue !== undefined && String(firstValue) !== 'undefined') {
            category = String(firstValue);
          }
        }
      } else if (categoryValue !== null && categoryValue !== undefined && String(categoryValue) !== 'undefined') {
        category = String(categoryValue);
      }

      // Initialize category if not exists
      if (!aggregated[category]) {
        aggregated[category] = { values: {}, rows: [] };
      }

      // Store the full row for tooltip
      aggregated[category].rows.push(row);

      // Aggregate each numeric field
      barChartFields.forEach(field => {
        const fieldValue = row[field];
        const actualValue = (typeof fieldValue === 'object' && fieldValue !== null && 'value' in fieldValue)
          ? (fieldValue as Record<string, unknown>).value
          : fieldValue;
        const numValue = parseFloat(String(actualValue || 0)) || 0;

        aggregated[category].values[field] = (aggregated[category].values[field] || 0) + numValue;
      });
    });

    // Convert to array format for chart, limit to top 10 categories
    return Object.entries(aggregated)
      .map(([name, data]) => ({
        name,
        ...data.values,
        details: data.rows // Include all related rows for tooltip
      }))
      .slice(0, 10);
  }, [analysis]);

  if (!analysis || analysis.dataArray.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No data available for visualization</p>
      </div>
    );
  }

  const { dataArray, numericFields, categoricalFields, rowCount, additionalFields } = analysis;

  return (
    <div className="space-y-8 p-6">
      {title && (
        <h3 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">{title}</h3>
      )}

      <DashboardCharts
        pieData={useConfigVisualization && configChartData ? configChartData.pieData : (pieData || [])}
        barData={useConfigVisualization && configChartData ? configChartData.barData : (barData || [])}
        lineData={useConfigVisualization && configChartData ? configChartData.lineData : []}
        areaData={useConfigVisualization && configChartData ? configChartData.areaData : []}
        scatterData={useConfigVisualization && configChartData ? configChartData.scatterData : []}
        candleData={useConfigVisualization && configChartData ? configChartData.candleData : []}
        waterfallData={configChartData ? configChartData.waterfallData : undefined}
        stackedData={configChartData ? configChartData.stackedData : undefined}
        radarData={configChartData ? configChartData.radarData : undefined}
        treemapData={configChartData ? configChartData.treemapData : undefined}
        funnelData={configChartData ? configChartData.funnelData : undefined}
        radialData={configChartData ? configChartData.radialData : undefined}
        composedData={configChartData ? configChartData.composedData : undefined}
        sankeyData={configChartData ? configChartData.sankeyData : undefined}
        categoricalFields={categoricalFields}
        numericFields={useConfigVisualization && configNumericFields.length > 0 ? configNumericFields : numericFields}
        rowCount={rowCount}
        requestedChartTypes={useConfigVisualization && visualization_config?.charts
          ? visualization_config.charts.map(c => c.type)
          : requestedChartTypes}
        chartMetadata={useConfigVisualization && visualization_config?.charts
          ? visualization_config.charts.map(c => ({
            id: c.id,
            type: c.type,
            title: c.title,
            description: c.description,
            data_source: c.data_source,
            config: c.config
          }))
          : []}
      />

      {/* Show visualization insights if available */}
      {useConfigVisualization && visualization_config?.insights && (
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border-1 border-blue-200 rounded-xl p-6">
          <h4 className="text-lg font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600 mb-2">
            AI-Generated Insights
          </h4>
          <p className="text-gray-700 leading-relaxed">{visualization_config.insights}</p>
        </div>
      )}

      {/* Data Table */}
      <div className="p-8 rounded-xl bg-gradient-to-br from-gray-50 to-pink-50 border-1 border-purple-100">
        <div className="mb-6">
          <h4 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-pink-600">Data Table</h4>
          <p className="text-sm text-gray-600 mt-1">{rowCount} Record{rowCount !== 1 ? 's' : ''}</p>
        </div>
        <div className="overflow-auto max-h-96">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-100 sticky top-0">
              <tr>
                {Object.keys(dataArray[0]).map((col) => (
                  <th
                    key={col}
                    className="px-3 py-2 text-left font-semibold text-gray-900 uppercase tracking-wider"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-100">
              {dataArray.map((row, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  {Object.entries(row).map(([, value], colIdx) => {
                    // Handle different value types
                    const displayValue =
                      value === null || value === undefined
                        ? '-'
                        : typeof value === 'object' && value !== null && 'value' in value
                          ? String((value as Record<string, unknown>).value)  // Extract 'value' from JSONB
                          : typeof value === 'object'
                            ? JSON.stringify(value)
                            : typeof value === 'number'
                              ? value.toLocaleString()
                              : String(value);

                    return (
                      <td key={colIdx} className="px-3 py-2 text-gray-800 whitespace-nowrap">
                        {displayValue}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* AI Generated Summary */}
      {additionalFields && Object.keys(additionalFields).length > 0 && (
        <div className="bg-gradient-to-br from-white to-indigo-50 p-8 rounded-2xl 1 border-indigo-100 shadow-lg hover:shadow-xl transition-shadow">
          <div className="mb-6">
            <h4 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">AI Generated Summary</h4>
            <p className="text-sm text-gray-600 mt-1">Insights and analysis</p>
          </div>
          <div className="space-y-4">
            {Object.entries(additionalFields).map(([key, value]) => {
              if (!value) return null;

              // Handle nested objects or arrays
              let content = '';
              if (typeof value === 'object') {
                try {
                  content = JSON.stringify(value, null, 2);
                } catch {
                  content = String(value);
                }
              } else {
                content = String(value);
              }

              // 🛠️ AGGRESSIVE CLEANING: Handle ALL escape sequences and malformed markdown
              content = content
                .replace(/\\\\n/g, '\n')  // Double-escaped newlines
                .replace(/\\n/g, '\n')     // Escaped newlines
                .replace(/\\r/g, '')        // Remove carriage returns
                .replace(/\\t/g, ' ')       // Tabs to spaces
                .trim();                    // Remove leading/trailing whitespace

              // Debug logging - DETAILED
              console.log('🔍 AI SUMMARY DEBUG:', {
                key,
                rawType: typeof value,
                rawValue: String(value).substring(0, 100),
                contentLength: content.length,
                firstChars: content.substring(0, 100),
                hasDoubleHash: content.includes('##'),
                hasBold: content.includes('**'),
                hasNewlines: content.includes('\n'),
                newlineCount: (content.match(/\n/g) || []).length,
                sampleLines: content.split('\n').slice(0, 5)
              });

              // Check if markdown exists
              const hasMarkdown = content.includes('#') || content.includes('**') || content.includes('-') || content.includes('>');

              if (!hasMarkdown) {
                console.warn('⚠️ No markdown detected in AI summary! Content appears to be plain text.');
                console.warn('Raw content:', content.substring(0, 200));
              } else {
                console.log('✅ Markdown detected! Headers:', content.match(/^#{1,4}\s+.+$/gm)?.length || 0);
                console.log('📝 Content being passed to ReactMarkdown:');
                console.log(content.substring(0, 300));
              }

              return (
                <div key={key} className="max-w-none" style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>
                  {/* Debug indicator */}
                  <div style={{ display: 'none' }}>🟢 ReactMarkdown Component Loaded</div>
                  <div className="markdown-content text-gray-800 leading-relaxed" style={{ fontFamily: 'inherit' }}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({ ...props }) => <h1 className="text-3xl font-bold text-gray-900 mt-8 mb-4" style={{ fontFamily: 'inherit' }} {...props} />,
                        h2: ({ ...props }) => <h2 className="text-2xl font-bold text-indigo-900 mt-6 mb-4" style={{ fontFamily: 'inherit' }} {...props} />,
                        h3: ({ ...props }) => <h3 className="text-xl font-semibold text-indigo-800 mt-5 mb-3" style={{ fontFamily: 'inherit' }} {...props} />,
                        h4: ({ ...props }) => <h4 className="text-lg font-semibold text-gray-800 mt-4 mb-2" style={{ fontFamily: 'inherit' }} {...props} />,
                        p: ({ ...props }) => <p className="text-base text-gray-700 mb-3 leading-relaxed" style={{ fontFamily: 'inherit' }} {...props} />,
                        ul: ({ ...props }) => <ul className="list-disc list-outside ml-6 mb-4 space-y-2" style={{ fontFamily: 'inherit' }} {...props} />,
                        ol: ({ ...props }) => <ol className="list-decimal list-outside ml-6 mb-4 space-y-2" style={{ fontFamily: 'inherit' }} {...props} />,
                        li: ({ ...props }) => <li className="text-gray-700 leading-relaxed" style={{ fontFamily: 'inherit' }} {...props} />,
                        strong: ({ ...props }) => <strong className="font-bold text-indigo-900" style={{ fontFamily: 'inherit' }} {...props} />,
                        em: ({ ...props }) => <em className="italic text-gray-700" style={{ fontFamily: 'inherit' }} {...props} />,
                        blockquote: ({ ...props }) => <blockquote className="border-l-4 border-amber-500 bg-amber-50 pl-4 py-2 my-4 italic text-gray-800" style={{ fontFamily: 'inherit' }} {...props} />,
                        code: ({ ...props }) => <code className="bg-gray-100 text-indigo-600 px-1.5 py-0.5 rounded text-sm" style={{ fontFamily: 'ui-monospace, monospace' }} {...props} />,
                        pre: ({ ...props }) => <pre className="bg-gray-100 p-4 rounded-lg overflow-auto my-3" style={{ fontFamily: 'ui-monospace, monospace' }} {...props} />,
                      }}
                    >
                      {content}
                    </ReactMarkdown>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default DataVisualization;