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
    let query: any = { email: payload.email };
    if (ObjectId.isValid(payload.userId)) {
      query = { _id: new ObjectId(payload.userId) };
    }

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
  } catch (error: any) {
    console.error('[Admin Me API Error]', error);
    return NextResponse.json(
      { authenticated: false, error: 'Failed to verify admin session.' },
      { status: 500 }
    );
  }
}
