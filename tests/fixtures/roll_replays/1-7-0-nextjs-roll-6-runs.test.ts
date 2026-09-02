import { beforeEach, describe, expect, it } from 'vitest'
import { reset, all, TABLES } from '@/lib/store'
import * as routeApiRuns from '@/app/api/runs/route'
import * as routeApiRunsRunId from '@/app/api/runs/[run_id]/route'
import * as routeApiRunsRunIdJoin from '@/app/api/runs/[run_id]/join/route'
import * as routeApiRunsRunIdLeave from '@/app/api/runs/[run_id]/leave/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

const VALID_PAYLOAD = { title: 'Sunrise Loop', datetime: '2026-08-01T08:00:00', meeting_location: 'Riverside Park' }

async function post(handler: Handler, url: string, payload: unknown, ctx?: unknown) {
  return handler(
    new Request(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) }),
    ctx,
  )
}

async function get(handler: Handler, url: string, ctx?: unknown) {
  return handler(new Request(url), ctx)
}

beforeEach(() => reset())

describe('POST /api/runs', () => {
  it('creates a run and returns the created entity', async () => {
    const res = await post(routeApiRuns.POST, 'http://test/api/runs', VALID_PAYLOAD)
    expect(res.status).toBe(201)
    const body = (await res.json()) as any
    expect(body.id).toBeTruthy()
    expect(body.title).toBe(VALID_PAYLOAD.title)
    expect(body.datetime).toBe(VALID_PAYLOAD.datetime)
    expect(body.meeting_location).toBe(VALID_PAYLOAD.meeting_location)
    expect(body.participants).toEqual([])
    expect(body.created_at).toBeTruthy()
    expect(all(TABLES.Run)).toHaveLength(1)
  })

  it('rejects a payload missing a required field with validation_error', async () => {
    const res = await post(routeApiRuns.POST, 'http://test/api/runs', { title: '', datetime: '2026-08-01T08:00:00', meeting_location: 'Riverside Park' })
    expect(res.status).toBe(400)
    const body = (await res.json()) as any
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)).toHaveLength(0)
  })
})

describe('GET /api/runs', () => {
  it('returns an empty list when no runs exist', async () => {
    const res = await get(routeApiRuns.GET, 'http://test/api/runs')
    expect(res.status).toBe(200)
    const body = (await res.json()) as any
    expect(Array.isArray(body)).toBe(true)
    expect(body).toHaveLength(0)
  })

  it('returns the created run after a create', async () => {
    const created = (await (await post(routeApiRuns.POST, 'http://test/api/runs', VALID_PAYLOAD)).json()) as any
    const res = await get(routeApiRuns.GET, 'http://test/api/runs')
    expect(res.status).toBe(200)
    const body = (await res.json()) as any
    expect(body).toHaveLength(1)
    expect(body[0].id).toBe(created.id)
    expect(body[0].title).toBe(VALID_PAYLOAD.title)
  })
})

describe('GET /api/runs/{run_id}', () => {
  it('returns the run for a valid id', async () => {
    const created = (await (await post(routeApiRuns.POST, 'http://test/api/runs', VALID_PAYLOAD)).json()) as any
    const res = await get(routeApiRunsRunId.GET, `http://test/api/runs/${created.id}`, { params: { run_id: created.id } })
    expect(res.status).toBe(200)
    const body = (await res.json()) as any
    expect(body.id).toBe(created.id)
    expect(body.title).toBe(VALID_PAYLOAD.title)
  })

  it('returns run_not_found for an unknown id', async () => {
    const res = await get(routeApiRunsRunId.GET, 'http://test/api/runs/nope', { params: { run_id: 'nope' } })
    expect(res.status).toBe(404)
    const body = (await res.json()) as any
    expect(body.error.code).toBe('run_not_found')
    expect(all(TABLES.Run)).toHaveLength(0)
  })
})

