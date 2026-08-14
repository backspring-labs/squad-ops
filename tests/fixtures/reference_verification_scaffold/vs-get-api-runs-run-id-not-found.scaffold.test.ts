// Deterministic verification scaffold (SIP-0104). GENERATED — DO NOT EDIT.
// The spine — placement, imports, lifecycle, invocation, status assertion — is
// frozen (SIP-0104 §4.2); the marked fill slot is the qa author's mutable surface.
import { beforeEach, describe, expect, it } from 'vitest'
import { reset } from '@/lib/store'
import * as routeApiRunsRunId from '@/app/api/runs/[run_id]/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

beforeEach(() => reset())

describe('scaffold: GET /api/runs/{run_id}', () => {
  it('GET /api/runs/{run_id} unknown id -> 404 [vs-get-api-runs-run-id-not-found]', async () => {
    const res = await (routeApiRunsRunId.GET as Handler)(
      new Request('http://test/api/runs/missing'),
      { params: { run_id: 'missing' } },
    )
    expect(res.status).toBe(404)
    const body: any = await res.json().catch(() => ({}))
    // [scaffold-slot:begin slot-vs-get-api-runs-run-id-not-found]
    // FILL (qa): domain assertions for this behavior — response values and store
    // effects beyond the declared status. `body` is the parsed response JSON.
    void body
    // [scaffold-slot:end slot-vs-get-api-runs-run-id-not-found]
  })
})
