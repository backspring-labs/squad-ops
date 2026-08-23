// Deterministic verification scaffold (SIP-0104). GENERATED — DO NOT EDIT.
// The spine — placement, imports, lifecycle, invocation, status assertion — is
// frozen (SIP-0104 §4.2); the marked fill slot is the qa author's mutable surface.
import { beforeEach, describe, expect, it } from 'vitest'
import { reset, all, TABLES } from '@/lib/store'
import * as routeApiRuns from '@/app/api/runs/route'

type Handler = (req: Request, ctx?: unknown) => Promise<Response> | Response

beforeEach(() => reset())

describe('scaffold: GET /api/runs', () => {
  it('GET /api/runs -> 200 [vs-get-api-runs]', async () => {
    const res = await (routeApiRuns.GET as Handler)(
      new Request('http://test/api/runs'),
    )
    expect(res.status).toBe(200)
    const body: any = await res.json().catch(() => ({}))
    // Response floor for RunEvent, derived from the interface manifest (#1029).
    const expectShape = (o: any) => {
      for (const k of ["id", "title", "datetime", "location", "participants"]) expect(o?.[k]).not.toBeUndefined()
      for (const e of o?.["participants"] ?? []) for (const k of ["id", "name"]) expect(e?.[k]).not.toBeUndefined()
    }
    expect(Array.isArray(body)).toBe(true)
    for (const item of body ?? []) expectShape(item)
    // [scaffold-slot:begin slot-vs-get-api-runs]
    // FILL (qa): domain assertions for this behavior — response values and store
    // effects beyond the declared status. `body` is the parsed response JSON.
    void body
    // [scaffold-slot:end slot-vs-get-api-runs]
  })
})
