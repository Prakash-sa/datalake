#!/usr/bin/env node
/**
 * Compute CSP hashes for Next.js's inline hydration scripts.
 *
 * The static export injects inline <script> blocks carrying hydration data.
 * Under the packaged app's `script-src 'self' app://local` they are blocked,
 * React never hydrates, and the window renders as inert HTML.
 *
 * Allowing 'unsafe-inline' would fix it by disabling the protection. Instead
 * this hashes each inline script and emits an allowlist the main process folds
 * into its CSP, so only these exact scripts may run.
 *
 * Runs after `next build`; the hashes change whenever the bundle does.
 */

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const OUT_DIR = path.resolve(__dirname, '..', 'out');
const TARGET = path.resolve(__dirname, '..', 'electron', 'csp-hashes.json');

// Non-greedy, so adjacent scripts are not merged into one match.
const INLINE_SCRIPT = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;

function htmlFiles(dir) {
  const found = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) found.push(...htmlFiles(full));
    else if (entry.name.endsWith('.html')) found.push(full);
  }
  return found;
}

function main() {
  if (!fs.existsSync(OUT_DIR)) {
    console.error(`[csp] ${OUT_DIR} not found — run \`next build\` first.`);
    process.exit(1);
  }

  const hashes = new Set();
  for (const file of htmlFiles(OUT_DIR)) {
    const html = fs.readFileSync(file, 'utf8');
    for (const [, body] of html.matchAll(INLINE_SCRIPT)) {
      if (!body.trim()) continue;
      // The hash covers the script's exact bytes, so any edit invalidates it.
      const digest = crypto.createHash('sha256').update(body, 'utf8').digest('base64');
      hashes.add(`'sha256-${digest}'`);
    }
  }

  const sorted = [...hashes].sort();
  fs.writeFileSync(TARGET, `${JSON.stringify(sorted, null, 2)}\n`);
  console.log(`[csp] wrote ${sorted.length} inline-script hash(es) to ${path.relative(process.cwd(), TARGET)}`);
}

main();
