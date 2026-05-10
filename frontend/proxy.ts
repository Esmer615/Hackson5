import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const url = new URL(pathname, API_URL);
  return NextResponse.rewrite(url);
}

export const config = {
  matcher: '/api/:path*',
};
