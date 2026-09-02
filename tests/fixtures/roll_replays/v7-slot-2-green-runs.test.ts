import { beforeEach, describe, expect, it } from 'vitest'
import { reset, all, TABLES, insert } from '@/lib/store'
import * as routeApiRuns from '@/app/api/runs/route'
import * as routeApiRunsRunId from '@/app/api/runs/[run_id]/route'
import * as routeApiRunsRunIdJoin from '@/app/api/runs/[run_id]/join/route'
import * as routeApiRunsRunIdLeave from '@/app/api/runs/[run_id]/leave/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

beforeEach(() => reset())

describe('CRUD lifecycle', () => {
  it('create run, list it, view detail, join, leave', async () => {
    // --- Create ---
    const createRes = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: 'Morning 5K',
          dateTime: '2026-09-15T07:00:00',
          location: 'Central Park',
          distance: '5K',
        }),
      }),
    )
    expect(createRes.status).toBe(201)
    const run: any = await createRes.json()
    expect(run.id).toBeTruthy()
    expect(run.title).toBe('Morning 5K')
    expect(run.dateTime).toBe('2026-09-15T07:00:00')
    expect(run.location).toBe('Central Park')
    expect(run.distance).toBe('5K')
    expect(all(TABLES.Run)).toHaveLength(1)

    // --- List ---
    const listRes = await (routeApiRuns.GET as Handler)(
      new Request('http://test/api/runs'),
    )
    expect(listRes.status).toBe(200)
    const listBody: any = await listRes.json()
    expect(Array.isArray(listBody)).toBe(true)
    expect(listBody).toHaveLength(1)
    expect(listBody[0].id).toBe(run.id)

    // --- Detail ---
    const detailRes = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${run.id}`),
      { params: { run_id: run.id } },
    )
    expect(detailRes.status).toBe(200)
    const detailBody: any = await detailRes.json()
    expect(detailBody.id).toBe(run.id)
    expect(detailBody.title).toBe('Morning 5K')
    expect(Array.isArray(detailBody.participants)).toBe(true)
    expect(detailBody.participants).toHaveLength(0)

    // --- Join ---
    const joinRes = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' }),
      }),
      { params: { run_id: run.id } },
    )
    expect(joinRes.status).toBe(200)
    const joinBody: any = await joinRes.json()
    expect(joinBody.participants).toContain('Alice')

    // Verify store reflects participant
    const storeRunsAfterJoin = all(TABLES.Run)
    expect(storeRunsAfterJoin).toHaveLength(1)
    expect(storeRunsAfterJoin[0].participants).toContain('Alice')

    // --- Leave ---
    const leaveRes = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' }),
      }),
      { params: { run_id: run.id } },
    )
    expect(leaveRes.status).toBe(200)
    const leaveBody: any = await leaveRes.json()
    expect(leaveBody.participants).not.toContain('Alice')

    // Verify store reflects removal
    const storeRunsAfterLeave = all(TABLES.Run)
    expect(storeRunsAfterLeave[0].participants).toHaveLength(0)
  })
})

describe('validation rejections', () => {
  it('rejects create with empty title', async () => {
    const res = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: '',
          dateTime: '2026-09-15T07:00:00',
          location: 'Park',
        }),
      }),
    )
    expect(res.status).toBe(422)
    const body: any = await res.json()
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)).toHaveLength(0)
  })

  it('rejects create with empty dateTime', async () => {
    const res = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: 'Run',
          dateTime: '',
          location: 'Park',
        }),
      }),
    )
    expect(res.status).toBe(422)
    const body: any = await res.json()
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)).toHaveLength(0)
  })

  it('rejects create with empty location', async () => {
    const res = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: 'Run',
          dateTime: '2026-09-15T07:00:00',
          location: '',
        }),
      }),
    )
    expect(res.status).toBe(422)
    const body: any = await res.json()
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)).toHaveLength(0)
  })

  it('rejects join with empty participant name', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: 'Run',
          dateTime: '2026-09-15T07:00:00',
          location: 'Park',
        }),
      }),
    )
    const created: any = await createRes.json()

    const joinRes = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: '' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(joinRes.status).toBe(422)
    const body: any = await joinRes.json()
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)[0].participants).toHaveLength(0)
  })

  it('rejects leave with empty participant name', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: 'Run',
          dateTime: '2026-09-15T07:00:00',
          location: 'Park',
        }),
      }),
    )
    const created: any = await createRes.json()

    const leaveRes = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: '' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(leaveRes.status).toBe(422)
    const body: any = await leaveRes.json()
    expect(body.error.code).toBe('validation_error')
  })
})

describe('missing run handling', () => {
  it('returns 404 when viewing unknown run', async () => {
    const res = await (routeApiRunsRunId.GET as Handler)(
      new Request('http://test/api/runs/nonexistent'),
      { params: { run_id: 'nonexistent' } },
    )
    expect(res.status).toBe(404)
    const body: any = await res.json()
    expect(body.error.code).toBe('run_not_found')
  })

  it('returns 404 when joining unknown run', async () => {
    const res = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request('http://test/api/runs/nonexistent/join', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Bob' }),
      }),
      { params: { run_id: 'nonexistent' } },
    )
    expect(res.status).toBe(404)
    const body: any = await res.json()
    expect(body.error.code).toBe('run_not_found')
  })

  it('returns 404 when leaving unknown run', async () => {
    const res = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request('http://test/api/runs/nonexistent/leave', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Bob' }),
      }),
      { params: { run_id: 'nonexistent' } },
    )
    expect(res.status).toBe(404)
    const body: any = await res.json()
    expect(body.error.code).toBe('run_not_found')
  })
})

describe('participant management edge cases', () => {
  it('rejects duplicate participant on same run', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: 'Run',
          dateTime: '2026-09-15T07:00:00',
          location: 'Park',
        }),
      }),
    )
    const created: any = await createRes.json()

    // First join succeeds
    await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Charlie' }),
      }),
      { params: { run_id: created.id } },
    )

    // Second join with same name fails
    const dupRes = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Charlie' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(dupRes.status).toBe(409)
    const body: any = await dupRes.json()
    expect(body.error.code).toBe('duplicate_participant')

    // Store still has exactly 1 participant
    const storeRuns = all(TABLES.Run)
    expect(storeRuns[0].participants).toHaveLength(1)
    expect(storeRuns[0].participants).toContain('Charlie')
  })

  it('returns 404 when leaving with non-existent participant name', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: 'Run',
          dateTime: '2026-09-15T07:00:00',
          location: 'Park',
        }),
      }),
    )
    const created: any = await createRes.json()

    const leaveRes = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Nobody' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(leaveRes.status).toBe(404)
    const body: any = await leaveRes.json()
    expect(body.error.code).toBe('participant_not_found')
  })

  it('supports multiple distinct participants', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          title: 'Group Run',
          dateTime: '2026-09-15T07:00:00',
          location: 'Trail',
        }),
      }),
    )
    const created: any = await createRes.json()

    // Join three different participants
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
    await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Carol' }),
      }),
      { params: { run_id: created.id } },
    )

    const storeRuns = all(TABLES.Run)
    expect(storeRuns[0].participants).toHaveLength(3)

    // Detail view reflects participant count
    const detailRes = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${created.id}`),
      { params: { run_id: created.id } },
    )
    const detailBody: any = await detailRes.json()
    expect(detailBody.participants).toHaveLength(3)

    // Remove one participant
    const leaveRes = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${created.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Bob' }),
      }),
      { params: { run_id: created.id } },
    )
    expect(leaveRes.status).toBe(200)

    const storeRunsAfter = all(TABLES.Run)
    expect(storeRunsAfter[0].participants).toHaveLength(2)
    expect(storeRunsAfter[0].participants).not.toContain('Bob')
    expect(storeRunsAfter[0].participants).toContain('Alice')
    expect(storeRunsAfter[0].participants).toContain('Carol')
  })

  it('list endpoint returns empty array when no runs exist', async () => {
    const res = await (routeApiRuns.GET as Handler)(
      new Request('http://test/api/runs'),
    )
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(Array.isArray(body)).toBe(true)
    expect(body).toHaveLength(0)
  })
})