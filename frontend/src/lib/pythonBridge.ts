import { spawn } from 'node:child_process';
import path from 'node:path';
import fs from 'node:fs';

const MAX_OUTPUT_BYTES = 16 * 1024 * 1024;

/**
 * Dynamically resolves the path to a python script relative to workspace roots,
 * avoiding hardcoded local user directory paths.
 */
export function resolveScriptPath(scriptName: string): string {
  const candidates = [
    path.resolve(/*turbopackIgnore: true*/ process.cwd(), '..', scriptName),
    path.resolve(/*turbopackIgnore: true*/ process.cwd(), scriptName),
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
): Promise<T | null> {
  const scriptPath = resolveScriptPath(scriptName);
  return new Promise<T | null>((resolve, reject) => {
    const child = spawn('python', [scriptPath, ...args], {
      windowsHide: true,
    });

    let stdout = '';
    let stderr = '';
    let outputBytes = 0;
    let timedOut = false;
    let settled = false;
    const finishReject = (error: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(error);
    };
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill();
    }, timeoutMs);

    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk: string) => {
      outputBytes += Buffer.byteLength(chunk);
      if (outputBytes > MAX_OUTPUT_BYTES) {
        child.kill();
        finishReject(new Error(`Output from ${scriptName} exceeded the size limit.`));
        return;
      }
      stdout += chunk;
    });
    child.stderr.on('data', (chunk: string) => {
      outputBytes += Buffer.byteLength(chunk);
      if (outputBytes > MAX_OUTPUT_BYTES) {
        child.kill();
        finishReject(new Error(`Output from ${scriptName} exceeded the size limit.`));
        return;
      }
      stderr += chunk;
    });
    child.on('error', (error) => finishReject(error));
    child.on('close', (code, signal) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);

      if (timedOut) {
        reject(new Error(`${scriptName} timed out after ${timeoutMs}ms.`));
        return;
      }
      if (code !== 0) {
        reject(new Error(stderr.trim() || `${scriptName} exited with code ${code ?? signal ?? 'unknown'}.`));
        return;
      }

      const output = stdout.trim();
      if (!output) {
        if (stderr.trim()) {
          reject(new Error(stderr.trim()));
        } else {
          resolve(null);
        }
        return;
      }

      try {
        resolve(JSON.parse(output) as T);
      } catch {
        reject(new Error(`Invalid JSON output from ${scriptName}.`));
      }
    });

    child.stdin.on('error', (error) => {
      if ((error as NodeJS.ErrnoException).code !== 'EPIPE') {
        finishReject(error);
      }
    });
    child.stdin.end(stdinData);
  });
}
