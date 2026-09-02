import { TABLES, all, insert, nextId } from '@/lib/store';
import { ApiError, errorResponse } from '@/lib/errors';
import type { Run } from '@/lib/models';

export async function GET() {
  try {
    const rows = all(TABLES.Run);
    const runs = rows.map((row) => {
      const run = row as unknown as Run;
      return {
        ...run,
        participantCount: run.participants.length,
      };
    });
    return Response.json(runs);
  } catch (err) {
    return errorResponse(err);
  }
}

export async function POST(request: Request) {
  try {
    let body: Record<string, unknown>;
    try {
      body = await request.json();
    } catch {
      throw new ApiError('validation_error', 'Request body must be valid JSON');
    }

    const title = body.title;
    const datetime = body.datetime;
    const location = body.location;

    if (typeof title !== 'string' || title.trim() === '') {
      throw new ApiError('validation_error', 'title is required and must be non-empty');
    }
    if (typeof datetime !== 'string' || datetime.trim() === '') {
      throw new ApiError('validation_error', 'datetime is required and must be non-empty');
    }
    if (typeof location !== 'string' || location.trim() === '') {
      throw new ApiError('validation_error', 'location is required and must be non-empty');
    }

    const row: Record<string, unknown> = {
      id: nextId(),
      title: title.trim(),
      datetime: datetime.trim(),
      location: location.trim(),
      distance: typeof body.distance === 'string' && body.distance.trim() !== '' ? body.distance : undefined,
      pace: typeof body.pace === 'string' && body.pace.trim() !== '' ? body.pace : undefined,
      routeNotes: typeof body.routeNotes === 'string' && body.routeNotes.trim() !== '' ? body.routeNotes : undefined,
      participants: [] as string[],
      capacity: typeof body.capacity === 'string' && body.capacity !== '' ? Number(body.capacity) : undefined,
      createdAt: new Date().toISOString(),
    };

    const created = insert(TABLES.Run, row);
    const run = created as unknown as Run;
    return Response.json(
      {
        ...run,
        participantCount: run.participants.length,
      },
      { status: 201 }
    );
  } catch (err) {
    return errorResponse(err);
  }
}