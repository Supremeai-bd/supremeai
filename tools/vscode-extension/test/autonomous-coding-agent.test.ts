import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { AutonomousCodingAgent } from '../src/services/AutonomousCodingAgent';

describe('AutonomousCodingAgent', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('skips (fallback) when disabled — no cost / no request', async () => {
    const postSpy = vi.spyOn(axios, 'post');
    const agent = new AutonomousCodingAgent({ enabled: false, serverUrl: 'http://x:1' });
    const out = await agent.runTask('task');
    expect(out.status).toBe('skipped');
    expect(out.engine).toBe('fallback');
    expect(postSpy).not.toHaveBeenCalled();
  });

  it('skips when serverUrl is missing', async () => {
    const agent = new AutonomousCodingAgent({ enabled: true, serverUrl: '' });
    const out = await agent.runTask('task');
    expect(out.status).toBe('skipped');
  });

  it('runs upstream flow when enabled + configured', async () => {
    vi.spyOn(axios, 'post')
      .mockResolvedValueOnce({ data: { id: 's1' } } as never)
      .mockResolvedValue({ data: {} } as never);
    vi.spyOn(axios, 'get').mockResolvedValue({
      data: [
        { message: { event: 'assistant', args: { content: 'analyzing auth module' } } },
        { message: { event: 'done', args: { content: 'fixed in auth' } } },
      ],
    } as never);

    const agent = new AutonomousCodingAgent({ enabled: true, serverUrl: 'http://localhost:3001' });
    const out = await agent.runTask('fix the bug in auth', '/repo');

    expect(out.status).toBe('ok');
    expect(out.engine).toBe('upstream');
    expect(out.sessionId).toBe('s1');
    expect(out.result).toContain('fixed in auth');
    expect(axios.post).toHaveBeenCalledTimes(2);
  });

  it('returns a clean error on upstream failure', async () => {
    vi.spyOn(axios, 'post').mockRejectedValue(new Error('server down'));
    const agent = new AutonomousCodingAgent({ enabled: true, serverUrl: 'http://localhost:3001' });
    const out = await agent.runTask('task');
    expect(out.status).toBe('error');
    expect(out.engine).toBe('upstream');
    expect(out.error).toContain('server down');
  });
});
