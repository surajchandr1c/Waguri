import { NextResponse } from 'next/server';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

function getScriptPath() {
  const candidates = [
    path.join(process.cwd(), '..', 'promotions_manager.py'),
    path.join(process.cwd(), 'promotions_manager.py'),
    'c:\\Users\\Suraj\\Desktop\\New folder\\bot\\promotions_manager.py',
  ];
  for (const c of candidates) {
    if (fs.existsSync(/*turbopackIgnore: true*/ c)) return c;
  }
  return 'promotions_manager.py';
}

function runScript(args: string[], stdinData?: string) {
  const scriptPath = getScriptPath();
  const res = spawnSync('python', [scriptPath, ...args], {
    input: stdinData,
    encoding: 'utf-8',
    timeout: 25000,
    windowsHide: true,
  });

  if (res.error) {
    throw res.error;
  }

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
    const data = runScript(['--list']);
    return NextResponse.json(data || { promotions: [], logs: [], chats: [], total_gcs: 0 });
  } catch (err: any) {
    console.error('Failed to load promotions:', err);
    return NextResponse.json({ error: err.message || 'Failed to load promotions' }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const action = body.action || 'add';

    if (action === 'add') {
      const { title, message, link_url, button_text, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval } = body;
      if (!message || !message.trim()) {
        return NextResponse.json({ error: 'Promotion message is required' }, { status: 400 });
      }

      const payload = JSON.stringify({
        title: title ? String(title).trim() : 'GC Promotional Announcement',
        message: String(message).trim(),
        link_url: link_url ? String(link_url).trim() : '',
        button_text: button_text ? String(button_text).trim() : 'Visit Website',
        target_type: target_type || 'all_gc',
        target_chat_ids: Array.isArray(target_chat_ids) ? target_chat_ids : [],
        schedule_type: schedule_type || 'once',
        scheduled_time: scheduled_time || new Date().toISOString().slice(0, 16),
        repeat_interval: schedule_type === 'recurring' ? repeat_interval : 'none',
      });

      const res = runScript(['--add'], payload);
      return NextResponse.json(res);
    } else if (action === 'edit') {
      const { id, title, message, link_url, button_text, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval, status } = body;
      if (!id) return NextResponse.json({ error: 'Missing promotion ID' }, { status: 400 });
      if (!message || !message.trim()) {
        return NextResponse.json({ error: 'Promotion message is required' }, { status: 400 });
      }

      const payload = JSON.stringify({
        title: title ? String(title).trim() : 'GC Promotional Announcement',
        message: String(message).trim(),
        link_url: link_url ? String(link_url).trim() : '',
        button_text: button_text ? String(button_text).trim() : 'Visit Website',
        target_type: target_type || 'all_gc',
        target_chat_ids: Array.isArray(target_chat_ids) ? target_chat_ids : [],
        schedule_type: schedule_type || 'once',
        scheduled_time: scheduled_time || new Date().toISOString().slice(0, 16),
        repeat_interval: schedule_type === 'recurring' ? repeat_interval : 'none',
        status: status || 'active',
      });

      const res = runScript(['--edit', String(id)], payload);
      return NextResponse.json(res);
    } else if (action === 'delete') {
      const { id } = body;
      if (!id) return NextResponse.json({ error: 'Missing promotion ID' }, { status: 400 });
      const res = runScript(['--delete', String(id)]);
      return NextResponse.json(res);
    } else if (action === 'toggle') {
      const { id, status } = body;
      if (!id || !status) return NextResponse.json({ error: 'Missing ID or status' }, { status: 400 });
      const res = runScript(['--toggle', String(id), String(status)]);
      return NextResponse.json(res);
    } else if (action === 'broadcast' || action === 'send_now') {
      const { id } = body;
      if (!id) return NextResponse.json({ error: 'Missing promotion ID' }, { status: 400 });
      const res = runScript(['--broadcast', String(id)]);
      return NextResponse.json(res);
    }

    return NextResponse.json({ error: 'Unknown action' }, { status: 400 });
  } catch (err: any) {
    console.error('Promotions action failed:', err);
    return NextResponse.json({ error: err.message || 'Promotion action failed' }, { status: 500 });
  }
}
