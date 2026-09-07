import { beforeEach, describe, expect, it } from 'vitest'
import { reset, all, TABLES } from '@/lib/store'
import * as routeApiRuns from '@/app/api/runs/route'
import * as routeApiRunsRunId from '@/app/api/runs/[run_id]/route'
import * as routeApiRunsRunIdParticipants from '@/app/api/runs/[run_id]/participants/route'
import * as routeApiRunsRunIdParticipantsLeave from '@/app/api/runs/[run_id]/participants/leave/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

const validPayload = {
  title: 'Morning 5K',
  datetime: '2026-08-01T07:00:00',
  meeting_location: 'Riverside Park',
  distance: '5K',
  pace_target: '9:00/mi',
  route_notes: 'Out and back on the river path',
}

function req(path: string, method: string, body?: unknown): Request {
  const init: RequestInit = { method }
  if (body !== undefined) {
    init.headers = { 'content-type': 'application/json' }
    init.body = JSON.stringify(body)
  }
  return new Request(`http://test${path}`, init)
}

beforeEach(() => reset())

describe('Create Run', () => {
  it('returns 201 with full run for valid payload', async () => {
    const res = await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))
    expect(res.status).toBe(201)
    const body: any = await res.json()
    expect(typeof body.id).toBe('string')
    expect(body.id).toBeTruthy()
    expect(body.title).toBe('Morning 5K')
    expect(typeof body.datetime).toBe('string')
    expect(body.datetime).toBe('2026-08-01T07:00:00')
    expect(typeof body.meeting_location).toBe('string')
    expect(body.meeting_location).toBe('Riverside Park')
    expect(typeof body.distance).toBe('string')
    expect(body.distance).toBe('5K')
    expect(typeof body.pace_target).toBe('string')
    expect(body.pace_target).toBe('9:00/mi')
    expect(typeof body.route_notes).toBe('string')
    expect(body.route_notes).toBe('Out and back on the river path')
    expect(Array.isArray(body.participants)).toBe(true)
    expect(body.participants).toHaveLength(0)
    expect(typeof body.created_at).toBe('string')
    expect(all(TABLES.Run)).toHaveLength(1)
  })

  it('returns 400 validation_error for blank required fields', async () => {
    const res = await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', { title: '', datetime: '', meeting_location: '' }))
    expect(res.status).toBe(400)
    const body: any = await res.json()
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)).toHaveLength(0)
  })
})

describe('List Runs', () => {
  it('returns empty array when store is empty', async () => {
    const res = await (routeApiRuns.GET as Handler)(req('/api/runs', 'GET'))
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(Array.isArray(body)).toBe(true)
    expect(body).toHaveLength(0)
  })

  it('returns summaries with numeric participant_count', async () => {
    await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))
    const res = await (routeApiRuns.GET as Handler)(req('/api/runs', 'GET'))
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(Array.isArray(body)).toBe(true)
    expect(body).toHaveLength(1)
    const s = body[0]
    expect(typeof s.id).toBe('string')
    expect(s.title).toBe('Morning 5K')
    expect(typeof s.datetime).toBe('string')
    expect(typeof s.meeting_location).toBe('string')
    expect(typeof s.participant_count).toBe('number')
    expect(s.participant_count).toBe(0)
  })

  it('reflects participant_count after a join', async () => {
    const cr: any = await (await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))).json()
    await (routeApiRunsRunIdParticipants.POST as Handler)(
      req(`/api/runs/${cr.id}/participants`, 'POST', { name: 'Alice' }),
      { params: { run_id: cr.id } },
    )
    const res = await (routeApiRuns.GET as Handler)(req('/api/runs', 'GET'))
    const body: any = await res.json()
    expect(body[0].participant_count).toBe(1)
    expect(typeof body[0].participant_count).toBe('number')
  })
})

