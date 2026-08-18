const path = require('path');

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'export',
  images: {
    unoptimized: true,
  },
  turbopack: {
    root: path.resolve(__dirname),
  },
  // Hide the floating Next.js dev-tools badge. It overlays the app's own UI in
  // the Electron window, where there is no browser chrome to separate them.
  devIndicators: false,
  // `next dev` otherwise writes its own AGENTS.md and CLAUDE.md into this
  // directory on every run. Agent instructions for this repo come from
  // ~/.agents, so the generated files are unwanted churn.
  agentRules: false,
}

module.exports = nextConfig
