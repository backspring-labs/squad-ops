import { all, insert, nextId, TABLES } from '@/lib/store';
import { ApiError, errorResponse } from '@/lib/errors';

export async function GET() {
  const runs = all(TABLES.Run);
  return Response.json(runs);
}

export async function POST(request: Request) {
  try {
    const body: Record<string, unknown> = await request.json();

    const { title, datetime, meeting_location, distance, pace_target, route_notes } = body;

    if (typeof title !== 'string' || title.trim() === '') {
      throw new ApiError('validation_error', 'title is required and must be a non-empty string');
    }
    if (typeof datetime !== 'string' || datetime.trim() === '') {
      throw new ApiError('validation_error', 'datetime is required and must be a non-empty string');
    }
    if (typeof meeting_location !== 'string' || meeting_location.trim() === '') {
      throw new ApiError('validation_error', 'meeting_location is required and must be a non-empty string');
    }

    const run: Record<string, unknown> = {
      id: nextId(),
      title,
      datetime,
      meeting_location,
      distance: typeof distance === 'string' ? distance : null,
      pace_target: typeof pace_target === 'string' ? pace_target : null,
      route_notes: typeof route_notes === 'string' ? route_notes : null,
      participants: [],
    };

    insert(TABLES.Run, run);

    return Response.json(run, { status: 201 });
  } catch (err) {
    if (err instanceof ApiError) {
      return errorResponse(err);
    }
    throw err;
  }
}