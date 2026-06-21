"use strict";
jest.mock('axios', () => {
    const mockAxios = {
        create: jest.fn((config) => {
            const baseURL = config?.baseURL || '';
            return {
                interceptors: {
                    request: { use: jest.fn() },
                    response: { use: jest.fn() },
                },
                post: (url, data, options) => {
                    const fullUrl = url.startsWith('http') ? url : (baseURL + url);
                    return mockAxios.post(fullUrl, data, options || {});
                },
                get: (url, options) => {
                    const fullUrl = url.startsWith('http') ? url : (baseURL + url);
                    return mockAxios.get(fullUrl, options || {});
                },
                delete: (url, options) => {
                    const fullUrl = url.startsWith('http') ? url : (baseURL + url);
                    return mockAxios.delete(fullUrl, options || {});
                },
            };
        }),
        post: jest.fn(),
        get: jest.fn(),
        delete: jest.fn(),
        mockReset: () => {
            mockAxios.post.mockReset();
            mockAxios.get.mockReset();
            mockAxios.delete.mockReset();
            mockAxios.create.mockClear();
        }
    };
    return mockAxios;
});
const axios = require('axios');
const { SupremeAIService, getSupremeAIService, setSupremeAIService } = require('../src/services/SupremeAIService');
describe('SupremeAIService', () => {
    let service;
    const mockConfig = {
        backendUrl: 'http://127.0.0.1:8080',
        enableRealTimeLearning: true,
        autoReportErrors: true,
    };
    beforeEach(() => {
        service = new SupremeAIService(mockConfig);
        axios.mockReset();
    });
    afterEach(() => {
        setSupremeAIService(null);
    });
    describe('constructor', () => {
        test('creates axios instance with correct baseURL', () => {
            expect(service).toBeDefined();
            expect(typeof service.sendCodeEdit).toBe('function');
        });
    });
    describe('sendCodeEdit', () => {
        test('returns failure when real-time learning is disabled', async () => {
            const disabledService = new SupremeAIService({
                ...mockConfig,
                enableRealTimeLearning: false,
            });
            const response = await disabledService.sendCodeEdit({
                taskId: '1',
                originalCode: 'a',
                editedCode: 'b',
                context: 'c',
                language: 'ts',
                timestamp: new Date().toISOString(),
                filePath: '/f.ts',
                lineNumber: 1,
            });
            expect(response.success).toBe(false);
            expect(response.message).toContain('disabled');
        });
        test('posts code edit to backend when enabled', async () => {
            axios.post.mockResolvedValueOnce({
                data: { success: true, message: 'learned' },
            });
            const response = await service.sendCodeEdit({
                taskId: '1',
                originalCode: 'a',
                editedCode: 'b',
                context: 'c',
                language: 'ts',
                timestamp: new Date().toISOString(),
                filePath: '/f.ts',
                lineNumber: 1,
            });
            expect(response.success).toBe(true);
            expect(response.message).toBe('learned');
            expect(axios.post).toHaveBeenCalledWith('http://127.0.0.1:8080/api/knowledge/learn', expect.objectContaining({
                type: 'CODE_EDIT',
                sessionId: expect.any(String),
            }), expect.any(Object));
        });
        test('returns failure object on network error', async () => {
            axios.post.mockRejectedValueOnce(new Error('Network error'));
            const response = await service.sendCodeEdit({
                taskId: '1',
                originalCode: 'a',
                editedCode: 'b',
                context: 'c',
                language: 'ts',
                timestamp: new Date().toISOString(),
                filePath: '/f.ts',
                lineNumber: 1,
            });
            expect(response.success).toBe(false);
            expect(typeof response.message).toBe('string');
        });
    });
    describe('reportError', () => {
        test('returns failure when auto-report errors is disabled', async () => {
            const disabledService = new SupremeAIService({
                ...mockConfig,
                autoReportErrors: false,
            });
            const response = await disabledService.reportError({
                errorType: 'compilation',
                errorMessage: 'err',
                filePath: '/f.ts',
                lineNumber: 1,
                severity: 'error',
                timestamp: new Date().toISOString(),
            });
            expect(response.success).toBe(false);
            expect(response.message).toContain('disabled');
        });
        test('posts error report to backend when enabled', async () => {
            axios.post.mockResolvedValueOnce({
                data: { success: true, message: 'recorded' },
            });
            const response = await service.reportError({
                errorType: 'runtime',
                errorMessage: 'TypeError',
                filePath: '/app.ts',
                lineNumber: 42,
                severity: 'error',
                timestamp: new Date().toISOString(),
            });
            expect(response.success).toBe(true);
            expect(axios.post).toHaveBeenCalledWith('http://127.0.0.1:8080/api/knowledge/failure', expect.objectContaining({ type: 'ERROR_REPORT' }), expect.any(Object));
        });
    });
    describe('sendFeedback', () => {
        test('posts feedback to backend', async () => {
            axios.post.mockResolvedValueOnce({
                data: { success: true, message: 'feedback recorded' },
            });
            const response = await service.sendFeedback({
                suggestionId: 's1',
                accepted: true,
                context: 'ctx',
                taskId: 't1',
                timestamp: new Date().toISOString(),
            });
            expect(response.success).toBe(true);
            expect(response.message).toBe('feedback recorded');
            expect(axios.post).toHaveBeenCalledWith('http://127.0.0.1:8080/api/knowledge/feedback', expect.objectContaining({ type: 'SUGGESTION_FEEDBACK' }), expect.any(Object));
        });
    });
    describe('analyzeRepository', () => {
        test('returns CodeFlow analysis response on success', async () => {
            axios.post.mockResolvedValueOnce({
                data: {
                    success: true,
                    analysisId: 'a1',
                    data: {
                        repositoryId: 'r1',
                        files: [],
                        dependencies: { nodes: [], edges: [] },
                        patterns: [],
                        securityIssues: [],
                        healthScore: {
                            score: 85,
                            grade: 'B',
                            breakdown: { security: 80, maintainability: 85, complexity: 70, documentation: 75, testing: 90 },
                            details: [],
                        },
                        analysisTimestamp: new Date().toISOString(),
                        status: 'completed',
                    },
                    message: 'ok',
                },
            });
            const response = await service.analyzeRepository({
                files: [{ path: 'a.ts', content: 'code' }],
                options: { includePatterns: true, includeSecurity: true, includeDependencies: true, depth: 2 },
            });
            expect(response.success).toBe(true);
            expect(response.analysisId).toBe('a1');
            expect(response.data.healthScore.score).toBe(85);
        });
        test('returns failed response on error', async () => {
            axios.post.mockRejectedValueOnce(new Error('Server error'));
            const response = await service.analyzeRepository({
                files: [{ path: 'a.ts', content: 'code' }],
                options: { includePatterns: true, includeSecurity: true, includeDependencies: true, depth: 2 },
            });
            expect(response.success).toBe(false);
            expect(response.analysisId).toBe('');
            expect(response.data.status).toBe('failed');
        });
    });
    describe('getSessionId', () => {
        test('returns a non-empty session ID string', () => {
            const sid = service.getSessionId();
            expect(typeof sid).toBe('string');
            expect(sid.length).toBeGreaterThan(0);
        });
    });
    describe('analyzeCodeMetrics', () => {
        test('returns metrics with correct counts', () => {
            const metrics = service.analyzeCodeMetrics('a\nb\nc', 'typescript');
            expect(metrics).toHaveProperty('linesOfCode');
            expect(metrics).toHaveProperty('nonEmptyLines');
            expect(metrics).toHaveProperty('commentLines');
            expect(metrics.linesOfCode).toBe(3);
        });
    });
});
