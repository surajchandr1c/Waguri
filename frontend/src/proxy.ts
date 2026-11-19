import { NextRequest, NextResponse } from 'next/server';
import { verifyAdminToken } from './lib/auth';
const AUTH_COOKIE_NAME = 'waguri_admin_token';

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Extract session token from cookie
  const token = request.cookies.get(AUTH_COOKIE_NAME)?.value;
  let isAuthenticated = false;

  if (token) {
    try {
      isAuthenticated = Boolean(await verifyAdminToken(token));
    } catch {
      isAuthenticated = false;
    }
  }

  // 2. Public Auth Routes
  const isLoginPage = pathname === '/login';
  const isLoginApi = pathname === '/api/admin/login';

  // If already authenticated and visiting /login -> redirect to main dashboard
  if (isLoginPage) {
    if (isAuthenticated) {
      return NextResponse.redirect(new URL('/', request.url));
    }
    return NextResponse.next();
  }

  // Public login API route
  if (isLoginApi) {
    return NextResponse.next();
  }

  // 3. Protected Routes handling
  if (!isAuthenticated) {
    // Return 401 for all protected API calls
    if (pathname.startsWith('/api')) {
      return NextResponse.json(
        { error: 'Unauthorized. Admin session required.' },
        { status: 401 }
      );
    }

    // Redirect unauthenticated page requests to /login
    const loginUrl = new URL('/login', request.url);
    // If an invalid token cookie was present, clear it on redirect
    const response = NextResponse.redirect(loginUrl);
    if (token) {
      response.cookies.set(AUTH_COOKIE_NAME, '', {
        path: '/',
        maxAge: 0,
        expires: new Date(0),
      });
    }
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - waguri.png (background image)
     * - image assets (*.svg, *.png, *.jpg, *.jpeg, *.gif, *.webp)
     */
    '/((?!_next/static|_next/image|favicon.ico|waguri.png|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
