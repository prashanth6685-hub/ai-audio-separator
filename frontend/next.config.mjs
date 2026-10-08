/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Overridable at build time (docker-compose sets it to http://backend:8000).
    const apiTarget = process.env.API_PROXY_TARGET || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${apiTarget}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