describe('Run Detail', () => {
  it('returns full run for known id', async () => {
    const cr: any = await (await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))).json()
    const res = await (routeApiRunsRunId.GET as Handler)(req(`/api/runs/${cr.id}`, 'GET'), { params: { run_id: cr.id } })
    expect(res.status).toBe(200)
    const body: any = await res.json()
    expect(body.id).toBe(cr.id)
    expect(body.title).toBe('Morning 5K')
    expect(typeof body.datetime).toBe('string')
    expect(typeof body.meeting_location).toBe('string')
    expect(typeof body.distance).toBe('string')
    expect(typeof body.pace_target).toBe('string')
    expect(typeof body.route_notes).toBe('string')
    expect(Array.isArray(body.participants)).toBe(true)
    expect(typeof body.created_at).toBe('string')
  })

  it('returns 404 run_not_found for unknown id', async () => {
    const res = await (routeApiRunsRunId.GET as Handler)(req('/api/runs/nope', 'GET'), { params: { run_id: 'nope' } })
    expect(res.status).toBe(404)
    const body: any = await res.json()
    expect(body.error.code).toBe('run_not_found')
  })
})

describe('Join Participant', () => {
  it('adds participant and returns name and joined_at', async () => {
    const cr: any = await (await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))).json()
    const res = await (routeApiRunsRunIdParticipants.POST as Handler)(
      req(`/api/runs/${cr.id}/participants`, 'POST', { name: 'Alice' }),
      { params: { run_id: cr.id } },
    )
    expect(res.status).toBe(201)
    const body: any = await res.json()
    expect(typeof body.name).toBe('string')
    expect(body.name).toBe('Alice')
    expect(typeof body.joined_at).toBe('string')
    const row = all(TABLES.Run).find((r: any) => r.id === cr.id)
    expect(row.participants).toHaveLength(1)
  })

  it('rejects empty name with validation_error', async () => {
    const cr: any = await (await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))).json()
    const res = await (routeApiRunsRunIdParticipants.POST as Handler)(
      req(`/api/runs/${cr.id}/participants`, 'POST', { name: '' }),
      { params: { run_id: cr.id } },
    )
    expect(res.status).toBe(400)
    const body: any = await res.json()
    expect(body.error.code).toBe('validation_error')
  })

  it('rejects case-insensitive duplicate with participant_already_exists', async () => {
    const cr: any = await (await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))).json()
    await (routeApiRunsRunIdParticipants.POST as Handler)(
      req(`/api/runs/${cr.id}/participants`, 'POST', { name: 'Alice' }),
      { params: { run_id: cr.id } },
    )
    const res = await (routeApiRunsRunIdParticipants.POST as Handler)(
      req(`/api/runs/${cr.id}/participants`, 'POST', { name: 'alice' }),
      { params: { run_id: cr.id } },
    )
    expect(res.status).toBe(409)
    const body: any = await res.json()
    expect(body.error.code).toBe('participant_already_exists')
    const row = all(TABLES.Run).find((r: any) => r.id === cr.id)
    expect(row.participants).toHaveLength(1)
  })
})

describe('Leave Participant', () => {
  it('removes participant and updates count', async () => {
    const cr: any = await (await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))).json()
    await (routeApiRunsRunIdParticipants.POST as Handler)(
      req(`/api/runs/${cr.id}/participants`, 'POST', { name: 'Alice' }),
      { params: { run_id: cr.id } },
    )
    const res = await (routeApiRunsRunIdParticipantsLeave.POST as Handler)(
      req(`/api/runs/${cr.id}/participants/leave`, 'POST', { name: 'Alice' }),
      { params: { run_id: cr.id } },
    )
    expect(res.status).toBe(200)
    const row = all(TABLES.Run).find((r: any) => r.id === cr.id)
    expect(row.participants).toHaveLength(0)
  })

  it('rejects empty name with validation_error', async () => {
    const cr: any = await (await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))).json()
    const res = await (routeApiRunsRunIdParticipantsLeave.POST as Handler)(
      req(`/api/runs/${cr.id}/participants/leave`, 'POST', { name: '' }),
      { params: { run_id: cr.id } },
    )
    expect(res.status).toBe(400)
    const body: any = await res.json()
    expect(body.error.code).toBe('validation_error')
  })

  it('returns 404 participant_not_found for unknown name', async () => {
    const cr: any = await (await (routeApiRuns.POST as Handler)(req('/api/runs', 'POST', validPayload))).json()
    const res = await (routeApiRunsRunIdParticipantsLeave.POST as Handler)(
      req(`/api/runs/${cr.id}/participants/leave`, 'POST', { name: 'Ghost' }),
      { params: { run_id: cr.id } },
    )
    expect(res.status).toBe(404)
    const body: any = await res.json()
    expect(body.error.code).toBe('participant_not_found')
  })
})