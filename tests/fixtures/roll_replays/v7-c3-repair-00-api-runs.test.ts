import { describe, it, expect, beforeEach, vi } from 'vitest';
import { reset, all, insert, find, TABLES, nextId } from '@/lib/store';
import { api } from '@/lib/api';
import { ApiError } from '@/lib/errors';

describe('API Runs - Core Behavior', () => {
  beforeEach(() => {
    reset();
    vi.restoreAllMocks();
  });

  it('lists all runs from the store', async () => {
    const runId = nextId();
    insert(TABLES.Run, {
      id: runId,
      title: 'Morning 5K',
      datetime: '2024-05-10T07:00:00',
      location: 'Riverside Park',
      participants: []
    });

    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => all(TABLES.Run)
    } as Response);

    const runs = await api<any[]>('/api/runs');
    expect(runs).toHaveLength(1);
    expect(runs[0].id).toBe(runId);
    expect(runs[0].title).toBe('Morning 5K');
  });

  it('creates a run with required fields and returns the new entity', async () => {
    const payload = {
      title: 'Evening Trail Run',
      datetime: '2024-05-11T18:00:00',
      location: 'Hilltop Reserve'
    };
    const newId = nextId();
    const createdAt = new Date().toISOString();

    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...payload, id: newId, participants: [], createdAt })
    } as Response);

    const created = await api('/api/runs', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    expect(created.id).toBe(newId);
    expect(created.title).toBe('Evening Trail Run');
    expect(created.participants).toEqual([]);
  });

  it('rejects run creation when required fields are empty', async () => {
    const payload = { title: '', datetime: '', location: '' };

    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ code: 'validation_error', detail: 'Missing required fields' })
    } as Response);

    await expect(api('/api/runs', {
      method: 'POST',
      body: JSON.stringify(payload)
    })).rejects.toThrow(ApiError);
  });

  it('returns run detail for a valid id', async () => {
    const runId = nextId();
    insert(TABLES.Run, {
      id: runId,
      title: 'Detail Target',
      datetime: '2024-05-12T09:00:00',
      location: 'Downtown Loop',
      participants: []
    });

    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => find(TABLES.Run, runId)
    } as Response);

    const detail = await api(`/api/runs/${runId}`);
    expect(detail.id).toBe(runId);
    expect(detail.title).toBe('Detail Target');
    expect(detail.location).toBe('Downtown Loop');
  });

  it('throws run_not_found for unknown run id', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ code: 'run_not_found', detail: 'Run not found' })
    } as Response);

    await expect(api('/api/runs/nonexistent-id')).rejects.toThrow(ApiError);
  });

  it('joins a run and updates participant list', async () => {
    const runId = nextId();
    insert(TABLES.Run, {
      id: runId,
      title: 'Joinable Run',
      datetime: '2024-05-13T10:00:00',
      location: 'Lakeside',
      participants: []
    });

    const updatedRun = {
      id: runId,
      title: 'Joinable Run',
      datetime: '2024-05-13T10:00:00',
      location: 'Lakeside',
      participants: [{ name: 'Alice', joinedAt: new Date().toISOString() }]
    };

    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => updatedRun
    } as Response);

    const result = await api(`/api/runs/${runId}/join`, {
      method: 'POST',
      body: JSON.stringify({ name: 'Alice' })
    });

    expect(result.participants).toHaveLength(1);
    expect(result.participants[0].name).toBe('Alice');
  });

  it('rejects duplicate participant join with 409', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ code: 'duplicate_participant', detail: 'Participant already joined this run' })
    } as Response);

    await expect(api('/api/runs/abc123/join', {
      method: 'POST',
      body: JSON.stringify({ name: 'Bob' })
    })).rejects.toThrow(ApiError);
  });

  it('leaves a run and removes participant', async () => {
    const runId = nextId();
    insert(TABLES.Run, {
      id: runId,
      title: 'Leavable Run',
      datetime: '2024-05-14T11:00:00',
      location: 'Mountain Trail',
      participants: [{ name: 'Charlie', joinedAt: '2024-05-14T09:00:00' }]
    });

    const updatedRun = {
      id: runId,
      title: 'Leavable Run',
      datetime: '2024-05-14T11:00:00',
      location: 'Mountain Trail',
      participants: []
    };

    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: true,
      json: async () => updatedRun
    } as Response);

    const result = await api(`/api/runs/${runId}/leave`, {
      method: 'POST',
      body: JSON.stringify({ name: 'Charlie' })
    });

    expect(result.participants).toHaveLength(0);
  });

  it('rejects leave for unknown participant with 404', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ code: 'participant_not_found', detail: 'Participant not found on this run' })
    } as Response);

    await expect(api('/api/runs/xyz789/leave', {
      method: 'POST',
      body: JSON.stringify({ name: 'Nobody' })
    })).rejects.toThrow(ApiError);
  });
});