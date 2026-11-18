import { NextResponse } from 'next/server';
import { runPythonScript } from '@/lib/pythonBridge';

export async function GET(_request: Request) {
  try {
    const data = await runPythonScript('get_users_data.py', ['--overview']);
    if (!data) {
      throw new Error('Overview telemetry returned no data.');
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Failed to load dashboard telemetry:', error);
    return NextResponse.json({ error: 'Failed to load dashboard telemetry.' }, { status: 500 });
  }
}
