export {};

declare global {
  interface Window {
    desktop?: {
      platform: string;
      isElectron: boolean;
      apiRequest: <T = unknown>(request: {
        path: string;
        method?: 'GET' | 'POST' | 'DELETE';
        body?: unknown;
      }) => Promise<{
        ok: boolean;
        status: number;
        data?: T;
        error?: string;
      }>;
      selectDocuments: () => Promise<string[]>;
    };
  }
}
