import React from 'react';

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onStartDateChange: (date: string) => void;
  onEndDateChange: (date: string) => void;
}

export const DateRangePicker: React.FC<DateRangePickerProps> = ({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
}) => {
  return (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Start Date
        </label>
        <input
          type="date"
          value={startDate}
          onChange={(e) => onStartDateChange(e.target.value)}
          className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 shadow-sm"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          End Date
        </label>
        <input
          type="date"
          value={endDate}
          onChange={(e) => onEndDateChange(e.target.value)}
          className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 shadow-sm"
        />
      </div>
    </>
  );
};

interface MonthYearPickerProps {
  month: string;
  year: string;
  onMonthChange: (month: string) => void;
  onYearChange: (year: string) => void;
}

export const MonthYearPicker: React.FC<MonthYearPickerProps> = ({
  month,
  year,
  onMonthChange,
  onYearChange,
}) => {
  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const years = Array.from({ length: 10 }, (_, i) => new Date().getFullYear() - i);

  return (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Month
        </label>
        <select
          value={month}
          onChange={(e) => onMonthChange(e.target.value)}
          className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 shadow-sm"
        >
          <option value="">Select Month</option>
          {months.map((m, idx) => (
            <option key={m} value={(idx + 1).toString().padStart(2, '0')}>
              {m}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Year
        </label>
        <select
          value={year}
          onChange={(e) => onYearChange(e.target.value)}
          className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 shadow-sm"
        >
          <option value="">Select Year</option>
          {years.map((y) => (
            <option key={y} value={y.toString()}>
              {y}
            </option>
          ))}
        </select>
      </div>
    </>
  );
};

interface YearPickerProps {
  year: string;
  onYearChange: (year: string) => void;
}

export const YearPicker: React.FC<YearPickerProps> = ({
  year,
  onYearChange,
}) => {
  const years = Array.from({ length: 10 }, (_, i) => new Date().getFullYear() - i);

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        Year
      </label>
      <select
        value={year}
        onChange={(e) => onYearChange(e.target.value)}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="">Select Year</option>
        {years.map((y) => (
          <option key={y} value={y.toString()}>
            {y}
          </option>
        ))}
      </select>
    </div>
  );
};