import type { InjectedPackage, ProjectFile, VersionSnapshot } from '../types/worldclass';

export const INITIAL_PROJECT_FILES: ProjectFile[] = [
  {
    path: 'src/App.tsx',
    name: 'App.tsx',
    language: 'typescript',
    content: `export default function App() {\n  return <main>SupremeAI Studio preview</main>;\n}\n`,
  },
  {
    path: 'src/index.css',
    name: 'index.css',
    language: 'css',
    content: `@tailwind base;\n@tailwind components;\n@tailwind utilities;\n`,
  },
  {
    path: 'package.json',
    name: 'package.json',
    language: 'json',
    content: JSON.stringify({ private: true, dependencies: { react: '^19.0.0' } }, null, 2),
  },
];

export const VERSION_SNAPSHOTS: VersionSnapshot[] = [
  {
    id: 'snapshot-v1-0',
    version: 'v1.0',
    title: 'Initial scaffold',
    timestamp: '2026-11-01T10:00:00Z',
    author: 'JARVIS Agent',
    summary: 'Initial interactive preview scaffold.',
    html: '<main>Initial preview</main>',
    files: Object.fromEntries(INITIAL_PROJECT_FILES.map((file) => [file.path, file.content])),
    diffSummary: { added: 1, removed: 0, filesChanged: 1 },
  },
  {
    id: 'snapshot-v1-3',
    version: 'v1.3',
    title: 'Production preview polish',
    timestamp: '2026-11-05T10:00:00Z',
    author: 'Developer',
    summary: 'Added responsive preview and deployment controls.',
    html: '<main>Production-ready preview</main>',
    files: Object.fromEntries(INITIAL_PROJECT_FILES.map((file) => [file.path, file.content])),
    diffSummary: { added: 24, removed: 3, filesChanged: 3 },
  },
];

export const POPULAR_PACKAGES: InjectedPackage[] = [
  { name: 'lucide-react', version: 'latest', cdnUrl: 'https://unpkg.com/lucide-react', installed: true, category: 'Icons' },
  { name: 'framer-motion', version: 'latest', cdnUrl: 'https://unpkg.com/framer-motion', installed: false, category: 'Animation' },
  { name: 'recharts', version: 'latest', cdnUrl: 'https://unpkg.com/recharts', installed: false, category: 'Data' },
  { name: 'radix-ui', version: 'latest', cdnUrl: 'https://unpkg.com/@radix-ui/react-dialog', installed: false, category: 'UI' },
];
