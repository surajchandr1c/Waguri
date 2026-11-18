import { NextResponse } from 'next/server';
import { fetchRawDatabaseData } from '@/lib/pythonBridge';

export async function GET(_request: Request) {
  const data = fetchRawDatabaseData();
  if (!data) {
    return NextResponse.json({ error: 'Failed to read MongoDB database' }, { status: 500 });
  }

  return NextResponse.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    ...data,
  });
}
