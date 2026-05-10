import type { NextRequest } from 'next/server';

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const url = new URL(pathname + search, API_URL);

  const headers = new Headers(request.headers);
  headers.delete('host');

  const response = await fetch(url, {
    method: request.method,
    headers,
    body:
      request.method !== 'GET' && request.method !== 'HEAD'
        ? await request.text()
        : undefined,
  });

  return response;
}

export const config = {
  matcher: '/api/:path*',
};
