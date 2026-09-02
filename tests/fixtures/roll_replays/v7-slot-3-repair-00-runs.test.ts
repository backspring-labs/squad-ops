import { describe, it, beforeEach, expect } from 'vitest';
import { reset, insert, all, find, TABLES, nextId } from '@/lib/store';
import { api } from '@/lib/api';

describe('Runs API', () => {
  beforeEach(() => {
    reset();
  });

  describe('Happy Paths', () => {
    it('should create a run and return it with an id', async () => {
      const res = await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Morning Run', datetime: '2024-01-01T08:00:00', location: 'City Park' }),
      });
      expect(res).toHaveProperty('id');
      expect(res.title).toBe('Morning Run');
    });

    it('should list all created runs', async () => {
      await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Run 1', datetime: '2024-01-01', location: 'A' }),
      });
      const list = await api('/api/runs');
      expect(Array.isArray(list)).toBe(true);
      expect(list.length).toBe(1);
    });

    it('should get run detail by id', async () => {
      const created = await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Detail Run', datetime: '2024-01-01', location: 'B' }),
      });
      const detail = await api(`/api/runs/${created.id}`);
      expect(detail.id).toBe(created.id);
      expect(detail.title).toBe('Detail Run');
    });

    it('should join a run with a participant name', async () => {
      const created = await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Join Run', datetime: '2024-01-01', location: 'C' }),
      });
      const joinRes = await api(`/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' }),
      });
      expect(joinRes.participants).toContain('Alice');
    });

    it('should leave a run with a participant name', async () => {
      const created = await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Leave Run', datetime: '2024-01-01', location: 'D' }),
      });
      await api(`/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Bob' }),
      });
      const leaveRes = await api(`/api/runs/${created.id}/leave`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Bob' }),
      });
      expect(leaveRes.participants).not.toContain('Bob');
    });
  });

  describe('Error Paths', () => {
    it('should reject duplicate participant name with 409', async () => {
      const created = await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Dup Run', datetime: '2024-01-01', location: 'E' }),
      });
      await api(`/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Charlie' }),
      });
      await expect(
        api(`/api/runs/${created.id}/join`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: 'Charlie' }),
        })
      ).rejects.toMatchObject({ code: 'duplicate_name' });
    });

    it('should reject empty participant name with 400', async () => {
      const created = await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Empty Name Run', datetime: '2024-01-01', location: 'F' }),
      });
      await expect(
        api(`/api/runs/${created.id}/join`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: '' }),
        })
      ).rejects.toMatchObject({ code: 'validation_error' });
    });

    it('should return 404 for run not found', async () => {
      await expect(api('/api/runs/nonexistent-id')).rejects.toMatchObject({ code: 'run_not_found' });
    });

    it('should return 404 for participant not found on leave', async () => {
      const created = await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Leave Not Found Run', datetime: '2024-01-01', location: 'G' }),
      });
      await expect(
        api(`/api/runs/${created.id}/leave`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: 'Nobody' }),
        })
      ).rejects.toMatchObject({ code: 'participant_not_found' });
    });
  });
});