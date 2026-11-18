import { NextResponse } from 'next/server';
import { runPythonScript } from '@/lib/pythonBridge';

export async function GET(_request: Request) {
  try {
    const data = await runPythonScript('get_users_data.py', ['--settings-get']);
    if (!data) throw new Error('Settings manager returned no data.');
    return NextResponse.json(data);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to fetch settings';
    console.error('Failed to fetch settings:', err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const payload = JSON.stringify(body);
    const res = await runPythonScript('get_users_data.py', ['--settings-save'], payload);
    return NextResponse.json(res);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to save settings';
    console.error('Failed to save settings:', err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  return POST(req);
}
