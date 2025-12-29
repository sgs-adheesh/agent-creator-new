import { useMemo } from 'react';
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer
} from 'recharts';

interface DataVisualizationProps {
  data: unknown;
  title?: string;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

// Helper to extract numeric fields from data
function extractNumericFields(data: Record<string, unknown>[]): string[] {
  if (!data || data.length === 0) return [];
  
  const firstRow = data[0];
  const numericFields: string[] = [];
  
  for (const [key, value] of Object.entries(firstRow)) {
    // Extract actual value from JSONB wrapper if present
    const actualValue = (typeof value === 'object' && value !== null && 'value' in value) 
      ? (value as Record<string, unknown>).value 
      : value;
    
    if (typeof actualValue === 'number' || (typeof actualValue === 'string' && !isNaN(parseFloat(actualValue)) && isFinite(parseFloat(actualValue)))) {
      numericFields.push(key);
    }
  }
  
  return numericFields;
}

// Helper to extract categorical fields (non-numeric, non-id)
function extractCategoricalFields(data: Record<string, unknown>[]): string[] {
  if (!data || data.length === 0) return [];
  
  const firstRow = data[0];
  const categoricalFields: string[] = [];
  
  for (const [key, value] of Object.entries(firstRow)) {
    // Extract actual value from JSONB wrapper if present
    const actualValue = (typeof value === 'object' && value !== null && 'value' in value) 
      ? (value as Record<string, unknown>).value 
      : value;
    
    const isId = key.toLowerCase().includes('id') || key.toLowerCase() === 'uuid';
    const isNumeric = typeof actualValue === 'number' || (typeof actualValue === 'string' && !isNaN(parseFloat(actualValue)));
    
    if (!isId && !isNumeric && typeof actualValue === 'string') {
      categoricalFields.push(key);
    }
  }
  
  return categoricalFields;
}

// Analyze data structure and prepare visualization data
function analyzeData(rawData: unknown) {
  // Handle different data formats
  let dataArray: Record<string, unknown>[] = [];
  
  if (Array.isArray(rawData)) {
    dataArray = rawData as Record<string, unknown>[];
  } else if (typeof rawData === 'object' && rawData !== null) {
    const typedData = rawData as Record<string, unknown>;
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
  
  // Extract field types
  const numericFields = extractNumericFields(dataArray);
  const categoricalFields = extractCategoricalFields(dataArray);
  
  return {
    dataArray,
    numericFields,
    categoricalFields,
    rowCount: dataArray.length
  };
}

export function DataVisualization({ data, title }: DataVisualizationProps) {
  const analysis = useMemo(() => analyzeData(data), [data]);
  
  // Prepare pie chart data (aggregate by first categorical field if exists)
  const pieData = useMemo(() => {
    if (!analysis || analysis.categoricalFields.length === 0 || analysis.numericFields.length === 0) return null;
    
    const { dataArray, categoricalFields, numericFields } = analysis;
    const categoryField = categoricalFields[0];
    const valueField = numericFields[0];
    
    // Aggregate values by category
    const aggregated = dataArray.reduce((acc: Record<string, number>, row: Record<string, unknown>) => {
      const categoryValue = row[categoryField];
      const numericValue = row[valueField];
      
      // Extract actual values from JSONB wrapper if present
      const category = String(
        (typeof categoryValue === 'object' && categoryValue !== null && 'value' in categoryValue)
          ? (categoryValue as Record<string, unknown>).value
          : categoryValue || 'Unknown'
      );
      
      const value = parseFloat(String(
        (typeof numericValue === 'object' && numericValue !== null && 'value' in numericValue)
          ? (numericValue as Record<string, unknown>).value
          : numericValue || 0
      )) || 0;
      
      acc[category] = (acc[category] || 0) + value;
      return acc;
    }, {});
    
    return Object.entries(aggregated).map(([name, value]) => ({ name, value }));
  }, [analysis]);
  
  // Prepare bar chart data (use first few rows or aggregated data)
  const barData = useMemo(() => {
    if (!analysis || analysis.numericFields.length === 0) return null;
    
    const { dataArray, numericFields, categoricalFields } = analysis;
    
    // Limit to 10 rows for clarity
    return dataArray.slice(0, 10).map((row, idx) => {
      const result: Record<string, unknown> = {};
      
      // Use categorical field as label, or row index
      if (categoricalFields.length > 0) {
        const nameValue = row[categoricalFields[0]];
        result.name = String(
          (typeof nameValue === 'object' && nameValue !== null && 'value' in nameValue)
            ? (nameValue as Record<string, unknown>).value
            : nameValue
        );
      } else {
        result.name = `Row ${idx + 1}`;
      }
      
      // Add all numeric fields
      numericFields.forEach(field => {
        const fieldValue = row[field];
        const actualValue = (typeof fieldValue === 'object' && fieldValue !== null && 'value' in fieldValue)
          ? (fieldValue as Record<string, unknown>).value
          : fieldValue;
        result[field] = parseFloat(String(actualValue || 0)) || 0;
      });
      
      return result;
    });
  }, [analysis]);
  
  if (!analysis || analysis.dataArray.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <p>No data available for visualization</p>
      </div>
    );
  }
  
  const { dataArray, numericFields, categoricalFields, rowCount } = analysis;
  
  return (
    <div className="space-y-6">
      {title && (
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      )}
      
      {/* Pie Chart */}
      {pieData && pieData.length > 0 && (
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-3">
            Distribution - {categoricalFields[0]} by {numericFields[0]}
          </h4>
          <ResponsiveContainer width="80%" height={400}>
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={100}
                fill="#8884d8"
                label={({ name, percent }) => `${name || 'Unknown'}: ${((percent ?? 0) * 100).toFixed(0)}%`}
              >
                {pieData.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => typeof value === 'number' ? value.toFixed(2) : value !== undefined ? String(value) : '-'} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      )}
      
      {/* Bar Chart */}
      {barData && barData.length > 0 && (
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <h4 className="text-sm font-medium text-gray-700 mb-3">
            Comparison Chart - Top {Math.min(10, rowCount)} Records
          </h4>
          <ResponsiveContainer width="80%" height={400}>
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={80} />
              <YAxis />
              <Tooltip />
              <Legend />
              {numericFields.map((field, idx) => (
                <Bar key={field} dataKey={field} fill={COLORS[idx % COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      
      {/* Data Table */}
      <div className="bg-white p-4 rounded-lg border border-gray-200">
        <h4 className="text-sm font-medium text-gray-700 mb-3">
          Data Table - {rowCount} Record{rowCount !== 1 ? 's' : ''}
        </h4>
        <div className="overflow-auto max-h-96">
          <table className="min-w-full divide-y divide-gray-200 text-xs">
            <thead className="bg-gray-50 sticky top-0">
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
    </div>
  );
}
