const fs = require('fs');
const path = 'f:\\supremeai backup\\frontend\\package.json';
let content = fs.readFileSync(path, 'utf8');
// Strip BOM
content = content.replace(/^\uFEFF/, '');
const p = JSON.parse(content);

// Remove @types/monaco-editor (doesn't exist in registry)
delete p.devDependencies['@types/monaco-editor'];

// Add monaco-editor as direct dependency (it ships its own types)
p.dependencies['monaco-editor'] = '0.55.1';

// Write with 2-space indent
fs.writeFileSync(path, JSON.stringify(p, null, 2) + '\n', 'utf8');
console.log('package.json updated successfully');
