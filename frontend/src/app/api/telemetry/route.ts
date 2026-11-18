import { NextResponse } from 'next/server';
import { execSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

function fetchRawDatabaseData() {
  const candidateScripts = [
    path.join(process.cwd(), '..', 'get_users_data.py'),
    path.join(process.cwd(), 'get_users_data.py'),
    'c:\\Users\\Suraj\\Desktop\\New folder\\bot\\get_users_data.py',
  ];

  for (const script of candidateScripts) {
    if (fs.existsSync(/*turbopackIgnore: true*/ script)) {
      try {
        const stdout = execSync(`python "${script}"`, {
          timeout: 15000,
          encoding: 'utf-8',
          windowsHide: true,
        });
        const parsed = JSON.parse(stdout);
        if (parsed && !parsed.error) {
          return parsed;
        }
      } catch (err) {
        console.warn(`Execution failed for ${script}:`, err);
      }
    }
  }

  return null;
}

export async function GET() {
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
