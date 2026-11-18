import { NextResponse } from 'next/server';
import { runPythonScript } from '@/lib/pythonBridge';

export async function GET(_request: Request) {
  try {
    const data = await runPythonScript('promotions_manager.py', ['--list']);
    if (!data) throw new Error('Promotions manager returned no data.');
    return NextResponse.json(data);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Failed to load promotions';
    console.error('Failed to load promotions:', err);
    return NextResponse.json({ error: message }, { status: 500 });
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

      const res = await runPythonScript('promotions_manager.py', ['--add'], payload);
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

      const res = await runPythonScript('promotions_manager.py', ['--edit', String(id)], payload);
      return NextResponse.json(res);
    } else if (action === 'delete') {
      const { id } = body;
      if (!id) return NextResponse.json({ error: 'Missing promotion ID' }, { status: 400 });
      const res = await runPythonScript('promotions_manager.py', ['--delete', String(id)]);
      return NextResponse.json(res);
    } else if (action === 'toggle') {
      const { id, status } = body;
      if (!id || !status) return NextResponse.json({ error: 'Missing ID or status' }, { status: 400 });
      const res = await runPythonScript('promotions_manager.py', ['--toggle', String(id), String(status)]);
      return NextResponse.json(res);
    } else if (action === 'broadcast' || action === 'send_now') {
      const { id } = body;
      if (!id) return NextResponse.json({ error: 'Missing promotion ID' }, { status: 400 });
      const res = await runPythonScript('promotions_manager.py', ['--broadcast', String(id)]);
      return NextResponse.json(res);
    }

    return NextResponse.json({ error: 'Unknown action' }, { status: 400 });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Promotion action failed';
    console.error('Promotions action failed:', err);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
