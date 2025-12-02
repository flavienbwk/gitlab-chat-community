/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,

  // API rewrites for development
  // In production (with nginx), API is served from same origin at /api
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    // Only rewrite if NEXT_PUBLIC_API_URL is set (development mode)
    if (apiUrl) {
      return [
        {
          source: '/api/:path*',
          destination: `${apiUrl}/api/:path*`,
        },
      ];
    }
    // In production, no rewrites needed - nginx handles routing
    return [];
  },
};

module.exports = nextConfig;
