import { describe, it, expect } from 'vitest';

describe('Agent Platform Smoke', () => {
  it('API module exports expected functions', async () => {
    const { api } = await import('../api');
    expect(api).toBeDefined();
    expect(typeof api.get).toBe('function');
    expect(typeof api.post).toBe('function');
  });

  it('renders without crashing (placeholder)', () => {
    // Basic smoke — does the test runner work?
    expect(1 + 1).toBe(2);
  });
});
