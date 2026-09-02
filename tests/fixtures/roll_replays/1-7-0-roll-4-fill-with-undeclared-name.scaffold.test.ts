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
    // Response floor for Run, derived from the interface manifest (#1029).
    const expectShape = (o: any) => {
      for (const k of ["id", "title", "datetime", "location", "participants", "createdAt"]) expect(o?.[k]).not.toBeUndefined()
      for (const e of o?.["participants"] ?? []) expect(typeof e).toBe("string")
    }
    expectShape(body)
    // [scaffold-slot:begin slot-vc-probe-api-runs]
    expect(body.id).not.toBe(created.id ?? undefined)
    expect(body.id).toBeTruthy()
    expect(body.title).toBe('sample')
    expect(body.datetime).toBe('2026-08-01T08:00:00')
    expect(body.location).toBe('sample')
    expect(Array.isArray(body.participants)).toBe(true)
    expect(body.participants).toHaveLength(0)
    expect(body.createdAt).toBeTruthy()
    expect(all(TABLES.Run)).toHaveLength(1)
    expect(all(TABLES.Run)[0].id).toBe(body.id)
    expect(all(TABLES.Run)[0].participants).toHaveLength(0)
    // [scaffold-slot:end slot-vc-probe-api-runs]
  })
})
