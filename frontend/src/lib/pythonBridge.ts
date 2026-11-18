import { spawnSync, execSync } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

/**
 * Dynamically resolves the path to a python script relative to workspace roots,
 * avoiding hardcoded local user directory paths.
 */
export function resolveScriptPath(scriptName: string): string {
  const candidates = [
    path.resolve(/*turbopackIgnore: true*/ process.cwd(), '..', scriptName),
    path.resolve(/*turbopackIgnore: true*/ process.cwd(), scriptName),
    path.join(/*turbopackIgnore: true*/ process.cwd(), '..', scriptName),
    path.join(/*turbopackIgnore: true*/ process.cwd(), scriptName),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(/*turbopackIgnore: true*/ candidate)) {
      return candidate;
    }
  }

  return scriptName;
}

/**
 * Execute a python manager script with arguments and optional stdin JSON data.
 */
export function runPythonScript<T = unknown>(
  scriptName: string,
  args: string[],
  stdinData?: string,
  timeoutMs = 25000
): T | null {
  const scriptPath = resolveScriptPath(scriptName);
  const res = spawnSync('python', [scriptPath, ...args], {
    input: stdinData,
    encoding: 'utf-8',
    timeout: timeoutMs,
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
    return JSON.parse(stdout) as T;
  } catch (err) {
    console.error(`Failed to parse output from ${scriptName}:`, stdout);
    throw err;
  }
}

/**
 * Executes get_users_data.py to retrieve full raw MongoDB data snapshots.
 */
export function fetchRawDatabaseData<T = Record<string, unknown>>(): T | null {
  const scriptPath = resolveScriptPath('get_users_data.py');
  if (!fs.existsSync(/*turbopackIgnore: true*/ scriptPath)) {
    return null;
  }

  try {
    const stdout = execSync(`python "${scriptPath}"`, {
      timeout: 15000,
      encoding: 'utf-8',
      windowsHide: true,
    });
    const parsed = JSON.parse(stdout);
    if (parsed && !parsed.error) {
      return parsed as T;
    }
  } catch (err) {
    console.warn(`Execution failed for ${scriptPath}:`, err);
  }

  return null;
}
