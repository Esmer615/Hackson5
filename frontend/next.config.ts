import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Vercel deployment: proxy /api/* to Railway backend
  // Replace with your actual Railway app URL after deployment
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
