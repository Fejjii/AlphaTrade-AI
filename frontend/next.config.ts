import type { NextConfig } from "next";

import { buildSecurityHeaders, resolveApiOrigin } from "./src/lib/security-headers";

const nextConfig: NextConfig = {
  output: "standalone",
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: buildSecurityHeaders({
          apiOrigin: resolveApiOrigin(process.env.NEXT_PUBLIC_API_URL),
          dev: process.env.NODE_ENV === "development",
        }),
      },
    ];
  },
};

export default nextConfig;
