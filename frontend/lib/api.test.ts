import { describe, expect, it } from 'vitest';
import { formatBytes, formatRelative } from '@/lib/api';

describe('formatBytes', () => {
  it('formats each unit', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
  });

  it('drops the decimal once the value reaches ten', () => {
    expect(formatBytes(15 * 1024)).toBe('15 KB');
  });
});

describe('formatRelative', () => {
  it('renders recent times', () => {
    expect(formatRelative(new Date().toISOString())).toBe('just now');
    expect(formatRelative(new Date(Date.now() - 5 * 60_000).toISOString())).toBe('5m ago');
    expect(formatRelative(new Date(Date.now() - 3 * 3600_000).toISOString())).toBe('3h ago');
    expect(formatRelative(new Date(Date.now() - 2 * 86400_000).toISOString())).toBe('2d ago');
  });

  it('handles absent or unparseable input', () => {
    expect(formatRelative(null)).toBe('—');
    expect(formatRelative('not a date')).toBe('—');
  });
});
