/** Shapes returned by the backend, mirrored from `rag_backend.schemas`. */

export type RuntimeSettings = {
  ollama_url: string;
  generation_provider: 'local' | 'ollama';
  local_llm_model_path: string;
  embedding_model: string;
  llm_model: string;
  temperature: number;
  model_profiles: Record<string, { llm_model: string; embedding_model: string }>;
};

export type SettingsResponse = {
  status: string;
  settings: RuntimeSettings;
};

export type ModelListResponse = {
  status: string;
  ollama_url: string;
  models: Array<{ name: string }>;
  required_models: string[];
  missing_models: string[];
};

export type Diagnostics = {
  status: string;
  runtime: { python_version: string; platform: string };
  paths: { app_data_dir: string; app_db_path: string; chroma_path: string };
  disk: { total_bytes: number; used_bytes: number; free_bytes: number };
  models: {
    ollama_url: string;
    generation_provider: 'local' | 'ollama';
    local_llm_model_path: string;
    embedding_model: string;
    llm_model: string;
  };
  storage: {
    status: string;
    provider: string;
    persistent_path: string;
    writable: boolean;
    error?: string;
  };
  stats: {
    documents_indexed: number;
    queries_processed: number;
    errors: number;
    total_documents: number;
    catalog_documents: number;
    timestamp: string;
  };
};

export type EmbeddingsCapability = {
  status: 'ready' | 'degraded' | 'error' | 'unknown';
  provider: 'local' | 'ollama';
  model: string;
  dimensions: number | null;
  requires_external_software: boolean;
};

export type GenerationCapability = {
  status: 'ready' | 'degraded' | 'error' | 'unknown';
  provider: 'local' | 'ollama';
  model: string;
  model_path?: string;
  requires_ollama?: boolean;
  error?: string;
};

export type Readiness = {
  status: string;
  capabilities: {
    embeddings: EmbeddingsCapability;
    generation: GenerationCapability;
    ollama: { status: string; missing_models?: string[]; url?: string };
    index?: { status: string; rebuild_required: boolean };
    memory?: { documents?: number; catalog_documents?: number };
  };
};
