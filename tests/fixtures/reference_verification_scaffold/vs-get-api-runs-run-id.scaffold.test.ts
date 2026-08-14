// Deterministic verification scaffold (SIP-0104). GENERATED — DO NOT EDIT.
// The spine — placement, imports, lifecycle, invocation, status assertion — is
// frozen (SIP-0104 §4.2); the marked fill slot is the qa author's mutable surface.
import { beforeEach, describe, expect, it } from 'vitest'
import { reset } from '@/lib/store'
import * as routeApiRuns from '@/app/api/runs/route'
import * as routeApiRunsRunId from '@/app/api/runs/[run_id]/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

beforeEach(() => reset())

describe('scaffold: GET /api/runs/{run_id}', () => {
  it('GET /api/runs/{run_id} -> 200 [vs-get-api-runs-run-id]', async () => {
    const createRes = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({"title": "sample", "datetime": "2026-08-01T08:00:00", "location": "sample"}),
      }),
    )
    const created: any = await createRes.json().catch(() => ({}))
    const res = await (routeApiRunsRunId.GET as Handler)(
      new Request(`http://test/api/runs/${created.id}`),
      { params: { run_id: created.id } },
    )
    expect(res.status).toBe(200)
    const body: any = await res.json().catch(() => ({}))
    // [scaffold-slot:begin slot-vs-get-api-runs-run-id]
    // FILL (qa): domain assertions for this behavior — response values and store
    // effects beyond the declared status. `body` is the parsed response JSON.
    void body
    // [scaffold-slot:end slot-vs-get-api-runs-run-id]
  })
})
