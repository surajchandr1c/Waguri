import { NextResponse } from 'next/server';
import { runPythonScript } from '@/lib/pythonBridge';

export async function GET() {
  try {
    const data = runPythonScript('stickers_manager.py', ['--list']);
    return NextResponse.json(data || { scheduled_stickers: [], logs: [], chats: [] });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to load stickers';
    console.error('Failed to load stickers:', err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const action = body.action || 'add';

    if (action === 'add') {
      const { chat_id, sticker_url, scheduled_time, sticker_name, schedule_type, repeat_interval, chat_title, target_type, target_chat_ids } = body;
      if (!sticker_url || !sticker_url.trim()) {
        return NextResponse.json({ error: 'Sticker link or identifier is required' }, { status: 400 });
      }

      const payload = JSON.stringify({
        target_type: target_type || 'single',
        chat_id: chat_id !== undefined && chat_id !== '' ? Number(chat_id) : 0,
        target_chat_ids: Array.isArray(target_chat_ids) ? target_chat_ids : [],
        sticker_url: String(sticker_url).trim(),
        sticker_name: sticker_name ? String(sticker_name).trim() : 'GC Sticker Broadcast',
        scheduled_time: scheduled_time || new Date().toISOString().slice(0, 16),
        schedule_type: schedule_type || 'once',
        repeat_interval: schedule_type === 'recurring' ? repeat_interval : 'none',
        chat_title: chat_title || '',
      });

      const res = runPythonScript('stickers_manager.py', ['--add'], payload);
      return NextResponse.json(res);
    } else if (action === 'edit') {
      const { id, chat_id, sticker_url, scheduled_time, sticker_name, schedule_type, repeat_interval, chat_title, target_type, target_chat_ids, status } = body;
      if (!id) return NextResponse.json({ error: 'Missing sticker ID' }, { status: 400 });
      if (!sticker_url || !sticker_url.trim()) {
        return NextResponse.json({ error: 'Sticker link or identifier is required' }, { status: 400 });
      }

      const payload = JSON.stringify({
        target_type: target_type || 'single',
        chat_id: chat_id !== undefined && chat_id !== '' ? Number(chat_id) : 0,
        target_chat_ids: Array.isArray(target_chat_ids) ? target_chat_ids : [],
        sticker_url: String(sticker_url).trim(),
        sticker_name: sticker_name ? String(sticker_name).trim() : 'GC Sticker Broadcast',
        scheduled_time: scheduled_time || new Date().toISOString().slice(0, 16),
        schedule_type: schedule_type || 'once',
        repeat_interval: schedule_type === 'recurring' ? repeat_interval : 'none',
        chat_title: chat_title || '',
        status: status || 'active',
      });

      const res = runPythonScript('stickers_manager.py', ['--edit', String(id)], payload);
      return NextResponse.json(res);
    } else if (action === 'delete') {
      const { id } = body;
      if (!id) return NextResponse.json({ error: 'Missing sticker ID' }, { status: 400 });
      const res = runPythonScript('stickers_manager.py', ['--delete', String(id)]);
      return NextResponse.json(res);
    } else if (action === 'toggle') {
      const { id, status } = body;
      if (!id || !status) return NextResponse.json({ error: 'Missing ID or status' }, { status: 400 });
      const res = runPythonScript('stickers_manager.py', ['--toggle', String(id), String(status)]);
      return NextResponse.json(res);
    } else if (action === 'send_now') {
      const { id } = body;
      if (!id) return NextResponse.json({ error: 'Missing sticker ID' }, { status: 400 });
      const res = runPythonScript('stickers_manager.py', ['--send-now', String(id)]);
      return NextResponse.json(res);
    }

    return NextResponse.json({ error: 'Unknown action' }, { status: 400 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Sticker action failed';
    console.error('Stickers action failed:', err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
