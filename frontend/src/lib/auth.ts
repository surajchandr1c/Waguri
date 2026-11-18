import { SignJWT, jwtVerify } from 'jose';

const JWT_SECRET_STRING =
  process.env.JWT_SECRET ||
  '5e277554b9ad109c9c4471543c0e7585c9abce475c62303c225a190da26297fc';

const secretKey = new TextEncoder().encode(JWT_SECRET_STRING);

export const AUTH_COOKIE_NAME = 'waguri_admin_token';

export interface AdminSessionPayload {
  userId: string;
  email: string;
  role: string;
}

/**
 * Generate a cryptographically signed JWT for the admin session.
 */
export async function signAdminToken(payload: AdminSessionPayload): Promise<string> {
  const expiresIn = process.env.JWT_EXPIRES_IN || '1d';
  return await new SignJWT({ ...payload })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(expiresIn)
    .sign(secretKey);
}

/**
 * Verify and decode the JWT session token. Returns null if invalid or expired.
 */
export async function verifyAdminToken(token: string): Promise<AdminSessionPayload | null> {
  try {
    const { payload } = await jwtVerify(token, secretKey);
    if (!payload || !payload.email || !payload.userId) {
      return null;
    }
    return {
      userId: String(payload.userId),
      email: String(payload.email),
      role: String(payload.role || 'admin'),
    };
  } catch {
    return null;
  }
}

/**
 * Standard cookie configuration for HttpOnly session security.
 */
export function getAuthCookieOptions() {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax' as const,
    path: '/',
    maxAge: 60 * 60 * 24, // 24 hours
  };
}

// =============================================================================
// Rate Limiting & Brute Force Protection (In-Memory Sliding Window)
// =============================================================================

interface AttemptRecord {
  count: number;
  firstAttemptAt: number;
  lockedUntil?: number;
}

const loginAttempts = new Map<string, AttemptRecord>();
const MAX_FAILED_ATTEMPTS = 5;
const ATTEMPT_WINDOW_MS = 15 * 60 * 1000; // 15 minutes window
const LOCKOUT_DURATION_MS = 15 * 60 * 1000; // 15 minutes lockout

export function checkLoginRateLimit(identifier: string): { allowed: boolean; retryAfterSeconds?: number } {
  const now = Date.now();
  const record = loginAttempts.get(identifier);

  if (!record) {
    return { allowed: true };
  }

  // Active lockout check
  if (record.lockedUntil && record.lockedUntil > now) {
    const retryAfterSeconds = Math.ceil((record.lockedUntil - now) / 1000);
    return { allowed: false, retryAfterSeconds };
  }

  // Window expiration cleanup
  if (now - record.firstAttemptAt > ATTEMPT_WINDOW_MS) {
    loginAttempts.delete(identifier);
    return { allowed: true };
  }

  // Too many attempts check
  if (record.count >= MAX_FAILED_ATTEMPTS) {
    record.lockedUntil = now + LOCKOUT_DURATION_MS;
    const retryAfterSeconds = Math.ceil(LOCKOUT_DURATION_MS / 1000);
    return { allowed: false, retryAfterSeconds };
  }

  return { allowed: true };
}

export function recordFailedLogin(identifier: string): void {
  const now = Date.now();
  const record = loginAttempts.get(identifier);

  if (!record || (now - record.firstAttemptAt > ATTEMPT_WINDOW_MS)) {
    loginAttempts.set(identifier, {
      count: 1,
      firstAttemptAt: now,
    });
  } else {
    record.count += 1;
    if (record.count >= MAX_FAILED_ATTEMPTS) {
      record.lockedUntil = now + LOCKOUT_DURATION_MS;
    }
  }
}

export function resetLoginAttempts(identifier: string): void {
  loginAttempts.delete(identifier);
}
