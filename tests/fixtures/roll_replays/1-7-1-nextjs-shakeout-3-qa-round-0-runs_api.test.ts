import { beforeEach, describe, expect, it } from 'vitest'
import { reset, all, TABLES } from '@/lib/store'
import * as routeApiRuns from '@/app/api/runs/route'
import * as routeApiRunsRunId from '@/app/api/runs/[run_id]/route'
import * as routeApiRunsRunIdJoin from '@/app/api/runs/[run_id]/join/route'
import * as routeApiRunsRunIdLeave from '@/app/api/runs/[run_id]/leave/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

beforeEach(() => reset())

async function createRun(payload: Record<string, unknown>): Promise<{ res: Response; body: any }> {
  const res = await (routeApiRuns.POST as Handler)(
    new Request('http://test/api/runs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )
  const body: any = await res.json().catch(() => ({}))
  return { res, body }
}

describe('Create (POST /api/runs)', () => {
  it('returns a run with id, title, datetime, location, and empty participants', async () => {
    const { res, body } = await createRun({
      title: 'Sunrise Run',
      datetime: '2026-09-15T06:00:00',
      location: 'Riverside Park',
    })
    expect(res.status).toBe(201)
    expect(body.id).toBeTruthy()
    expect(body.title).toBe('Sunrise Run')
    expect(body.datetime).toBe('2026-09-15T06:00:00')
    expect(body.location).toBe('Riverside Park')
    expect(body.participants).toEqual([])
    expect(typeof body.createdAt).toBe('string')
    expect(all(TABLES.Run)).toHaveLength(1)
    const row = all(TABLES.Run)[0]
    expect(row.title).toBe('Sunrise Run')
    expect(row.participants).toEqual([])
  })

  it('accepts optional fields (distance, pace, routeNotes, capacity)', async () => {
    const { res, body } = await createRun({
      title: 'Long Loop',
      datetime: '2026-10-01T07:00:00',
      location: 'Lakeside Trail',
      distance: '10K',
      pace: '9:00/mi',
      routeNotes: 'Stay on the main path',
      capacity: 20,
    })
    expect(res.status).toBe(201)
    expect(body.distance).toBe('10K')
    expect(body.pace).toBe('9:00/mi')
    expect(body.routeNotes).toBe('Stay on the main path')
    expect(body.capacity).toBe(20)
    expect(body.participants).toEqual([])
  })

  it('rejects when title is missing', async () => {
    const { res, body } = await createRun({
      datetime: '2026-09-15T06:00:00',
      location: 'Riverside Park',
    })
    expect(res.status).toBe(400)
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)).toHaveLength(0)
  })

  it('rejects when datetime is missing', async () => {
    const { res, body } = await createRun({
      title: 'Sunrise Run',
      location: 'Riverside Park',
    })
    expect(res.status).toBe(400)
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)).toHaveLength(0)
  })

  it('rejects when location is missing', async () => {
    const { res, body } = await createRun({
      title: 'Sunrise Run',
      datetime: '2026-09-15T06:00:00',
    })
    expect(res.status).toBe(400)
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)).toHaveLength(0)
  })
})

describe('List (GET /api/runs)', () => {
  it('returns an empty list when no runs exist', async () => {
    const res = await (routeApiRuns.GET as Handler)(new Request('http://test/api/runs'))
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(body).toEqual([])
  })

  it('returns created runs with their participants', async () => {
    const a = await createRun({ title: 'A', datetime: '2026-09-01T06:00:00', location: 'Park A' })
    const b = await createRun({ title: 'B', datetime: '2026-09-02T06:00:00', location: 'Park B' })
    const joinRes = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${a.body.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' }),
      }),
      { params: { run_id: a.body.id } },
    )
    expect(joinRes.status).toBe(200)

    const res = await (routeApiRuns.GET as Handler)(new Request('http://test/api/runs'))
    expect(res.status).toBe(200)
    const body: any[] = await res.json()
    expect(body).toHaveLength(2)

    const runA = body.find(r => r.id === a.body.id)!
    expect(runA).toBeTruthy()
    expect(runA.participants).toEqual(['Alice'])

    const runB = body.find(r => r.id === b.body.id)!
    expect(runB).toBeTruthy()
    expect(runB.participants).toEqual([])
  })
})

