import { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import DashboardCharts from './RE-Chart';

interface DataVisualizationProps {
  data: unknown;
  title?: string;
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
    
    // Exclude pure UUID/ID columns (internal system IDs)
    const isPureId = keyLower === 'id' || keyLower === 'uuid';
    
    if (!isPureId && (isStringValue || isIdentifier)) {
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

export function DataVisualization({ data, title }: DataVisualizationProps) {
  const analysis = useMemo(() => {
    const result = analyzeData(data);
    if (result) {
      console.log('🔍 Analysis Result:');
      console.log('  - Numeric fields:', result.numericFields);
      console.log('  - Categorical fields:', result.categoricalFields);
    }
    return result;
  }, [data]);
  
  // Prepare pie chart data (aggregate by best categorical field)
  const pieData = useMemo(() => {
    if (!analysis || analysis.categoricalFields.length === 0 || analysis.numericFields.length === 0) return null;
    
    const { dataArray, categoricalFields, numericFields } = analysis;
    
    // Select best category field (ONLY use vendor_name for grouping, NOT invoice_number)
    let categoryField = null;
    
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
      const categoryValue = row[categoryField];
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
      _categoryField: categoryField, // Include for heading display
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
    let labelField = null;
    
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
      const categoryValue = row[labelField];
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
  pieData={pieData || []}
  barData={barData || []}
  categoricalFields={categoricalFields}
  numericFields={numericFields}
  rowCount={rowCount}
/>
      
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
              }
              
              return (
                <div key={key} className="max-w-none" style={{ fontFamily: 'system-ui, -apple-system, sans-serif' }}>
                  <div className="markdown-content text-gray-800 leading-relaxed" style={{ fontFamily: 'inherit' }}>
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({...props}) => <h1 className="text-3xl font-bold text-gray-900 mt-8 mb-4" style={{ fontFamily: 'inherit' }} {...props} />,
                        h2: ({...props}) => <h2 className="text-2xl font-bold text-indigo-900 mt-6 mb-4" style={{ fontFamily: 'inherit' }} {...props} />,
                        h3: ({...props}) => <h3 className="text-xl font-semibold text-indigo-800 mt-5 mb-3" style={{ fontFamily: 'inherit' }} {...props} />,
                        h4: ({...props}) => <h4 className="text-lg font-semibold text-gray-800 mt-4 mb-2" style={{ fontFamily: 'inherit' }} {...props} />,
                        p: ({...props}) => <p className="text-base text-gray-700 mb-3 leading-relaxed" style={{ fontFamily: 'inherit' }} {...props} />,
                        ul: ({...props}) => <ul className="list-disc list-outside ml-6 mb-4 space-y-2" style={{ fontFamily: 'inherit' }} {...props} />,
                        ol: ({...props}) => <ol className="list-decimal list-outside ml-6 mb-4 space-y-2" style={{ fontFamily: 'inherit' }} {...props} />,
                        li: ({...props}) => <li className="text-gray-700 leading-relaxed" style={{ fontFamily: 'inherit' }} {...props} />,
                        strong: ({...props}) => <strong className="font-bold text-indigo-900" style={{ fontFamily: 'inherit' }} {...props} />,
                        em: ({...props}) => <em className="italic text-gray-700" style={{ fontFamily: 'inherit' }} {...props} />,
                        blockquote: ({...props}) => <blockquote className="border-l-4 border-amber-500 bg-amber-50 pl-4 py-2 my-4 italic text-gray-800" style={{ fontFamily: 'inherit' }} {...props} />,
                        code: ({...props}) => <code className="bg-gray-100 text-indigo-600 px-1.5 py-0.5 rounded text-sm" style={{ fontFamily: 'ui-monospace, monospace' }} {...props} />,
                        pre: ({...props}) => <pre className="bg-gray-100 p-4 rounded-lg overflow-auto my-3" style={{ fontFamily: 'ui-monospace, monospace' }} {...props} />,
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
