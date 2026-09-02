import { describe, it, beforeEach, expect } from 'vitest'
import { api } from '@/lib/api'
import { reset, TABLES, all } from '@/lib/store'

describe('Runs API Integration', () => {
  beforeEach(() => {
    // Isolate state between tests using the store reset fixture
    reset()
  })

  it('happy path: create, list, detail, join, leave', async () => {
    const runPayload = {
      title: 'Sunrise 5K',
      datetime: '2023-10-25T07:00:00',
      location: 'Central Park Loop'
    }

    // 1. Create run
    const created = await api('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(runPayload)
    })
    expect(created).toHaveProperty('id')
    const runId = created.id
    expect(created.title).toBe(runPayload.title)
    expect(Array.isArray(created.participants)).toBe(true)
    expect(created.participants.length).toBe(0)

    // Verify store mutation
    const storeRuns = all(TABLES.Run)
    expect(storeRuns.length).toBe(1)
    expect(storeRuns[0].id).toBe(runId)

    // 2. List runs
    const runs = await api('/api/runs')
    expect(Array.isArray(runs)).toBe(true)
    expect(runs.length).toBe(1)
    expect(runs[0].id).toBe(runId)

    // 3. Detail run
    const detail = await api(`/api/runs/${runId}`)
    expect(detail.id).toBe(runId)
    expect(detail.title).toBe('Sunrise 5K')
    expect(detail.participants.length).toBe(0)

    // 4. Join run
    const joined = await api(`/api/runs/${runId}/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Alice' })
    })
    expect(joined.participants).toContain('Alice')
    expect(joined.participants.length).toBe(1)

    // 5. Leave run
    const left = await api(`/api/runs/${runId}/leave`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Alice' })
    })
    expect(left.participants).not.toContain('Alice')
    expect(left.participants.length).toBe(0)

    // Verify store reflects removal
    const finalRun = all(TABLES.Run).find(r => r.id === runId)
    expect(finalRun).toBeDefined()
    expect(Array.isArray(finalRun?.participants)).toBe(true)
    expect((finalRun as any).participants.length).toBe(0)
  })

  it('rejects duplicate participant join with appropriate error', async () => {
    const created = await api('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Dup Prevention Run',
        datetime: '2023-10-26T08:00:00',
        location: 'Riverside Trail'
      })
    })
    const runId = created.id

    // First join succeeds
    await api(`/api/runs/${runId}/join`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Bob' })
    })

    // Second join with same name should fail
    let err: unknown
    try {
      await api(`/api/runs/${runId}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Bob' })
      })
    } catch (e) {
      err = e
    }

    expect(err).toBeDefined()
  })

  it('rejects create request with missing required fields', async () => {
    let err: unknown
    try {
      await api('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          datetime: '2023-10-27T09:00:00',
          location: 'Hill Park'
          // title is missing
        })
      })
    } catch (e) {
      err = e
    }

    expect(err).toBeDefined()
  })

  it('rejects join with empty participant name', async () => {
    const created = await api('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Validation Run',
        datetime: '2023-10-28T07:30:00',
        location: 'City Loop'
      })
    })
    const runId = created.id

    let err: unknown
    try {
      await api(`/api/runs/${runId}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: '' })
      })
    } catch (e) {
      err = e
    }

    expect(err).toBeDefined()
  })

  it('rejects leave for participant not on run', async () => {
    const created = await api('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Leave Validation',
        datetime: '2023-10-29T10:00:00',
        location: 'Beach Boardwalk'
      })
    })
    const runId = created.id

    let err: unknown
    try {
      await api(`/api/runs/${runId}/leave`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'UnknownRunner' })
      })
    } catch (e) {
      err = e
    }

    expect(err).toBeDefined()
  })

  it('returns error for unknown run id on detail, join, and leave', async () => {
    const fakeId = 'non-existent-run-id'

    // Detail
    let errDetail: unknown
    try {
      await api(`/api/runs/${fakeId}`)
    } catch (e) {
      errDetail = e
    }
    expect(errDetail).toBeDefined()

    // Join
    let errJoin: unknown
    try {
      await api(`/api/runs/${fakeId}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' })
      })
    } catch (e) {
      errJoin = e
    }
    expect(errJoin).toBeDefined()

    // Leave
    let errLeave: unknown
    try {
      await api(`/api/runs/${fakeId}/leave`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' })
      })
    } catch (e) {
      errLeave = e
    }
    expect(errLeave).toBeDefined()
  })
})