describe('POST /api/runs/{run_id}/join', () => {
  it('adds a participant by name', async () => {
    const created = (await (await post(routeApiRuns.POST, 'http://test/api/runs', VALID_PAYLOAD)).json()) as any
    const ctx = { params: { run_id: created.id } }
    const res = await post(routeApiRunsRunIdJoin.POST, `http://test/api/runs/${created.id}/join`, { name: 'Ada' }, ctx)
    expect(res.status).toBe(200)
    const body = (await res.json()) as any
    expect(body.participants).toContain('Ada')
    expect(all(TABLES.Run)[0].participants).toContain('Ada')
  })

  it('rejects an empty name with validation_error', async () => {
    const created = (await (await post(routeApiRuns.POST, 'http://test/api/runs', VALID_PAYLOAD)).json()) as any
    const ctx = { params: { run_id: created.id } }
    const res = await post(routeApiRunsRunIdJoin.POST, `http://test/api/runs/${created.id}/join`, { name: '' }, ctx)
    expect(res.status).toBe(400)
    const body = (await res.json()) as any
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)[0].participants).toHaveLength(0)
  })

  it('rejects a duplicate participant case-insensitively', async () => {
    const created = (await (await post(routeApiRuns.POST, 'http://test/api/runs', VALID_PAYLOAD)).json()) as any
    const ctx = { params: { run_id: created.id } }
    await post(routeApiRunsRunIdJoin.POST, `http://test/api/runs/${created.id}/join`, { name: 'Ada' }, ctx)
    const res = await post(routeApiRunsRunIdJoin.POST, `http://test/api/runs/${created.id}/join`, { name: 'ada' }, ctx)
    expect(res.status).toBe(409)
    const body = (await res.json()) as any
    expect(body.error.code).toBe('duplicate_participant')
    expect(all(TABLES.Run)[0].participants).toHaveLength(1)
  })
})

describe('POST /api/runs/{run_id}/leave', () => {
  it('removes a participant by name', async () => {
    const created = (await (await post(routeApiRuns.POST, 'http://test/api/runs', VALID_PAYLOAD)).json()) as any
    const ctx = { params: { run_id: created.id } }
    await post(routeApiRunsRunIdJoin.POST, `http://test/api/runs/${created.id}/join`, { name: 'Ada' }, ctx)
    const res = await post(routeApiRunsRunIdLeave.POST, `http://test/api/runs/${created.id}/leave`, { name: 'Ada' }, ctx)
    expect(res.status).toBe(200)
    const body = (await res.json()) as any
    expect(body.participants).not.toContain('Ada')
    expect(body.participants).toHaveLength(0)
  })

  it('rejects an empty name with validation_error', async () => {
    const created = (await (await post(routeApiRuns.POST, 'http://test/api/runs', VALID_PAYLOAD)).json()) as any
    const ctx = { params: { run_id: created.id } }
    await post(routeApiRunsRunIdJoin.POST, `http://test/api/runs/${created.id}/join`, { name: 'Ada' }, ctx)
    const res = await post(routeApiRunsRunIdLeave.POST, `http://test/api/runs/${created.id}/leave`, { name: '' }, ctx)
    expect(res.status).toBe(400)
    const body = (await res.json()) as any
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)[0].participants).toHaveLength(1)
    expect(all(TABLES.Run)[0].participants).toContain('Ada')
  })

  it('returns participant_not_found for a name not on the run', async () => {
    const created = (await (await post(routeApiRuns.POST, 'http://test/api/runs', VALID_PAYLOAD)).json()) as any
    const ctx = { params: { run_id: created.id } }
    await post(routeApiRunsRunIdJoin.POST, `http://test/api/runs/${created.id}/join`, { name: 'Ada' }, ctx)
    const res = await post(routeApiRunsRunIdLeave.POST, `http://test/api/runs/${created.id}/leave`, { name: 'Zoe' }, ctx)
    expect(res.status).toBe(404)
    const body = (await res.json()) as any
    expect(body.error.code).toBe('participant_not_found')
    expect(all(TABLES.Run)[0].participants).toHaveLength(1)
    expect(all(TABLES.Run)[0].participants).toContain('Ada')
  })
})