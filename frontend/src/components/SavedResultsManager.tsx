import React, { useState, useEffect, useRef } from 'react';
import { type ExecuteAgentResponse } from '../services/api';

interface SavedResult {
  id: string;
  name: string;
  timestamp: string;
}

interface SavedResultsManagerProps {
  agentId: string;
  currentResult: ExecuteAgentResponse | null;
  resultSaved: boolean;
  onSaveResult: (name: string) => Promise<void>;
  onLoadResult: (resultId: string) => Promise<void>;
  handleDownloadPDF: () => Promise<void>;
}

export default function SavedResultsManager({
  agentId,
  currentResult,
  resultSaved,
  onSaveResult,
  onLoadResult,
  handleDownloadPDF,
}: SavedResultsManagerProps) {
  const [savedResults, setSavedResults] = useState<SavedResult[]>([]);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [resultName, setResultName] = useState('');
  const [selectedResultId, setSelectedResultId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [showSavedList, setShowSavedList] = useState(false);

  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadSavedResults();
    
    // Close dropdown on outside click
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowSavedList(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [agentId]);


  const loadSavedResults = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/agents/${agentId}/results`);
      const data = await response.json();
      if (data.success) {
        setSavedResults(data.results || []);
      }
    } catch (error) {
      console.error('Failed to load saved results:', error);
    }
  };

  const handleSaveClick = () => {
    if (!currentResult) {
      alert('No result to save');
      return;
    }
    const timestamp = new Date().toLocaleString();
    setResultName(`Result - ${timestamp}`);
    setShowSaveModal(true);
  };

  const handleSaveConfirm = async () => {
    setLoading(true);
    try {
      await onSaveResult(resultName);
      setShowSaveModal(false);
      setResultName('');
      await loadSavedResults(); // Refresh list
    } catch (error) {
      console.error('Failed to save result:', error);
      alert('Failed to save result');
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSelect = async (resultId: string) => {
    if (currentResult && !resultSaved) {
      // Current result not saved, show confirmation
      setSelectedResultId(resultId);
      setShowConfirmModal(true);
    } else {
      // Safe to load
      await loadResult(resultId);
    }
  };

  const loadResult = async (resultId: string) => {
    setLoading(true);
    try {
      await onLoadResult(resultId);
    } catch (error) {
      console.error('Failed to load result:', error);
      alert('Failed to load result');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmSaveAndContinue = async () => {
    const timestamp = new Date().toLocaleString();
    const autoName = `Result - ${timestamp}`;
    
    setLoading(true);
    try {
      await onSaveResult(autoName);
      await loadResult(selectedResultId);
      setShowConfirmModal(false);
    } catch (error) {
      console.error('Failed to save and load:', error);
      alert('Failed to save and load result');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmContinue = async () => {
    await loadResult(selectedResultId);
    setShowConfirmModal(false);
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString();
    } catch {
      return timestamp;
    }
  };

  return (
    <>
      <div className="flex items-center gap-4">
        {/* Load Result Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setShowSavedList(!showSavedList)}
            disabled={loading}
            className={`group text-sm flex items-center gap-2 font-semibold transition-colors
              ${showSavedList ? 'text-blue-700' : 'text-blue-600 hover:text-blue-800'}
              disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            <span>Load Saved Result</span>
            <svg 
              className={`w-4 h-4 transition-transform duration-200 ${showSavedList ? 'rotate-180' : 'group-hover:translate-y-0.5'}`} 
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          

          {/* Dropdown Menu */}
          {showSavedList && (
            <div className="absolute left-0 mt-3 w-72 bg-white border border-gray-200 rounded-xl shadow-xl z-50 py-2 animate-in fade-in slide-in-from-top-2 duration-200">
              <div className="px-4 py-2 text-xs font-bold text-gray-400 uppercase tracking-wider">
                Saved Executions
              </div>
              <div className="max-h-64 overflow-y-auto custom-scrollbar">
                {savedResults.length === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-gray-500 italic">
                    No saved results found
                  </div>
                ) : (
                  savedResults.map((result) => (
                    <button
                      key={result.id}
                      onClick={() => {
                        handleLoadSelect(result.id);
                        setShowSavedList(false);
                      }}
                      className="w-full text-left px-4 py-3 hover:bg-blue-50 transition-colors border-l-2 border-transparent hover:border-blue-500 group"
                    >
                      <div className="text-sm font-medium text-gray-800 group-hover:text-blue-700 truncate">
                        {result.name}
                      </div>
                      <div className="text-[11px] text-gray-400 mt-0.5">
                        {formatTimestamp(result.timestamp)}
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Vertical Divider */}
        {currentResult && <div className="h-4 w-[1px] bg-gray-300" />}

        {/* Save Result Button */}
        {currentResult && (
            <>
          <button
            onClick={handleSaveClick}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-blue-700 active:bg-blue-800 transition-all shadow-sm hover:shadow-md disabled:opacity-50 disabled:shadow-none"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4" />
            </svg>
            Save Result
          </button>

    <button
      onClick={handleDownloadPDF}
      className="flex items-center gap-2 bg-emerald-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-emerald-700 active:bg-emerald-800 transition-all shadow-sm hover:shadow-md focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50"
    >
      <svg 
        className="w-4 h-4" 
        fill="none" 
        stroke="currentColor" 
        viewBox="0 0 24 24"
      >
        <path 
          strokeLinecap="round" 
          strokeLinejoin="round" 
          strokeWidth={2} 
          d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" 
        />
      </svg>
      Download PDF
    </button>
    </>
        )}
      </div>

      {/* Save Modal - Improved Styling */}
      {showSaveModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 overflow-hidden">
          <div className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm transition-opacity" onClick={() => setShowSaveModal(false)} />
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md relative z-10 transform transition-all animate-in zoom-in-95 duration-200">
            <div className="p-6">
              <h3 className="text-xl font-bold text-gray-900">Save Execution</h3>
              <p className="text-sm text-gray-500 mt-1 mb-6">Give this result a name to find it later.</p>
              
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700 uppercase ml-1">Result Name</label>
                <input
                  autoFocus
                  type="text"
                  value={resultName}
                  onChange={(e) => setResultName(e.target.value)}
                  className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all outline-none"
                  placeholder="Monthly Audit - Jan"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 p-4 bg-gray-50 rounded-b-2xl">
              <button onClick={() => setShowSaveModal(false)} className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800">
                Cancel
              </button>
              <button
                onClick={handleSaveConfirm}
                disabled={!resultName.trim() || loading}
                className="px-6 py-2 bg-blue-600 text-white text-sm font-bold rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Saving...' : 'Save Result'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Modal - Improved Styling */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm" />
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm relative z-10 p-6 text-center animate-in scale-in-95">
            <div className="w-16 h-16 bg-yellow-100 text-yellow-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-gray-900">Unsaved Changes</h3>
            <p className="text-sm text-gray-500 mt-2 mb-6">
              The current result isn't saved. Loading a new one will overwrite this data.
            </p>
            <div className="space-y-2">
              <button
                onClick={handleConfirmSaveAndContinue}
                disabled={loading}
                className="w-full py-2.5 bg-blue-600 text-white rounded-xl font-bold text-sm hover:bg-blue-700 transition-colors"
              >
                Save & Continue
              </button>
              <button
                onClick={handleConfirmContinue}
                className="w-full py-2.5 bg-white border border-gray-200 text-gray-700 rounded-xl font-semibold text-sm hover:bg-gray-50 transition-colors"
              >
                Discard & Continue
              </button>
              <button
                onClick={() => setShowConfirmModal(false)}
                className="w-full py-2 text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Go Back
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
