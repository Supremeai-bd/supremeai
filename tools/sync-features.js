/**
 * SupremeAI Feature Sync Validator
 * ================================
 * Reads feature-registry.json (single source of truth) and checks
 * which features are missing from which platform.
 *
 * Usage:
 *   node scripts/sync-features.js          → Show sync report
 *   node scripts/sync-features.js --strict → Exit with error if out of sync
 *
 * Run this in CI/CD or before every deploy to catch feature drift early.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const REGISTRY_PATH = path.join(ROOT, 'feature-registry.json');

// ─── Platform file paths ───────────────────────────────────────
const ADMIN_HTML = path.join(ROOT, 'src', 'main', 'resources', 'static', 'admin.html');
const REACT_DIR  = path.join(ROOT, 'dashboard', 'src');
const FLUTTER_DIR = path.join(ROOT, 'flutter_admin_app', 'lib', 'screens');

// ─── Load registry ─────────────────────────────────────────────
if (!fs.existsSync(REGISTRY_PATH)) {
    console.error('❌ feature-registry.json not found at:', REGISTRY_PATH);
    process.exit(1);
}
const registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf8'));
const features = registry.features || [];
console.log(`\n📋 Feature Registry: ${features.length} features loaded\n`);

// ─── Check admin.html sections ─────────────────────────────────
let adminHtmlContent = '';
if (fs.existsSync(ADMIN_HTML)) {
    adminHtmlContent = fs.readFileSync(ADMIN_HTML, 'utf8');
}

function checkAdminHtml(feature) {
    const cfg = feature.adminHtml;
    if (!cfg || !cfg.sectionId) return false;
    // Check if section ID exists in admin.html
    return adminHtmlContent.includes(`id="${cfg.sectionId}"`) ||
           adminHtmlContent.includes(`id='${cfg.sectionId}'`);
}

// ─── Check React components ────────────────────────────────────
function checkReact(feature) {
    const cfg = feature.react;
    if (!cfg || !cfg.component) return false;
    const fullPath = path.join(REACT_DIR, cfg.path || `components/${cfg.component}`);
    return fs.existsSync(fullPath);
}

// ─── Check Flutter screens ─────────────────────────────────────
function checkFlutter(feature) {
    const cfg = feature.flutter;
    if (!cfg || !cfg.screen) return false;
    const fullPath = path.join(FLUTTER_DIR, cfg.path || cfg.screen);
    return fs.existsSync(fullPath);
}

// ─── Run audit ─────────────────────────────────────────────────
const results = [];
let missingAdmin = [], missingReact = [], missingFlutter = [];
let adminCount = 0, reactCount = 0, flutterCount = 0, fullySynced = 0;

for (const f of features) {
    const hasAdmin   = checkAdminHtml(f);
    const hasReact   = checkReact(f);
    const hasFlutter = checkFlutter(f);

    if (hasAdmin) adminCount++;
    if (hasReact) reactCount++;
    if (hasFlutter) flutterCount++;

    const synced = hasAdmin && hasReact && hasFlutter;
    if (synced) fullySynced++;

    const status = synced ? '✅' : '⚠️';
    results.push({
        id: f.id,
        name: f.name,
        priority: f.priority,
        admin: hasAdmin   ? '✅' : '❌',
        react: hasReact   ? '✅' : '❌',
        flutter: hasFlutter ? '✅' : '❌',
        synced: status
    });

    if (!hasAdmin && f.adminHtml?.sectionId)     missingAdmin.push(f);
    if (!hasReact && f.react?.component)          missingReact.push(f);
    if (!hasFlutter && f.flutter?.screen)         missingFlutter.push(f);
}

// ─── Print report ──────────────────────────────────────────────
console.log('╔══════════════════════════════════════════════════════════════════════╗');
console.log('║                    FEATURE SYNC REPORT                             ║');
console.log('╠══════════════════════════════════════════════════════════════════════╣');
console.log(`║  Total Features:  ${features.length.toString().padEnd(5)} │ Fully Synced: ${fullySynced}/${features.length} (${Math.round(fullySynced*100/features.length)}%)`.padEnd(71) + '║');
console.log(`║  admin.html:      ${adminCount}/${features.length}`.padEnd(25) + `│ React: ${reactCount}/${features.length}`.padEnd(20) + `│ Flutter: ${flutterCount}/${features.length}`.padEnd(24) + '║');
console.log('╠══════════════════════════════════════════════════════════════════════╣');

// Table header
console.log('║  Feature'.padEnd(30) + 'Priority'.padEnd(10) + 'Admin'.padEnd(8) + 'React'.padEnd(8) + 'Flutter'.padEnd(10) + 'Sync  ║');
console.log('║' + '─'.repeat(70) + '║');

for (const r of results) {
    const line = `  ${r.name}`.padEnd(28) + `${r.priority}`.padEnd(10) + `${r.admin}`.padEnd(6) + `${r.react}`.padEnd(6) + `${r.flutter}`.padEnd(8) + `${r.synced}`;
    console.log('║' + line.padEnd(70) + '║');
}
console.log('╚══════════════════════════════════════════════════════════════════════╝');

// ─── Missing features detail ───────────────────────────────────
if (missingAdmin.length) {
    console.log(`\n⚠️  Missing in admin.html (${missingAdmin.length}):`);
    missingAdmin.forEach(f => console.log(`   - ${f.name} (${f.id}) — needs section id="${f.adminHtml.sectionId}"`));
}
if (missingReact.length) {
    console.log(`\n⚠️  Missing in React Dashboard (${missingReact.length}):`);
    missingReact.forEach(f => console.log(`   - ${f.name} (${f.id}) — needs ${f.react.component}`));
}
if (missingFlutter.length) {
    console.log(`\n⚠️  Missing in Flutter App (${missingFlutter.length}):`);
    missingFlutter.forEach(f => console.log(`   - ${f.name} (${f.id}) — needs ${f.flutter.screen}`));
}

// ─── Strict mode ───────────────────────────────────────────────
const isStrict = process.argv.includes('--strict');
const totalMissing = missingAdmin.length + missingReact.length + missingFlutter.length;
if (isStrict && totalMissing > 0) {
    console.log(`\n🚫 STRICT MODE: ${totalMissing} missing implementations detected. Exiting with error.`);
    process.exit(1);
}

console.log(`\n✅ Sync check complete. ${totalMissing === 0 ? 'All platforms in sync!' : `${totalMissing} gaps found.`}\n`);
