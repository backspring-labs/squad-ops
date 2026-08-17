// Deterministic verification scaffold (SIP-0104). GENERATED — DO NOT EDIT.
// The spine — placement, imports, lifecycle, invocation, status assertion — is
// frozen (SIP-0104 §4.2); the marked fill slot is the qa author's mutable surface.
import { beforeEach, describe, expect, it } from 'vitest'
import { reset, all, TABLES } from '@/lib/store'
import * as routeApiRuns from '@/app/api/runs/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

beforeEach(() => reset())

describe('scaffold: POST /api/runs', () => {
  it('POST /api/runs -> 201 [vc-probe-api-runs]', async () => {
    const res = await (routeApiRuns.POST as Handler)(
      new Request('http://test/api/runs', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({"title": "sample", "datetime": "2026-08-01T08:00:00", "location": "sample"}),
      }),
    )
    expect(res.status).toBe(201)
    const body: any = await res.json().catch(() => ({}))
    // [scaffold-slot:begin slot-vc-probe-api-runs]
    // FILL (qa): domain assertions for this behavior — response values and store
    // effects beyond the declared status. `body` is the parsed response JSON.
    void body
    // [scaffold-slot:end slot-vc-probe-api-runs]
  })
})
