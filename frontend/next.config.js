/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ['192.168.56.1', '192.168.1.0/24', '192.168.0.0/16'],
};

module.exports = nextConfig;
