import type { NextConfig } from "next";

import { PHASE_B_REDIRECTS } from "./src/lib/navigation/phase-b-redirects";
import { buildSecurityHeaders, resolveApiOrigin } from "./src/lib/security-headers";

const nextConfig: NextConfig = {
  output: "standalone",
  async redirects() {
    return PHASE_B_REDIRECTS.map((rule) => ({
      source: rule.source,
      destination: rule.destination,
      permanent: rule.permanent,
    }));
  },
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
