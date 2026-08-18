import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: {
    // Mirrors the tsconfig "@/*" alias.
    alias: { '@': path.resolve(import.meta.dirname, '.') },
  },
  test: {
    // Component tests need a DOM; the pure helpers are happy either way.
    environment: 'jsdom',
    globals: true,
    include: ['lib/**/*.test.ts', 'app/**/*.test.tsx'],
  },
});
