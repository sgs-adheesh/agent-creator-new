import React, { useState, useEffect } from 'react';
import { 
  CheckCircle2, 
  Circle, 
  AlertCircle, 
  ChevronDown, 
  Loader2,
  Sparkles
} from 'lucide-react';

export interface ProgressStep {
  id: string;
  label: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error';
  detail?: string;
  substeps?: ProgressStep[];  // NEW: Support nested sub-steps
}

interface ProgressPanelProps {
  title: string;
  steps: ProgressStep[];
}

/**
 * StatusIcon: Sub-component for clean status rendering.
 * Uses Lucide-react for industry-standard SVG icons.
 */
const StatusIcon = ({ status, isHeader = false }: { status: ProgressStep['status'] | 'active', isHeader?: boolean }) => {
  const iconSize = isHeader ? "h-5 w-5" : "h-[22px] w-[22px]";

  switch (status) {
    case 'completed':
      return <CheckCircle2 className={`${iconSize} text-emerald-500 fill-emerald-50`} />;
    case 'in_progress':
      return (
        <div className="relative flex items-center justify-center">
          <Loader2 className={`${iconSize} animate-spin text-blue-500`} />
          <div className="absolute h-1.5 w-1.5 bg-blue-500 rounded-full" />
        </div>
      );
    case 'error':
      return <AlertCircle className={`${iconSize} text-red-500 fill-red-50`} />;
    case 'pending':
    default:
      return <Circle className={`${iconSize} text-slate-300`} />;
  }
};

  const ProgressPanel = ({ title, steps }: ProgressPanelProps) => {
  const hasError = steps.some(s => s.status === 'error');
  const allCompleted = steps.every(s => s.status === 'completed');
  const inProgress = steps.some(s => s.status === 'in_progress');

  // Compute initial expanded state: should be expanded if in progress OR not all completed
  const shouldBeExpanded = inProgress || !allCompleted;
  
  const [expanded, setExpanded] = useState(() => {
    return shouldBeExpanded;
  });

  useEffect(() => {
    if (allCompleted) {
      const timer = setTimeout(() => {
        setExpanded(false);
      }, 1500);
      return () => {
        clearTimeout(timer);
      };
    } else if (inProgress) {
      // When execution starts, expand immediately
      // eslint-disable-next-line react-hooks/exhaustive-deps
      setExpanded(true);
    }
  }, [allCompleted, inProgress]);

  const getContainerStyles = () => {
    if (hasError) return "border-red-200 bg-red-50/50 text-red-900";
    if (allCompleted) return "border-emerald-200 bg-emerald-50/50 text-emerald-900";
    if (inProgress) return "border-blue-200 bg-blue-50/50 text-blue-900";
    return "border-slate-200 bg-slate-50 text-slate-900";
  };

  return (
    <>
      {/* Collapsed Bar - Inline */}
      {!expanded && (
        <div className={`overflow-hidden rounded-xl border transition-all duration-200 ${getContainerStyles()}`}>
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex w-full items-center justify-between p-4 text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500/40"
            aria-expanded={expanded}
          >
            <div className="flex items-center gap-3 font-semibold">
              <StatusIcon 
                status={hasError ? 'error' : allCompleted ? 'completed' : inProgress ? 'in_progress' : 'pending'} 
                isHeader 
              />
              <span className="text-sm md:text-base font-semibold tracking-tight">{title}</span>
            </div>
            <ChevronDown 
              className={`h-5 w-5 text-slate-400 transition-transform duration-300 ease-in-out ${expanded ? 'rotate-180' : ''}`} 
            />
          </button>
        </div>
      )}

      {/* Expanded Modal */}
      {expanded && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 backdrop-blur-sm"
          onClick={() => setExpanded(false)}  // Close on backdrop click
        >
          <div 
            className="w-full max-w-2xl mx-4"
            onClick={(e) => e.stopPropagation()}  // Prevent close when clicking modal content
          >
            <div className={`overflow-hidden rounded-xl border transition-all duration-200 shadow-2xl ${getContainerStyles()}`}>
              {/* Header Button */}
              <button
                onClick={() => setExpanded(!expanded)}
                className="flex w-full items-center justify-between p-4 text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500/40"
                aria-expanded={expanded}
              >
                <div className="flex items-center gap-3 font-semibold">
                  <StatusIcon 
                    status={hasError ? 'error' : allCompleted ? 'completed' : inProgress ? 'in_progress' : 'pending'} 
                    isHeader 
                  />
                  <span className="text-sm md:text-base font-semibold tracking-tight">{title}</span>
                </div>
                <ChevronDown 
                  className={`h-5 w-5 text-slate-400 transition-transform duration-300 ease-in-out ${expanded ? 'rotate-180' : ''}`} 
                />
              </button>

              {/* Expandable Content */}
              <div className="overflow-hidden">
                <div className="border-t border-inherit bg-white p-5 space-y-1">
                  {steps.map((step, index) => (
                    <div key={step.id} className="relative flex gap-4 group">
                      
                      {/* Vertical Connector Line */}
                      {index !== steps.length - 1 && (
                        <div className="absolute left-[10px] top-[26px] h-[calc(100%-20px)] w-[1.5px] bg-slate-100 group-hover:bg-slate-200 transition-colors" />
                      )}
                      
                      {/* Icon Column */}
                      <div className="relative z-10 mt-1 flex-shrink-0">
                        <StatusIcon status={step.status} />
                      </div>

                      {/* Text Column */}
                      <div className="pb-5">
                        <p className={`text-sm font-medium leading-tight ${
                          step.status === 'pending' ? 'text-slate-400' : 'text-slate-700'
                        }`}>
                          {step.label}
                        </p>
                        {step.detail && (
                          <div className="mt-1.5 rounded bg-slate-50 px-2 py-1 border border-slate-100">
                            <p className="text-[11px] font-mono text-slate-500 break-all leading-normal">
                              {step.detail}
                            </p>
                          </div>
                        )}
                        
                        {/* Nested Sub-steps with AI styling */}
                        {step.substeps && step.substeps.length > 0 && (
                          <div className="mt-2 ml-4 space-y-1.5 border-l-2 border-purple-300 pl-3 bg-purple-50/30 rounded-r py-2">
                            {step.substeps.map((substep) => (
                              <div key={substep.id} className="flex items-start gap-2">
                                <div className="mt-0.5 flex-shrink-0">
                                  {/* AI Substep Icon - Purple sparkles */}
                                  {substep.status === 'in_progress' ? (
                                    <div className="relative flex items-center justify-center">
                                      <Sparkles className="h-4 w-4 animate-pulse text-purple-500" />
                                    </div>
                                  ) : substep.status === 'completed' ? (
                                    <CheckCircle2 className="h-4 w-4 text-purple-500 fill-purple-50" />
                                  ) : substep.status === 'error' ? (
                                    <AlertCircle className="h-4 w-4 text-red-500 fill-red-50" />
                                  ) : (
                                    <Circle className="h-4 w-4 text-purple-300" />
                                  )}
                                </div>
                                <div>
                                  <p className={`text-xs leading-tight font-medium ${
                                    substep.status === 'pending' ? 'text-purple-400' : 'text-purple-700'
                                  }`}>
                                    {substep.label}
                                  </p>
                                  {substep.detail && (
                                    <p className="text-[10px] text-purple-500 mt-1">
                                      {substep.detail}
                                    </p>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ProgressPanel;