const path = require("node:path");

/** @type {import('next').NextConfig} */
const nextConfig = {
  serverExternalPackages: ["@duckdb/node-api", "@duckdb/node-bindings"],
  outputFileTracingIncludes: {
    "/*": [
      "./data/merged/player_analytics.duckdb",
      "./node_modules/@duckdb/node-bindings*/**/*",
      "./node_modules/@duckdb/node-api*/**/*",
    ],
  },
  turbopack: {
    root: path.resolve(__dirname),
  },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "img.a.transfermarkt.technology",
      },
      {
        protocol: "https",
        hostname: "**.transfermarkt.com",
      },
    ],
  },
};

module.exports = nextConfig;
