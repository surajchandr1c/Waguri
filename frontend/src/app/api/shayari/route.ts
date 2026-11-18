import { NextResponse } from 'next/server';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

function getScriptPath() {
  const candidates = [
    path.join(process.cwd(), '..', 'shayari_manager.py'),
    path.join(process.cwd(), 'shayari_manager.py'),
    'c:\\Users\\Suraj\\Desktop\\New folder\\bot\\shayari_manager.py',
  ];
  for (const c of candidates) {
    if (fs.existsSync(/*turbopackIgnore: true*/ c)) return c;
  }
  return 'shayari_manager.py';
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
    console.error('Failed to parse shayari script output:', stdout);
    throw err;
  }
}

export async function GET() {
  try {
    const data = runScript(['--list']);
    return NextResponse.json(data || { items: [], scheduled_shayari: [], logs: [], total_count: 0, category_counts: {}, chats: [] });
  } catch (err: any) {
    console.error('Failed to load shayari content:', err);
    return NextResponse.json({ error: err.message || 'Failed to load content' }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const action = body.action || 'add';

    if (action === 'add') {
      const { category, content, author, language, media_url, tags } = body;
      if (!content || !content.trim()) {
        return NextResponse.json({ error: 'Content text is required' }, { status: 400 });
      }

      const payload = JSON.stringify({
        category: category ? String(category).trim().toLowerCase() : 'shayari',
        content: String(content).trim(),
        author: author ? String(author).trim() : 'Anonymous',
        language: language ? String(language).trim() : 'Hindi / English',
        media_url: media_url ? String(media_url).trim() : '',
        tags: tags ? String(tags).trim() : '',
      });

      const res = runScript(['--add'], payload);
      return NextResponse.json(res);
    } else if (action === 'edit_item') {
      const { id, category, content, author, language, media_url, tags } = body;
      if (!id) return NextResponse.json({ error: 'Missing content ID' }, { status: 400 });
      if (!content || !content.trim()) {
        return NextResponse.json({ error: 'Content text is required' }, { status: 400 });
      }

      const payload = JSON.stringify({
        category: category ? String(category).trim().toLowerCase() : 'shayari',
        content: String(content).trim(),
        author: author ? String(author).trim() : 'Anonymous',
        language: language ? String(language).trim() : 'Hindi / English',
        media_url: media_url ? String(media_url).trim() : '',
        tags: tags ? String(tags).trim() : '',
      });

      const res = runScript(['--edit-item', String(id)], payload);
      return NextResponse.json(res);
    } else if (action === 'delete') {
      const { id } = body;
      if (!id) return NextResponse.json({ error: 'Missing content ID' }, { status: 400 });
      const res = runScript(['--delete', String(id)]);
      return NextResponse.json(res);
    } else if (action === 'broadcast' || action === 'send_now') {
      const { id, chat_id } = body;
      if (!id) return NextResponse.json({ error: 'Missing content ID' }, { status: 400 });
      const target = chat_id ? String(chat_id) : 'all_gc';
      const res = runScript(['--broadcast', String(id), target]);
      return NextResponse.json(res);
    } else if (action === 'add_schedule') {
      const { title, category, content_id, custom_text, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval } = body;

      const payload = JSON.stringify({
        title: title ? String(title).trim() : 'Daily Shayari Broadcast',
        category: category ? String(category).trim().toLowerCase() : 'all',
        content_id: content_id || null,
        custom_text: custom_text ? String(custom_text).trim() : '',
        target_type: target_type || 'all_gc',
        target_chat_ids: Array.isArray(target_chat_ids) ? target_chat_ids : [],
        schedule_type: schedule_type || 'recurring',
        scheduled_time: scheduled_time || new Date().toISOString().slice(0, 16),
        repeat_interval: schedule_type === 'recurring' ? repeat_interval : 'none',
      });

      const res = runScript(['--add-schedule'], payload);
      return NextResponse.json(res);
    } else if (action === 'edit_schedule') {
      const { id, title, category, content_id, custom_text, target_type, target_chat_ids, schedule_type, scheduled_time, repeat_interval, status } = body;
      if (!id) return NextResponse.json({ error: 'Missing schedule ID' }, { status: 400 });

      const payload = JSON.stringify({
        title: title ? String(title).trim() : 'Daily Shayari Broadcast',
        category: category ? String(category).trim().toLowerCase() : 'all',
        content_id: content_id || null,
        custom_text: custom_text ? String(custom_text).trim() : '',
        target_type: target_type || 'all_gc',
        target_chat_ids: Array.isArray(target_chat_ids) ? target_chat_ids : [],
        schedule_type: schedule_type || 'recurring',
        scheduled_time: scheduled_time || new Date().toISOString().slice(0, 16),
        repeat_interval: schedule_type === 'recurring' ? repeat_interval : 'none',
        status: status || 'active',
      });

      const res = runScript(['--edit-schedule', String(id)], payload);
      return NextResponse.json(res);
    } else if (action === 'delete_schedule') {
      const { id } = body;
      if (!id) return NextResponse.json({ error: 'Missing schedule ID' }, { status: 400 });
      const res = runScript(['--delete-schedule', String(id)]);
      return NextResponse.json(res);
    } else if (action === 'toggle_schedule') {
      const { id, status } = body;
      if (!id || !status) return NextResponse.json({ error: 'Missing ID or status' }, { status: 400 });
      const res = runScript(['--toggle-schedule', String(id), String(status)]);
      return NextResponse.json(res);
    } else if (action === 'broadcast_schedule' || action === 'send_schedule_now') {
      const { id } = body;
      if (!id) return NextResponse.json({ error: 'Missing schedule ID' }, { status: 400 });
      const res = runScript(['--broadcast-schedule', String(id)]);
      return NextResponse.json(res);
    }

    return NextResponse.json({ error: 'Unknown action' }, { status: 400 });
  } catch (err: any) {
    console.error('Shayari action failed:', err);
    return NextResponse.json({ error: err.message || 'Shayari action failed' }, { status: 500 });
  }
}
