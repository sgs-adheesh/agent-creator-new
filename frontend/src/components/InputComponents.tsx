// import type { CustomField } from '../services/api';

// interface YearSelectorProps {
//   value: string;
//   onChange: (value: string) => void;
//   disabled?: boolean;
// }

// export function YearSelector({ value, onChange, disabled }: YearSelectorProps) {
//   return (
//     <div className="space-y-2">
//       <label className="block text-sm font-medium text-gray-700">
//         Year
//       </label>
//       <select
//         value={value}
//         onChange={(e) => onChange(e.target.value)}
//         disabled={disabled}
//         className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
//       >
//         <option value="">Select Year</option>
//         {[2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030].map(year => (
//           <option key={year} value={year.toString()}>
//             {year}
//           </option>
//         ))}
//       </select>
//     </div>
//   );
// }

// interface MonthYearSelectorProps {
//   month: string;
//   year: string;
//   onMonthChange: (month: string) => void;
//   onYearChange: (year: string) => void;
//   disabled?: boolean;
// }

// export function MonthYearSelector({ 
//   month, 
//   year, 
//   onMonthChange, 
//   onYearChange, 
//   disabled 
// }: MonthYearSelectorProps) {
//   const months = [
//     'January', 'February', 'March', 'April', 'May', 'June',
//     'July', 'August', 'September', 'October', 'November', 'December'
//   ];

//   return (
//     <div className="grid grid-cols-2 gap-4">
//       <div className="space-y-2">
//         <label className="block text-sm font-medium text-gray-700">
//           Month
//         </label>
//         <select
//           value={month}
//           onChange={(e) => onMonthChange(e.target.value)}
//           disabled={disabled}
//           className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
//         >
//           <option value="">Select Month</option>
//           {months.map(m => (
//             <option key={m} value={m}>
//               {m}
//             </option>
//           ))}
//         </select>
//       </div>
      
//       <div className="space-y-2">
//         <label className="block text-sm font-medium text-gray-700">
//           Year
//         </label>
//         <select
//           value={year}
//           onChange={(e) => onYearChange(e.target.value)}
//           disabled={disabled}
//           className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
//         >
//           <option value="">Select Year</option>
//           {[2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030].map(y => (
//             <option key={y} value={y.toString()}>
//               {y}
//             </option>
//           ))}
//         </select>
//       </div>
//     </div>
//   );
// }

// interface DateRangeSelectorProps {
//   startDate: string;
//   endDate: string;
//   onStartDateChange: (date: string) => void;
//   onEndDateChange: (date: string) => void;
//   disabled?: boolean;
// }

// export function DateRangeSelector({ 
//   startDate, 
//   endDate, 
//   onStartDateChange, 
//   onEndDateChange, 
//   disabled 
// }: DateRangeSelectorProps) {
//   return (
//     <div className="grid grid-cols-2 gap-4">
//       <div className="space-y-2">
//         <label className="block text-sm font-medium text-gray-700">
//           Start Date
//         </label>
//         <input
//           type="date"
//           value={startDate}
//           onChange={(e) => onStartDateChange(e.target.value)}
//           disabled={disabled}
//           className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
//         />
//       </div>
      
//       <div className="space-y-2">
//         <label className="block text-sm font-medium text-gray-700">
//           End Date
//         </label>
//         <input
//           type="date"
//           value={endDate}
//           onChange={(e) => onEndDateChange(e.target.value)}
//           disabled={disabled}
//           className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
//         />
//       </div>
//     </div>
//   );
// }

// interface CustomFieldRendererProps {
//   fields: CustomField[];
//   values: Record<string, string>;
//   onChange: (fieldValue: string, fieldName: string) => void;
//   disabled?: boolean;
// }

// export function CustomFieldRenderer({ 
//   fields, 
//   values, 
//   onChange, 
//   disabled 
// }: CustomFieldRendererProps) {
//   if (!fields || fields.length === 0) {
//     return (
//       <div className="text-center py-4 text-gray-500">
//         No custom fields configured
//       </div>
//     );
//   }

//   return (
//     <div className="space-y-4">
//       <p className="text-sm text-gray-600">Fill in the required information:</p>
//       {fields.map((field: CustomField, index: number) => (
//         <div key={index} className="space-y-2">
//           <label className="block text-sm font-medium text-gray-700">
//             {field.label}
//           </label>
          
//           {field.type === 'text' && (
//             <input
//               type="text"
//               value={values[field.value] || ''}
//               onChange={(e) => onChange(e.target.value, field.value)}
//               disabled={disabled}
//               className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
//               placeholder={field.label}
//             />
//           )}
          
//           {field.type === 'number' && (
//             <input
//               type="number"
//               value={values[field.value] || ''}
//               onChange={(e) => onChange(e.target.value, field.value)}
//               disabled={disabled}
//               className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
//               placeholder={field.label}
//             />
//           )}
          
//           {field.type === 'dropdown' && field.options && (
//             <select
//               value={values[field.value] || ''}
//               onChange={(e) => onChange(e.target.value, field.value)}
//               disabled={disabled}
//               className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
//             >
//               <option value="">Select an option</option>
//               {field.options.split(',').map((opt: string, i: number) => (
//                 <option key={i} value={opt.trim()}>
//                   {opt.trim()}
//                 </option>
//               ))}
//             </select>
//           )}
          
//           {field.type === 'date' && (
//             <input
//               type="date"
//               value={values[field.value] || ''}
//               onChange={(e) => onChange(e.target.value, field.value)}
//               disabled={disabled}
//               className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
//             />
//           )}
//         </div>
//       ))}
//     </div>
//   );
// }