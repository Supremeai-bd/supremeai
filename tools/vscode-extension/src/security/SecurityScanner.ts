import * as vscode from 'vscode';
import { SupremeAIService } from '../services/SupremeAIService';

export class SecurityScanner {
  private supremeAIService: SupremeAIService;

  constructor(service: SupremeAIService) {
    this.supremeAIService = service;
  }

  public async scanFile(document: vscode.TextDocument): Promise<any[]> {
    const code = document.getText();
    const language = document.languageId;

    const response = await this.supremeAIService.sendChatMessage({
      message: `Perform a security scan on the following ${language} code and identify potential vulnerabilities:\n\n\`\`\`${language}\n${code}\n\`\`\``,
      sessionId: this.supremeAIService.getSessionId()
    });

    return this.parseSecurityIssues(response.response);
  }

  public async scanProject(): Promise<any[]> {
    // প্রজেক্ট জুড়ে সিকিউরিটি স্ক্যান করার লজিক
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders) {
      return [];
    }

    const securityIssues: any[] = [];
    
    // প্রতিটি ফাইল স্ক্যান করা
    const files = await vscode.workspace.findFiles('**/*.{js,ts,jsx,tsx,py,java}', '**/node_modules/**');
    
    for (const file of files) {
      const document = await vscode.workspace.openTextDocument(file);
      const issues = await this.scanFile(document);
      securityIssues.push(...issues.map(issue => ({
        ...issue,
        file: file.path
      })));
    }

    return securityIssues;
  }

  private parseSecurityIssues(response: string): any[] {
    // সিকিউরিটি ইস্যু পার্স করার লজিক
    // এটি এআই রেসপন্স থেকে সিকিউরিটি ইস্যু এক্সট্রাক্ট করবে
    const issues: any[] = [];
    
    // সাধারণ সিকিউরিটি ইস্যু খুঁজে বার করা
    if (response.includes('vulnerability') || response.includes('security')) {
      const lines = response.split('\n');
      for (const line of lines) {
        if (line.toLowerCase().includes('vulnerability') || 
            line.toLowerCase().includes('security') || 
            line.toLowerCase().includes('injection') ||
            line.toLowerCase().includes('xss') ||
            line.toLowerCase().includes('csrf')) {
          issues.push({
            severity: 'medium',
            type: 'potential_security_risk',
            description: line,
            recommendation: 'Review and validate inputs'
          });
        }
      }
    }
    
    return issues;
  }
}