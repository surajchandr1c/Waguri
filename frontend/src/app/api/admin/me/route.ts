import { NextRequest, NextResponse } from 'next/server';
import { AUTH_COOKIE_NAME, verifyAdminToken } from '@/lib/auth';
import { getAdminCollection } from '@/lib/mongodb';
import { ObjectId } from 'mongodb';

export async function GET(request: NextRequest) {
  try {
    const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
    if (!token) {
      return NextResponse.json(
        { authenticated: false, error: 'No active session found.' },
        { status: 401 }
      );
    }

    const payload = await verifyAdminToken(token);
    if (!payload) {
      return NextResponse.json(
        { authenticated: false, error: 'Session token invalid or expired.' },
        { status: 401 }
      );
    }

    const admins = await getAdminCollection();
    const query = ObjectId.isValid(payload.userId)
      ? { _id: new ObjectId(payload.userId) }
      : { email: payload.email };

    const admin = await admins.findOne(query);
    if (!admin || admin.isActive === false) {
      return NextResponse.json(
        { authenticated: false, error: 'Admin account not found or disabled.' },
        { status: 401 }
      );
    }

    return NextResponse.json({
      authenticated: true,
      user: {
        email: admin.email,
        role: admin.role,
        lastLoginAt: admin.lastLoginAt,
      },
    });
  } catch (error: unknown) {
    if (
      typeof error === 'object' &&
      error !== null &&
      'digest' in error &&
      (error as { digest?: string }).digest === 'NEXT_PRERENDER_INTERRUPTED'
    ) {
      throw error;
    }
    console.error('[Admin Me API Error]', error);
    return NextResponse.json(
      { authenticated: false, error: 'Failed to verify admin session.' },
      { status: 500 }
    );
  }
}
