import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Agent {
  id: string;
  name: string;
  prompt: string;
  created_at: string;
  workflow_config?: WorkflowConfig;
  selected_tools?: string[];
  tool_configs?: Record<string, Record<string, string>>;
}

export interface WorkflowConfig {
  trigger_type: string;  // "text_query", "date_range", "month_year", "year", "conditions", "scheduled"
  input_fields: Array<{
    name: string;
    type: string;
    label: string;
    placeholder?: string;
    options?: string[];
  }>;
  output_format: string;  // "text", "csv", "json", "table"
}

export interface CreateAgentRequest {
  prompt: string;
  name?: string;
  selected_tools?: string[];  // Tools to assign to this agent
  workflow_config?: WorkflowConfig;
}

export interface ExecuteAgentRequest {
  query: string;
  input_data?: Record<string, string | number | boolean>;
  tool_configs?: Record<string, Record<string, string>>;
}

export interface ExecuteAgentResponse {
  success: boolean;
  output?: string;
  error?: string;
  intermediate_steps?: unknown[];
  query_auto_saved?: boolean;
  saved_query?: string;
  query_corrected?: boolean;
  query_attempts?: number;
}

export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: Record<string, unknown>;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  animated?: boolean;
}

export interface WorkflowGraph {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  metadata?: Record<string, unknown>;
}

export interface UpdateAgentRequest {
  prompt: string;
  name?: string;
  workflow_config?: WorkflowConfig;
  selected_tools?: string[];
  tool_configs?: Record<string, Record<string, string>>;
}

export interface ToolSpec {
  name: string;
  display_name: string;
  description: string;
  api_type: string;
  service: string;
}

export interface ToolAnalysisResponse {
  success: boolean;
  matched_tools?: string[];
  new_tools_needed?: ToolSpec[];
  reasoning?: string;
  requires_user_confirmation: boolean;
  error?: string;
}

export interface ToolGenerationResponse {
  success: boolean;
  tool_name?: string;
  file_path?: string;
  dependencies?: string[];
  warnings?: string[];
  dependencies_installed?: boolean;
  installation_log?: Array<{
    package: string;
    success: boolean;
    message?: string;
    error?: string;
  }>;
  error?: string;
}

export interface ToolConfigField {
  name: string;
  label: string;
  type: string;
  required: boolean;
  env_var: string;
}

export interface ToolSchema {
  tool_name: string;
  config_fields: ToolConfigField[];
}

export const agentApi = {
  createAgent: async (data: CreateAgentRequest): Promise<Agent> => {
    const response = await api.post<Agent>('/api/agents/create', data);
    return response.data;
  },

  listAgents: async (): Promise<Agent[]> => {
    const response = await api.get<Agent[]>('/api/agents');
    return response.data;
  },

  getAgent: async (id: string): Promise<Agent> => {
    const response = await api.get<Agent>(`/api/agents/${id}`);
    return response.data;
  },

  executeAgent: async (id: string, query: string, toolConfigs?: Record<string, Record<string, string>>, inputData?: Record<string, string | number | boolean>): Promise<ExecuteAgentResponse> => {
    const response = await api.post<ExecuteAgentResponse>(`/api/agents/${id}/execute`, { 
      query,
      input_data: inputData,
      tool_configs: toolConfigs 
    });
    return response.data;
  },

  deleteAgent: async (id: string): Promise<void> => {
    await api.delete(`/api/agents/${id}`);
  },

  getWorkflow: async (id: string, useAi: boolean = true): Promise<WorkflowGraph> => {
    const response = await api.get<WorkflowGraph>(`/api/agents/${id}/workflow`, {
      params: { use_ai: useAi }
    });
    return response.data;
  },

  updateAgent: async (id: string, data: UpdateAgentRequest): Promise<Agent> => {
    const response = await api.put<Agent>(`/api/agents/${id}`, data);
    return response.data;
  },
};

export const toolApi = {
  analyzePrompt: async (prompt: string): Promise<ToolAnalysisResponse> => {
    const response = await api.post<ToolAnalysisResponse>('/api/tools/analyze', { prompt });
    return response.data;
  },

  generateTool: async (toolSpec: ToolSpec): Promise<ToolGenerationResponse> => {
    const response = await api.post<ToolGenerationResponse>('/api/tools/generate', {
      tool_spec: toolSpec,
    });
    return response.data;
  },

  listTools: async (): Promise<string[]> => {
    const response = await api.get<{ success: boolean; tools: string[] }>('/api/tools/list');
    return response.data.tools;
  },
  
  getToolSchema: async (toolName: string): Promise<ToolSchema> => {
    const response = await api.get<ToolSchema>(`/api/tools/${toolName}/schema`);
    return response.data;
  },
};

