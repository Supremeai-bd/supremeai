import { getAIService, CodeSuggestion } from './AIService';

export interface CodeSuggestionItem {
  description: string;
  code: string;
  improvement: string;
}

export class CodeGenerationService {
  private aiService = getAIService();

  async generateFunction(
    functionName: string,
    parameters: string,
    returnType: string,
    language: string
  ): Promise<CodeSuggestion | null> {
    const prompt = `Generate a ${language} function named ${functionName} with parameters (${parameters}) returning ${returnType}. Provide only the function code.`;
    
    return this.aiService.generateCodeCompletion(prompt, language);
  }

  async generateClass(
    className: string,
    methods: string[],
    language: string
  ): Promise<CodeSuggestion | null> {
    const methodsStr = methods.join(', ');
    const prompt = `Generate a ${language} class named ${className} with methods: ${methodsStr}. Include constructor and proper encapsulation.`;
    
    return this.aiService.generateCodeCompletion(prompt, language);
  }

  async generateTest(
    functionName: string,
    language: string
  ): Promise<CodeSuggestion | null> {
    const prompt = `Generate unit tests for ${functionName} function in ${language}. Include edge cases.`;
    
    return this.aiService.generateCodeCompletion(prompt, language);
  }

  async generateDocumentation(
    code: string,
    language: string
  ): Promise<string> {
    const prompt = `Generate JSDoc/TSDoc documentation for this ${language} code:\n${code}`;
    
    const result = await this.aiService.generateCodeCompletion(prompt, language);
    return result?.code || 'Documentation generation unavailable';
  }

  async explainError(
    error: string,
    code: string,
    language: string
  ): Promise<string> {
    const prompt = `Explain this ${language} error and provide a fix:\nError: ${error}\nCode:\n${code}`;
    
    return this.aiService.explainCode(code, language);
  }

  async generateFromComment(
    comment: string,
    language: string
  ): Promise<CodeSuggestion | null> {
    const prompt = `Convert this comment into working ${language} code:\n"${comment}"`;
    
    return this.aiService.generateCodeCompletion(prompt, language);
  }

  async learnFromEdit(
    originalCode: string,
    editedCode: string,
    language: string,
    filePath: string
  ): Promise<void> {
    // This would call the backend service
    console.log('[SupremeAI] Learning from edit:', filePath);
  }
}

let codeGenerationInstance: CodeGenerationService | null = null;

export function getCodeGenerationService(): CodeGenerationService {
  if (!codeGenerationInstance) {
    codeGenerationInstance = new CodeGenerationService();
  }
  return codeGenerationInstance;
}

export function setCodeGenerationService(service: CodeGenerationService): void {
  codeGenerationInstance = service;
}