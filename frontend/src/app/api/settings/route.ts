import { NextResponse } from 'next/server';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

function getScriptPath() {
  const candidates = [
    path.join(process.cwd(), '..', 'get_users_data.py'),
    path.join(process.cwd(), 'get_users_data.py'),
    'c:\\Users\\Suraj\\Desktop\\New folder\\bot\\get_users_data.py',
  ];
  for (const c of candidates) {
    if (fs.existsSync(/*turbopackIgnore: true*/ c)) return c;
  }
  return 'get_users_data.py';
}

function runScript(args: string[], stdinData?: string) {
  const scriptPath = getScriptPath();
  const res = spawnSync('python', [scriptPath, ...args], {
    input: stdinData,
    encoding: 'utf-8',
    timeout: 20000,
    windowsHide: true,
  });

  if (res.error) throw res.error;

  const stdout = (res.stdout || '').trim();
  if (!stdout) {
    if (res.stderr) throw new Error(res.stderr);
    return null;
  }

  try {
    return JSON.parse(stdout);
  } catch (err) {
    console.error('Failed to parse script output:', stdout);
    throw err;
  }
}

export async function GET() {
  try {
    const data = runScript(['--settings-get']);
    return NextResponse.json(data || {});
  } catch (err: any) {
    console.error('Failed to fetch settings:', err);
    return NextResponse.json({ error: err.message || 'Failed to fetch settings' }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const payload = JSON.stringify(body);
    const res = runScript(['--settings-save'], payload);
    return NextResponse.json(res);
  } catch (err: any) {
    console.error('Failed to save settings:', err);
    return NextResponse.json({ error: err.message || 'Failed to save settings' }, { status: 500 });
  }
}

export async function PUT(req: Request) {
  return POST(req);
}