describe('Detail (GET /api/runs/{run_id})', () => {
  it('returns a single run matching the created payload', async () => {
    const { body: created } = await createRun({
      title: 'Solo Shakedown',
      datetime: '2026-11-20T18:00:00',
      location: 'Hilltop Loop',
      distance: '5K',
      pace: '8:30/mi',
    })
    const res = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${created.id}`),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(body.id).toBe(created.id)
    expect(body.title).toBe('Solo Shakedown')
    expect(body.datetime).toBe('2026-11-20T18:00:00')
    expect(body.location).toBe('Hilltop Loop')
    expect(body.distance).toBe('5K')
    expect(body.pace).toBe('8:30/mi')
    expect(body.participants).toEqual([])
  })

  it('returns not-found for an unknown id', async () => {
    const res = await (routeApiRunsRunId.GET as Handler)(
      new Request('http://test/api/runs/does-not-exist'),
      { params: { run_id: 'does-not-exist' } },
    )
    expect(res.status).toBe(404)
    const body: any = await res.json()
    expect(body.error.code).toBe('run_not_found')
  })
})

describe('Join (POST /api/runs/{run_id}/join)', () => {
  it('adds the participant and updates the count', async () => {
    const { body: created } = await createRun({
      title: 'Group Run',
      datetime: '2026-09-10T06:30:00',
      location: 'Riverside',
    })
    const res = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(body.id).toBe(created.id)
    expect(body.participants).toEqual(['Alice'])

    const row = all(TABLES.Run).find(r => r.id === created.id)!
    expect(row).toBeTruthy()
    expect(row.participants).toEqual(['Alice'])
  })

  it('accumulates multiple distinct participants', async () => {
    const { body: created } = await createRun({
      title: 'Group Run',
      datetime: '2026-09-10T06:30:00',
      location: 'Riverside',
    })
    for (const name of ['Alice', 'Bob', 'Carol']) {
      const res = await (routeApiRunsRunIdJoin.POST as Handler)(
        new Request(`http://test/api/runs/${created.id}/join`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ name }),
        }),
        { params: { run_id: created.id } },
      )
      expect(res.status).toBe(200)
    }
    const row = all(TABLES.Run).find(r => r.id === created.id)!
    expect(row.participants).toEqual(['Alice', 'Bob', 'Carol'])
  })

  it('rejects an empty name', async () => {
    const { body: created } = await createRun({
      title: 'Group Run',
      datetime: '2026-09-10T06:30:00',
      location: 'Riverside',
    })
    const res = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: '' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(400)
    const body: any = await res.json()
    expect(body.error.code).toBe('validation_error')
    const row = all(TABLES.Run).find(r => r.id === created.id)!
    expect(row.participants).toEqual([])
  })

  it('rejects duplicate name case-insensitively', async () => {
    const { body: created } = await createRun({
      title: 'Group Run',
      datetime: '2026-09-10T06:30:00',
      location: 'Riverside',
    })
    const first = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(first.status).toBe(200)

    const dup = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'alice' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(dup.status).toBe(409)
    const body: any = await dup.json()
    expect(body.error.code).toBe('duplicate_participant')

    const row = all(TABLES.Run).find(r => r.id === created.id)!
    expect(row.participants).toEqual(['Alice'])
  })
})

describe('Leave (POST /api/runs/{run_id}/leave)', () => {
  it('removes the named participant and updates the count', async () => {
    const { body: created } = await createRun({
      title: 'Group Run',
      datetime: '2026-09-10T06:30:00',
      location: 'Riverside',
    })
    await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' }),
      }),
      { params: { run_id: created.id } },
    )
    await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Bob' }),
      }),
      { params: { run_id: created.id } },
    )

    const res = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(body.id).toBe(created.id)
    expect(body.participants).toEqual(['Bob'])

    const row = all(TABLES.Run).find(r => r.id === created.id)!
    expect(row.participants).toEqual(['Bob'])
  })

  it('rejects an unknown name', async () => {
    const { body: created } = await createRun({
      title: 'Group Run',
      datetime: '2026-09-10T06:30:00',
      location: 'Riverside',
    })
    const res = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'NotHere' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(404)
    const body: any = await res.json()
    expect(body.error.code).toBe('participant_not_found')
  })

  it('rejects an empty name', async () => {
    const { body: created } = await createRun({
      title: 'Group Run',
      datetime: '2026-09-10T06:30:00',
      location: 'Riverside',
    })
    const res = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: '' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(400)
    const body: any = await res.json()
    expect(body.error.code).toBe('validation_error')
  })
})