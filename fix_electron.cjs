const fs = require('fs');
const path = 'f:\\supremeai backup\\packages\\shared-services\\src\\platform\\electron.ts';
let c = fs.readFileSync(path, 'utf8');

const old = `export class ElectronWorkspace implements PlatformWorkspace {
  constructor(
    public readonly secrets: PlatformSecretStorage,
    private fileProvider?: {
      workspaceFolders: string[] | null;
      findFiles: (include: string, exclude?: string) => Promise<string[]>;
    }
  ) {}`;

const replacement = `export class ElectronWorkspace implements PlatformWorkspace {
  public readonly secrets: PlatformSecretStorage;
  private fileProvider?: {
    workspaceFolders: string[] | null;
    findFiles: (include: string, exclude?: string) => Promise<string[]>;
  };

  constructor(
    secrets: PlatformSecretStorage,
    fileProvider?: ElectronWorkspace['fileProvider']
  ) {
    this.secrets = secrets;
    this.fileProvider = fileProvider;
  }`;

c = c.replace(old, replacement);
fs.writeFileSync(path, c, 'utf8');
console.log('Done: electron.ts fixed');
