/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export — Electron loads files directly
  output: 'export',
  trailingSlash: true,

  // Images must be unoptimized for static export
  images: {
    unoptimized: true,
  },

  // The OpenClaw gateway URL can be configured via environment variable.
  // On a different machine, set OPENCLAW_URL in .env.local
  // Default: http://localhost:18789
};

module.exports = nextConfig;
