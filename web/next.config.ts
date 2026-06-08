import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Required for the Dockerfile's `.next/standalone` runtime — Next bundles
  // a minimal node_modules into .next/standalone so the production image
  // doesn't have to ship the full dev tree.
  output: "standalone",
};

export default nextConfig;
