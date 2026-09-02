import { beforeEach, describe, expect, it } from 'vitest'
import { reset, all, TABLES } from '@/lib/store'
import * as routeApiRuns from '@/app/api/runs/route'
import * as routeApiRunsRunId from '@/app/api/runs/[run_id]/route'
import * as routeApiRunsRunIdJoin from '@/app/api/runs/[run_id]/join/route'
import * as routeApiRunsRunIdLeave from '@/app/api/runs/[run_id]/leave/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

beforeEach(() => reset())

async function createRun(overrides: Record<string, string> = {}) {
  const payload = {
    title: 'Sunrise 5K',
    datetime: '2026-09-01T07:00:00',
    meeting_location: 'Riverside Park',
    ...overrides,
  }
  const res = await (routeApiRuns.POST as Handler)(
    new Request('http://test/api/runs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )
  return { res, body: (await res.json().catch(() => ({}))) as any }
}

describe('runs API – behavioral tests', () => {
  // ─── CREATE ───────────────────────────────────────────────────────────

  it('creates a run and it appears in the list', async () => {
    const { res, body } = await createRun()
    expect(res.status).toBe(201)
    expect(body.id).toBeTruthy()
    expect(body.title).toBe('Sunrise 5K')
    expect(body.participants).toEqual([])

    // Appears in list
    const listRes = await (routeApiRuns.GET as Handler)(new Request('http://test/api/runs'))
    expect(listRes.status).toBe(200)
    const list: any = await listRes.json()
    expect(Array.isArray(list)).toBe(true)
    expect(list).toHaveLength(1)
    expect(list[0].id).toBe(body.id)
    expect(list[0].title).toBe('Sunrise 5K')
    expect(list[0].participant_count).toBe(0)
  })

  it('rejects create when a required field is missing', async () => {
    const res = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ title: '', datetime: '2026-09-01T07:00:00', meeting_location: 'Riverside Park' }),
      }),
    )
    expect(res.status).toBe(400)
    const body: any = await res.json()
    expect(body.error).toBeDefined()
    expect(body.error.code).toBe('validation_error')
    expect(typeof body.error.message).toBe('string')
    expect(body.error.message.length).toBeGreaterThan(0)
    // No run persisted
    expect(all(TABLES.Run)).toHaveLength(0)
  })

  // ─── DETAIL ───────────────────────────────────────────────────────────

  it('fetches a run by id and returns full details including participants', async () => {
    const { body: created } = await createRun()

    const res = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${created.id}`),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(200)
    const detail: any = await res.json()
    expect(detail.id).toBe(created.id)
    expect(detail.title).toBe('Sunrise 5K')
    expect(detail.datetime).toBe('2026-09-01T07:00:00')
    expect(detail.meeting_location).toBe('Riverside Park')
    expect(detail.participants).toEqual([])
    expect(detail.created_at).toBeTruthy()
  })

  it('returns 404 with run_not_found for a non-existent run id', async () => {
    const res = await (routeApiRunsRunId.GET as Handler)(
      new Request('http://test/api/runs/does-not-exist'),
      { params: { run_id: 'does-not-exist' } },
    )
    expect(res.status).toBe(404)
    const body: any = await res.json()
    expect(body.error).toBeDefined()
    expect(body.error.code).toBe('run_not_found')
    expect(typeof body.error.message).toBe('string')
    expect(body.error.message.length).toBeGreaterThan(0)
  })

  // ─── JOIN ─────────────────────────────────────────────────────────────

  it('joins a run with a valid name – participant added, count incremented', async () => {
    const { body: run } = await createRun()

    const res = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Alice' }),
      }),
      { params: { run_id: run.id } },
    )
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(body.participants).toContain('Alice')
    expect(body.participants).toHaveLength(1)

    // Store reflects the join
    const rows = all(TABLES.Run)
    expect(rows).toHaveLength(1)
    expect(rows[0].participants).toContain('Alice')

    // List view shows updated count
    const listRes = await (routeApiRuns.GET as Handler)(new Request('http://test/api/runs'))
    const list: any = await listRes.json()
    expect(list[0].participant_count).toBe(1)
  })

  it('rejects join with an empty name', async () => {
    const { body: run } = await createRun()

    const res = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: '' }),
      }),
      { params: { run_id: run.id } },
    )
    expect(res.status).toBe(400)
    const body: any = await res.json()
    expect(body.error).toBeDefined()
    expect(body.error.code).toBe('validation_error')
    expect(typeof body.error.message).toBe('string')
    // No participant added
    const rows = all(TABLES.Run)
    expect(rows[0].participants).toEqual([])
  })

  it('rejects join with a duplicate name (case-insensitive)', async () => {
    const { body: run } = await createRun()

    // First join succeeds
    const first = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Bob' }),
      }),
      { params: { run_id: run.id } },
    )
    expect(first.status).toBe(200)

    // Duplicate (different case) rejected
    const dup = await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'BOB' }),
      }),
      { params: { run_id: run.id } },
    )
    expect(dup.status).toBe(409)
    const body: any = await dup.json()
    expect(body.error).toBeDefined()
    expect(body.error.code).toBe('duplicate_participant')
    expect(typeof body.error.message).toBe('string')
    // Still only one participant
    const rows = all(TABLES.Run)
    expect(rows[0].participants).toHaveLength(1)
  })

  // ─── LEAVE ────────────────────────────────────────────────────────────

  it('leaves a run with a valid name – participant removed, count decremented', async () => {
    const { body: run } = await createRun()

    // Join first
    await (routeApiRunsRunIdJoin.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/join`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Carol' }),
      }),
      { params: { run_id: run.id } },
    )

    // Leave
    const res = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Carol' }),
      }),
      { params: { run_id: run.id } },
    )
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(body.participants).not.toContain('Carol')
    expect(body.participants).toHaveLength(0)

    // Store reflects the leave
    const rows = all(TABLES.Run)
    expect(rows[0].participants).toHaveLength(0)

    // List view shows 0
    const listRes = await (routeApiRuns.GET as Handler)(new Request('http://test/api/runs'))
    const list: any = await listRes.json()
    expect(list[0].participant_count).toBe(0)
  })

  it('returns 404 with participant_not_found when leaving with an unknown name', async () => {
    const { body: run } = await createRun()

    const res = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: 'Nobody' }),
      }),
      { params: { run_id: run.id } },
    )
    expect(res.status).toBe(404)
    const body: any = await res.json()
    expect(body.error).toBeDefined()
    expect(body.error.code).toBe('participant_not_found')
    expect(typeof body.error.message).toBe('string')
    expect(body.error.message.length).toBeGreaterThan(0)
  })

  it('rejects leave with an empty name', async () => {
    const { body: run } = await createRun()

    const res = await (routeApiRunsRunIdLeave.POST as Handler)(
      new Request(`http://test/api/runs/${run.id}/leave`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name: '' }),
      }),
      { params: { run_id: run.id } },
    )
    expect(res.status).toBe(400)
    const body: any = await res.json()
    expect(body.error).toBeDefined()
    expect(body.error.code).toBe('validation_error')
    expect(typeof body.error.message).toBe('string')
  })
})