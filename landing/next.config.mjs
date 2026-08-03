/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export for GitHub Pages. basePath is intentionally NOT hardcoded here —
  // the Pages deploy workflow injects it at build time (actions/configure-pages).
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
