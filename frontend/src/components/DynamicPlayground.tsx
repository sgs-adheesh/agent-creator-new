import { useState } from 'react';
import { DateRangePicker, MonthYearPicker, YearPicker } from './DatePickers';
import {DynamicForm} from './DynamicForm';

interface DynamicPlaygroundProps {
  triggerType: string;
  inputFields: Array<{
    name: string;
    type: string;
    label: string;
    placeholder?: string;
    options?: string[];
  }>;
  onExecute: (inputData: Record<string, string | number | boolean>) => void;
  loading?: boolean;
}

export const DynamicPlayground: React.FC<DynamicPlaygroundProps> = ({
  triggerType,
  inputFields,
  onExecute,
  loading = false,
}) => {
  // State for different input types
  const [textQuery, setTextQuery] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [month, setMonth] = useState('');
  const [year, setYear] = useState('');

  const handleExecute = () => {
    let inputData: Record<string, string | number | boolean> = {};

    switch (triggerType) {
      case 'text_query':
        inputData = { query: textQuery };
        break;
        case 'date_range':
        inputData = { start_date: startDate, end_date: endDate };
          break;
        case 'month_year':
        inputData = { month, year };
          break;
        case 'year':
        inputData = { year };
          break;
      case 'scheduled':
        // No input needed for scheduled agents
        inputData = {};
          break;
      default:
        inputData = {};
      }

    onExecute(inputData);
  };

  const handleFormSubmit = (data: Record<string, string | number | boolean>) => {
    onExecute(data);
  };

  const renderInputUI = () => {
    switch (triggerType) {
      case 'text_query':
  return (
    <div className="space-y-4">
          <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Ask a Question
            </label>
            <textarea
                value={textQuery}
                onChange={(e) => setTextQuery(e.target.value)}
              rows={4}
                placeholder="Enter your query or question..."
                className="w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <button
              onClick={handleExecute}
              disabled={loading || !textQuery.trim()}
              className="w-full bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Executing...' : 'Execute Agent'}
            </button>
          </div>
        );

      case 'date_range':
        return (
          <div className="space-y-4">
            <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
            />
            <button
              onClick={handleExecute}
              disabled={loading || !startDate || !endDate}
              className="w-full bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Generating Report...' : 'Generate Report'}
            </button>
          </div>
        );

      case 'month_year':
        return (
          <div className="space-y-4">
            <MonthYearPicker
            month={month}
            year={year}
            onMonthChange={setMonth}
            onYearChange={setYear}
            />
            <button
              onClick={handleExecute}
              disabled={loading || !month || !year}
              className="w-full bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Generating Report...' : 'Generate Monthly Report'}
            </button>
          </div>
        );

      case 'year':
        return (
          <div className="space-y-4">
            <YearPicker year={year} onYearChange={setYear} />
            <button
              onClick={handleExecute}
              disabled={loading || !year}
              className="w-full bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Generating Report...' : 'Generate Yearly Report'}
            </button>
          </div>
        );

      case 'conditions':
        return (
          <DynamicForm
            fields={inputFields}
            onSubmit={handleFormSubmit}
            submitLabel={loading ? 'Processing...' : 'Submit'}
          />
        );

      case 'scheduled':
        return (
          <div className="text-center py-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-100 mb-4">
              <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">Scheduled Agent</h3>
            <p className="text-sm text-gray-500 mb-4">
              This agent runs automatically on a schedule. No manual input required.
            </p>
            <button
              onClick={handleExecute}
              disabled={loading}
              className="bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Running...' : 'Run Now (Manual Trigger)'}
            </button>
              </div>
        );

      default:
        return (
          <div className="text-center py-8 text-gray-500">
            <p>Unknown trigger type: {triggerType}</p>
            </div>
        );
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-1">Playground</h3>
        <p className="text-sm text-gray-500">
          {triggerType === 'text_query' && 'Ask questions to get answers from the agent'}
          {triggerType === 'date_range' && 'Select a date range to generate reports'}
          {triggerType === 'month_year' && 'Select month and year for monthly reports'}
          {triggerType === 'year' && 'Select a year for yearly reports'}
          {triggerType === 'conditions' && 'Fill in the required conditions to execute the workflow'}
          {triggerType === 'scheduled' && 'This agent runs on a schedule'}
        </p>
      </div>
      {renderInputUI()}
    </div>
  );
};
