import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // FIX(FE-08): stop letting type errors sail into production builds.
  // ignoreBuildErrors:true meant broken API response shapes / null derefs /
  // wrong tower RPC args shipped silently; reactStrictMode:false kept
  // effect double-fire bugs invisible in dev. Both are now off/on per the
  // audit — `next build` again fails on type errors (default behavior).
  reactStrictMode: true,
};

export default nextConfig;
