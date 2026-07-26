/**
 * Copy backend/assets/Components → public/component-photos (slug filenames).
 * Run from repo root: node frontend/scripts/sync-component-photos.mjs
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '..', '..');
const srcDir = path.join(repoRoot, 'backend', 'assets', 'Components');
const dstDir = path.join(__dirname, '..', 'public', 'component-photos');

function slugify(base) {
  return base
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

if (!fs.existsSync(srcDir)) {
  console.error('Missing folder:', srcDir);
  process.exit(1);
}

fs.mkdirSync(dstDir, { recursive: true });
let n = 0;
for (const file of fs.readdirSync(srcDir)) {
  const full = path.join(srcDir, file);
  if (!fs.statSync(full).isFile()) continue;
  const ext = path.extname(file).toLowerCase();
  const slug = slugify(path.basename(file, ext));
  fs.copyFileSync(full, path.join(dstDir, `${slug}${ext}`));
  n += 1;
}
console.log(`Synced ${n} photos → ${dstDir}`);
