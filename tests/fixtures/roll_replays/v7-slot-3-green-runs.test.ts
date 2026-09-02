import { beforeEach, describe, expect, it } from 'vitest'
import { reset, all, insert, TABLES, nextId } from '@/lib/store'
import * as routeApiRuns from '@/app/api/runs/route'
import * as routeApiRunsRunId from '@/app/api/runs/[run_id]/route'
import * as routeApiRunsRunIdJoin from '@/app/api/runs/[run_id]/join/route'
import * as routeApiRunsRunIdLeave from '@/app/api/runs/[run_id]/leave/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

beforeEach(() => reset())

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function makeCreateRequest(
  payload: { title: string; datetime: string; location: string; distance?: string; pace?: string; notes?: string },
) {
  return new Request('http://test/api/runs', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

function makeJoinRequest(runId: string, name: string) {
  return new Request(`http://test/api/runs/${runId}/join`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

function makeLeaveRequest(runId: string, name: string) {
  return new Request(`http://test/api/runs/${runId}/leave`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

// ---------------------------------------------------------------------------
// Happy Path: Full Lifecycle
// ---------------------------------------------------------------------------
describe('happy path: create → list → detail → join → leave', () => {
  it('creates a run, lists it, gets detail, joins, and leaves', async () => {
    // 1. Create run
    const createRes = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({ title: 'Morning 5K', datetime: '2026-09-01T07:00:00', location: 'Central Park' }),
    )
    expect(createRes.status).toBe(201)
    const created = await createRes.json()
    expect(created.id).toBeTruthy()
    expect(created.title).toBe('Morning 5K')

    // 2. List runs — should contain the created run
    const listRes = await (routeApiRuns.GET as Handler)(new Request('http://test/api/runs'))
    expect(listRes.status).toBe(200)
    const listBody = await listRes.json()
    expect(Array.isArray(listBody)).toBe(true)
    expect(listBody).toHaveLength(1)
    expect(listBody[0].id).toBe(created.id)

    // 3. Get run detail
    const detailRes = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${created.id}`),
      { params: { run_id: created.id } },
    )
    expect(detailRes.status).toBe(200)
    const detail = await detailRes.json()
    expect(detail.id).toBe(created.id)
    expect(detail.title).toBe('Morning 5K')
    expect(detail.datetime).toBe('2026-09-01T07:00:00')
    expect(detail.location).toBe('Central Park')
    expect(detail.participants).toEqual([])

    // 4. Join run
    const joinRes = await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest(created.id, 'Alice'),
      { params: { run_id: created.id } },
    )
    expect(joinRes.status).toBe(200)
    const joinBody = await joinRes.json()
    expect(joinBody.id).toBe(created.id)
    expect(joinBody.participants).toContain('Alice')

    // Verify store reflects the join
    const storeRun = all(TABLES.Run).find(r => r.id === created.id)
    expect(storeRun).toBeDefined()
    expect(storeRun.participants).toContain('Alice')

    // 5. Leave run
    const leaveRes = await (routeApiRunsRunIdLeave.POST as Handler)(
      makeLeaveRequest(created.id, 'Alice'),
      { params: { run_id: created.id } },
    )
    expect(leaveRes.status).toBe(200)
    const leaveBody = await leaveRes.json()
    expect(leaveBody.id).toBe(created.id)
    expect(leaveBody.participants).toEqual([])

    // Verify store reflects the leave
    const storeRunAfter = all(TABLES.Run).find(r => r.id === created.id)
    expect(storeRunAfter).toBeDefined()
    expect(storeRunAfter.participants).toEqual([])
  })

  it('supports multiple participants joining and leaving independently', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({ title: 'Group Run', datetime: '2026-09-15T09:00:00', location: 'River Trail' }),
    )
    const created = await createRes.json()

    // Alice joins
    await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest(created.id, 'Alice'),
      { params: { run_id: created.id } },
    )
    // Bob joins
    await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest(created.id, 'Bob'),
      { params: { run_id: created.id } },
    )

    // Detail should show both
    const detailRes = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${created.id}`),
      { params: { run_id: created.id } },
    )
    const detail = await detailRes.json()
    expect(detail.participants).toContain('Alice')
    expect(detail.participants).toContain('Bob')

    // Bob leaves
    await (routeApiRunsRunIdLeave.POST as Handler)(
      makeLeaveRequest(created.id, 'Bob'),
      { params: { run_id: created.id } },
    )

    // Only Alice remains
    const detailRes2 = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${created.id}`),
      { params: { run_id: created.id } },
    )
    const detail2 = await detailRes2.json()
    expect(detail2.participants).toContain('Alice')
    expect(detail2.participants).not.toContain('Bob')
  })

  it('includes optional fields when provided on create', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({
        title: 'Tempo Run',
        datetime: '2026-10-01T06:30:00',
        location: 'Track',
        distance: '5K',
        pace: '5:00/km',
        notes: 'Bring water',
      }),
    )
    expect(createRes.status).toBe(201)
    const created = await createRes.json()
    expect(created.distance).toBe('5K')
    expect(created.pace).toBe('5:00/km')
    expect(created.notes).toBe('Bring water')
  })
})

// ---------------------------------------------------------------------------
// Error Path: Validation & Not-Found
// ---------------------------------------------------------------------------
describe('error path: validation rejections', () => {
  it('rejects create with empty title (400)', async () => {
    const res = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({ title: '', datetime: '2026-09-01T07:00:00', location: 'Park' }),
    )
    expect(res.status).toBe(400)
    const body = await res.json()
    expect(body.error.code).toBe('validation_error')
    expect(all(TABLES.Run)).toHaveLength(0)
  })

  it('rejects create with empty datetime (400)', async () => {
    const res = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({ title: 'Run', datetime: '', location: 'Park' }),
    )
    expect(res.status).toBe(400)
    const body = await res.json()
    expect(body.error.code).toBe('validation_error')
  })

  it('rejects create with empty location (400)', async () => {
    const res = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({ title: 'Run', datetime: '2026-09-01T07:00:00', location: '' }),
    )
    expect(res.status).toBe(400)
    const body = await res.json()
    expect(body.error.code).toBe('validation_error')
  })

  it('rejects join with empty name (400)', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({ title: 'Run', datetime: '2026-09-01T07:00:00', location: 'Park' }),
    )
    const created = await createRes.json()

    const res = await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest(created.id, ''),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(400)
    const body = await res.json()
    expect(body.error.code).toBe('validation_error')
  })

  it('rejects duplicate participant name on join (409)', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({ title: 'Run', datetime: '2026-09-01T07:00:00', location: 'Park' }),
    )
    const created = await createRes.json()

    // First join succeeds
    await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest(created.id, 'Alice'),
      { params: { run_id: created.id } },
    )

    // Duplicate join is rejected
    const dupRes = await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest(created.id, 'Alice'),
      { params: { run_id: created.id } },
    )
    expect(dupRes.status).toBe(409)
    const body = await dupRes.json()
    expect(body.error.code).toBe('duplicate_name')

    // Store still has only one Alice
    const storeRun = all(TABLES.Run).find(r => r.id === created.id)
    expect(storeRun.participants).toHaveLength(1)
  })

  it('rejects leave for participant not on run (404)', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({ title: 'Run', datetime: '2026-09-01T07:00:00', location: 'Park' }),
    )
    const created = await createRes.json()

    const res = await (routeApiRunsRunIdLeave.POST as Handler)(
      makeLeaveRequest(created.id, 'Nobody'),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(404)
    const body = await res.json()
    expect(body.error.code).toBe('participant_not_found')
  })
})

// ---------------------------------------------------------------------------
// Error Path: Not-Found
// ---------------------------------------------------------------------------
describe('error path: not found', () => {
  it('returns 404 when getting a non-existent run', async () => {
    const res = await (routeApiRunsRunId.GET as Handler)(
      new Request('http://test/api/runs/nonexistent'),
      { params: { run_id: 'nonexistent' } },
    )
    expect(res.status).toBe(404)
    const body = await res.json()
    expect(body.error.code).toBe('run_not_found')
  })

  it('returns 404 when joining a non-existent run', async () => {
    const res = await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest('ghost-run', 'Alice'),
      { params: { run_id: 'ghost-run' } },
    )
    expect(res.status).toBe(404)
    const body = await res.json()
    expect(body.error.code).toBe('run_not_found')
  })

  it('returns 404 when leaving a non-existent run', async () => {
    const res = await (routeApiRunsRunIdLeave.POST as Handler)(
      makeLeaveRequest('ghost-run', 'Alice'),
      { params: { run_id: 'ghost-run' } },
    )
    expect(res.status).toBe(404)
    const body = await res.json()
    expect(body.error.code).toBe('run_not_found')
  })
})

// ---------------------------------------------------------------------------
// Store-Driven Edge Cases
// ---------------------------------------------------------------------------
describe('store-driven behavior', () => {
  it('list returns all runs when multiple are seeded directly', async () => {
    insert(TABLES.Run, { id: nextId(), title: 'Run A', datetime: '2026-01-01T00:00:00', location: 'A', participants: [] })
    insert(TABLES.Run, { id: nextId(), title: 'Run B', datetime: '2026-01-02T00:00:00', location: 'B', participants: [] })
    insert(TABLES.Run, { id: nextId(), title: 'Run C', datetime: '2026-01-03T00:00:00', location: 'C', participants: [] })

    const res = await (routeApiRuns.GET as Handler)(new Request('http://test/api/runs'))
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(Array.isArray(body)).toBe(true)
    expect(body).toHaveLength(3)
  })

  it('detail returns participants seeded on the run', async () => {
    const runId = nextId()
    insert(TABLES.Run, {
      id: runId,
      title: 'Weekend Run',
      datetime: '2026-06-01T08:00:00',
      location: 'Hill',
      participants: ['Alice', 'Bob', 'Charlie'],
    })

    const res = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${runId}`),
      { params: { run_id: runId } },
    )
    expect(res.status).toBe(200)
    const body = await res.json()
    expect(body.participants).toContain('Alice')
    expect(body.participants).toContain('Bob')
    expect(body.participants).toContain('Charlie')
  })

  it('isolation: each test starts with empty store', async () => {
    // This test verifies the beforeEach reset works by confirming the store is empty
    // before we do anything. If another test leaked state, this would fail.
    expect(all(TABLES.Run)).toHaveLength(0)
  })

  it('leave removes only the named participant, others persist', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      makeCreateRequest({ title: 'Social Run', datetime: '2026-07-04T10:00:00', location: 'Square' }),
    )
    const created = await createRes.json()

    await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest(created.id, 'Alice'),
      { params: { run_id: created.id } },
    )
    await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest(created.id, 'Bob'),
      { params: { run_id: created.id } },
    )
    await (routeApiRunsRunIdJoin.POST as Handler)(
      makeJoinRequest(created.id, 'Charlie'),
      { params: { run_id: created.id } },
    )

    // Bob leaves
    await (routeApiRunsRunIdLeave.POST as Handler)(
      makeLeaveRequest(created.id, 'Bob'),
      { params: { run_id: created.id } },
    )

    const detailRes = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${created.id}`),
      { params: { run_id: created.id } },
    )
    const detail = await detailRes.json()
    expect(detail.participants).toContain('Alice')
    expect(detail.participants).toContain('Charlie')
    expect(detail.participants).not.toContain('Bob')
    expect(detail.participants).toHaveLength(2)
  })
})