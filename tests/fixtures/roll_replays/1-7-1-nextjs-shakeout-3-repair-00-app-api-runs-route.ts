import { ApiError, errorResponse } from '@/lib/errors';
import { TABLES, all, insert, nextId } from '@/lib/store';

export async function GET() {
  try {
    const runs = all(TABLES.Run);
    return Response.json(runs);
  } catch (err) {
    return errorResponse(err);
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();

    if (!body.title || !body.datetime || !body.location) {
      throw new ApiError('validation_error', 'Missing required fields: title, datetime, location');
    }

    const run = {
      id: nextId(),
      title: body.title,
      datetime: body.datetime,
      location: body.location,
      distance: body.distance ?? undefined,
      pace: body.pace ?? undefined,
      routeNotes: body.routeNotes ?? undefined,
      participants: [] as string[],
      capacity: body.capacity != null && body.capacity !== '' ? Number(body.capacity) : undefined,
      createdAt: new Date().toISOString(),
    };

    const created = insert(TABLES.Run, run);
    return Response.json(created, { status: 201 });
  } catch (err) {
    return errorResponse(err);
  }
}