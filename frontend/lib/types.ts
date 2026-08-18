/** Shapes returned by the backend, mirrored from `rag_backend.schemas`. */

export type RuntimeSettings = {
  ollama_url: string;
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
  models: { ollama_url: string; embedding_model: string; llm_model: string };
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
