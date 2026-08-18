import { describe, expect, it } from 'vitest';
import {
  JOB_STATUSES,
  explainErrorCode,
  isTerminal,
  progressFraction,
} from '@/lib/jobs';

describe('isTerminal', () => {
  it('treats finished states as terminal', () => {
    expect(isTerminal('complete')).toBe(true);
    expect(isTerminal('failed')).toBe(true);
    expect(isTerminal('cancelled')).toBe(true);
  });

  it('treats in-flight states as non-terminal', () => {
    expect(isTerminal('queued')).toBe(false);
    expect(isTerminal('embedding')).toBe(false);
  });
});

describe('progressFraction', () => {
  it('runs from zero at queued to one at complete', () => {
    expect(progressFraction('queued')).toBe(0);
    expect(progressFraction('complete')).toBe(1);
  });

  it('increases monotonically along the pipeline', () => {
    const pipeline = ['queued', 'parsing', 'chunking', 'embedding', 'committing', 'complete'] as const;
    const values = pipeline.map(progressFraction);
    expect(values).toEqual([...values].sort((a, b) => a - b));
  });

  it('reports no progress for failed and cancelled', () => {
    // Matches the backend: a stalled bar misleads more than an empty one.
    expect(progressFraction('failed')).toBe(0);
    expect(progressFraction('cancelled')).toBe(0);
  });
});

describe('explainErrorCode', () => {
  it('explains the codes the backend actually emits', () => {
    expect(explainErrorCode('embedding_failed')).toContain('embedding provider');
    expect(explainErrorCode('unsupported_format')).toContain('cannot be read');
    expect(explainErrorCode('duplicate')).toContain('Already indexed');
  });

  it('does not attribute an embedding failure to Ollama', () => {
    // Embeddings run in-process by default, so naming Ollama would misdirect.
    expect(explainErrorCode('embedding_failed')).not.toContain('Ollama');
  });

  it('returns null for unknown or absent codes', () => {
    expect(explainErrorCode(null)).toBeNull();
    expect(explainErrorCode('something_new')).toBeNull();
  });
});

describe('JOB_STATUSES', () => {
  it('matches the backend state machine exactly', () => {
    expect([...JOB_STATUSES]).toEqual([
      'queued',
      'parsing',
      'chunking',
      'embedding',
      'committing',
      'complete',
      'failed',
      'cancelled',
    ]);
  });
});
