import { getAIService, CodeSuggestion } from './AIService';
import * as vscode from 'vscode';

export interface CodeReviewIssue {
  line: number;
  severity: 'error' | 'warning' | 'info';
  message: string;
  suggestion: string;
  code?: string;
}

export class CodeReviewService {
  private aiService = getAIService();

  async reviewCode(
    code: string,
    language: string,
    filePath: string
  ): Promise<CodeReviewIssue[]> {
    if (!this.aiService.isAIEnabled()) {
      return this.getBasicReview(code, language);
    }

    const suggestion = await this.aiService.generateCodeCompletion(
      `Review this ${language} code for issues:\n${code}\n\nReturn JSON: {issues: [{line, severity, message, suggestion}]}`,
      language
    );

    if (suggestion) {
      try {
        const parsed = JSON.parse(suggestion.code);
        return parsed.issues || [];
      } catch {
        return this.getBasicReview(code, language);
      }
    }

    return this.getBasicReview(code, language);
  }

  async reviewSelection(
    code: string,
    language: string
  ): Promise<CodeSuggestion | null> {
    const prompt = `Review and improve this selected ${language} code:\n${code}`;
    return this.aiService.generateCodeCompletion(prompt, language);
  }

  private getBasicReview(code: string, language: string): CodeReviewIssue[] {
    const issues: CodeReviewIssue[] = [];
    const lines = code.split('\n');

    lines.forEach((line: string, index: number) => {
      if (line.includes('console.log') && language !== 'javascript') {
        issues.push({
          line: index + 1,
          severity: 'warning',
          message: 'Debug statement found',
          suggestion: 'Remove console.log before production',
        });
      }
      if (line.trim().startsWith('TODO') || line.trim().startsWith('FIXME')) {
        issues.push({
          line: index + 1,
          severity: 'info',
          message: 'Todo/Fixme comment found',
          suggestion: 'Address this item',
        });
      }
    });

    return issues;
  }
}

let codeReviewInstance: CodeReviewService | null = null;

export function getCodeReviewService(): CodeReviewService {
  if (!codeReviewInstance) {
    codeReviewInstance = new CodeReviewService();
  }
  return codeReviewInstance;
}

export function setCodeReviewService(service: CodeReviewService): void {
  codeReviewInstance = service;
}