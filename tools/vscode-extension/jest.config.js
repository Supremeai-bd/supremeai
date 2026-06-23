// ============================================================================
// file >> jest.config.js
// project >> SupremeAI 2.0
// purpose >> Configuration loading
// module >> tools
// ============================================================================
// ============================================================================
// file >> jest.config.js
// project >> SupremeAI 2.0
// purpose >> Configuration loading
// module >> tools
// ============================================================================
// ============================================================================
// file >> jest.config.js\n// project >> SupremeAI 2.0\n// purpose >> Configuration management\n// module >> tools\n// ============================================================================\nmodule.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src', '<rootDir>/test'],
  testMatch: ['**/*.test.ts'],
  moduleFileExtensions: ['ts', 'js', 'json'],
  collectCoverageFrom: ['src/**/*.ts', '!src/**/*.d.ts'],
  coverageDirectory: 'coverage',
  transform: {
    '^.+\\.ts$': 'ts-jest',
  },
  moduleNameMapper: {
    '^vscode$': '<rootDir>/test/__mocks__/vscode.ts',
  },
};
