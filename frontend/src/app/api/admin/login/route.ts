import { NextRequest, NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';
import { getAdminCollection } from '@/lib/mongodb';
import {
  signAdminToken,
  AUTH_COOKIE_NAME,
  getAuthCookieOptions,
  checkLoginRateLimit,
  recordFailedLogin,
  resetLoginAttempts,
} from '@/lib/auth';

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function POST(request: NextRequest) {
  try {
    // 1. IP identification & Rate limit check
    const forwardedFor = request.headers.get('x-forwarded-for');
    const ip = forwardedFor ? forwardedFor.split(',')[0].trim() : request.headers.get('x-real-ip') || '127.0.0.1';

    const rateCheck = checkLoginRateLimit(ip);
    if (!rateCheck.allowed) {
      return NextResponse.json(
        {
          error: `Too many failed login attempts. Please wait ${rateCheck.retryAfterSeconds} seconds before trying again.`,
        },
        { status: 429 }
      );
    }

    // 2. Parse & sanitize request body
    let body;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json(
        { error: 'Invalid JSON request payload.' },
        { status: 400 }
      );
    }

    const { email, password } = body || {};

    if (!email || typeof email !== 'string' || !password || typeof password !== 'string') {
      return NextResponse.json(
        { error: 'Email and password are required fields.' },
        { status: 400 }
      );
    }

    const cleanEmail = email.trim().toLowerCase();
    if (!EMAIL_REGEX.test(cleanEmail)) {
      return NextResponse.json(
        { error: 'Please enter a valid email address.' },
        { status: 400 }
      );
    }

    if (password.length > 256) {
      return NextResponse.json(
        { error: 'Password length exceeds maximum permitted limit.' },
        { status: 400 }
      );
    }

    // 3. Database lookup in MongoDB
    const admins = await getAdminCollection();
    const admin = await admins.findOne({ email: cleanEmail });

    if (!admin) {
      recordFailedLogin(ip);
      // Generic message to prevent email enumeration
      return NextResponse.json(
        { error: 'Invalid email or password.' },
        { status: 401 }
      );
    }

    // 4. Verify account status
    if (admin.isActive === false) {
      recordFailedLogin(ip);
      return NextResponse.json(
        { error: 'This admin account has been deactivated. Please contact the bot administrator.' },
        { status: 403 }
      );
    }

    // 5. Compare cryptographic password hash
    const isPasswordValid = await bcrypt.compare(password, admin.passwordHash);
    if (!isPasswordValid) {
      recordFailedLogin(ip);
      return NextResponse.json(
        { error: 'Invalid email or password.' },
        { status: 401 }
      );
    }

    // 6. Login successful: reset rate limit & update lastLoginAt
    resetLoginAttempts(ip);
    const nowIso = new Date().toISOString();
    await admins.updateOne(
      { _id: admin._id },
      { $set: { lastLoginAt: nowIso, updatedAt: nowIso } }
    );

    // 7. Generate JWT token
    const token = await signAdminToken({
      userId: admin._id.toString(),
      email: admin.email,
      role: admin.role,
    });

    // 8. Return response with HttpOnly cookie (never exposes passwordHash)
    const response = NextResponse.json({
      success: true,
      message: 'Admin authentication successful.',
      user: {
        email: admin.email,
        role: admin.role,
        lastLoginAt: nowIso,
      },
    });

    response.cookies.set(AUTH_COOKIE_NAME, token, getAuthCookieOptions());
    return response;
  } catch (error: any) {
    console.error('[Auth API Error]', error);
    return NextResponse.json(
      { error: 'An unexpected internal error occurred during authentication.' },
      { status: 500 }
    );
  }
}
