import type { NextConfig } from "next";

// Pages that moved under /[competition]/ in v2: their v1 URLs were the IPL's.
const MOVED = ["matches", "players", "matchups", "compare", "teams", "simulator", "lab", "models"];

const nextConfig: NextConfig = {
  reactCompiler: true,
  async redirects() {
    // 308s, so old links, the README and search engines follow them for good.
    return MOVED.map((page) => ({
      source: `/${page}/:path*`,
      destination: `/ipl/${page}/:path*`,
      permanent: true,
    }));
  },
};

export default nextConfig;
