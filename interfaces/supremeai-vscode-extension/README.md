# SupremeAI VS Code Extension

Real-time code learning and AI assistance directly in your IDE. Every code edit, error, and feedback you provide trains the SupremeAI core engine instantly.

## Features

- **Real-Time Learning**: Every code edit you make is anonymously sent to SupremeAI for learning
- **Auto Error Reporting**: Compilation errors and stack traces automatically reported
- **Suggestion Feedback**: Accept/Reject AI suggestions with one click to improve future results

## Installation

### From Source

1. Clone and install dependencies:

```bash
cd supremeai-vscode-extension
npm install
```

2. Compile TypeScript:

```bash
npm run compile
```

3. Package extension:

```bash
npx vsce package
```

4. Install in VS Code:
   - Open Extensions view (Ctrl+Shift+X)
   - Click "..." → "Install from VSIX"
   - Select `supremeai-vscode-6.0.0.vsix`

## Configuration

Open VS Code Settings (Ctrl+,) and search for `supremeai`:

| Setting                            | Type    | Default                                | Description                            |
| ---------------------------------- | ------- | -------------------------------------- | -------------------------------------- |
| `supremeai.backendUrl`             | string  | `https://ide-api.supremeai.google.com` | SupremeAI Backend API URL              |
| `supremeai.enableRealTimeLearning` | boolean | `true`                                 | Enable sending code edits for learning |
| `supremeai.autoReportErrors`       | boolean | `true`                                 | Auto-report errors to backend          |

## Usage

### Automatic (Background)

The extension works automatically in the background:

1. Edit any code file → after 2 seconds of inactivity, changes are sent
2. Compilation errors appear → automatically reported
3. VS Code shows SupremeAI status in bottom-right corner

### Manual Commands

Open Command Palette (Ctrl+Shift+P) and run:

| Command                                    | Description                               |
| ------------------------------------------ | ----------------------------------------- |
| `SupremeAI: Accept Suggestion`             | Mark current AI suggestion as accepted    |
| `SupremeAI: Reject Suggestion`             | Mark current AI suggestion as rejected    |
| `SupremeAI: Send Feedback`                 | Open feedback dialog                      |
| `SupremeAI: Report Error`                  | Manually report error at cursor           |
| `SupremeAI: Force Learn from Current File` | Immediately analyze and send current file |

## Data Sent to Backend

### Code Edit Events

```json
{
  "type": "CODE_EDIT",
  "data": {
    "taskId": "task_1693123456_abc123",
    "originalCode": "const x = 1;",
    "editedCode": "const x = 2;",
    "context": "File: /src/app.ts, Language: typescript",
    "filePath": "/src/app.ts",
    "timestamp": "2026-04-28T07:30:00Z"
  }
}
```

### Error Reports

```json
{
  "type": "ERROR_REPORT",
  "data": {
    "errorType": "compilation",
    "errorMessage": "TypeError: Cannot read property 'map' of undefined",
    "filePath": "/src/components/UserList.tsx",
    "lineNumber": 42,
    "severity": "error",
    "timestamp": "2026-04-28T07:31:00Z"
  }
}
```

### Suggestion Feedback

```json
{
  "type": "SUGGESTION_FEEDBACK",
  "data": {
    "suggestionId": "sug_1693123400_xyz789",
    "accepted": true,
    "taskId": "task_1693123388_def456",
    "context": "Auto-completion suggestion"
  }
}
```

## Privacy & Security

- **No Personal Data**: Only code snippets and error messages are sent
- **No Secrets**: The extension automatically filters out API keys, passwords, tokens
- **Anonymous Sessions**: Each VS Code session uses a random anonymous session ID
- **Opt-Out**: Disable `supremeai.enableRealTimeLearning` to stop sending data
- **Encrypted**: All data sent over HTTPS to backend

## Backend API Endpoints

The extension communicates with:

- `POST /api/knowledge/learn` - Receive code edits for learning
- `POST /api/knowledge/failure` - Report errors for pattern analysis
- `POST /api/knowledge/feedback` - Send accept/reject feedback
- `POST /api/knowledge/analysis` - Send full code analysis snapshots
- `GET /api/knowledge/stats` - Retrieve learning statistics

## Development

### Build & Watch

```bash
npm run watch    # Compile in watch mode
npm run lint     # Run ESLint
```

### Debug

1. Press `F5` in VS Code to launch extension development host
2. Open any code file and make edits
3. Check Debug Console for `[SupremeAI]` logs

### Testing Backend Connectivity

```bash
# Test backend health
curl https://ide-api.supremeai.google.com/actuator/health

# Send test learning event
curl -X POST https://ide-api.supremeai.google.com/api/knowledge/learn \
  -H "Content-Type: application/json" \
  -d '{
    "type": "CODE_EDIT",
    "data": {
      "taskId": "test-123",
      "originalCode": "console.log(\"hello\")",
      "editedCode": "console.log(\"hello world\")",
      "context": "test",
      "filePath": "/test.ts",
      "timestamp": "2026-04-28T07:00:00Z"
    },
    "sessionId": "vscode-test-session"
  }'
```

## Troubleshooting

### Extension not activating

- Check if backend URL is reachable
- Verify `out/extension.js` exists (run `npm run compile`)

### Data not being sent

- Ensure `enableRealTimeLearning` is `true`
- Check Developer Tools Console for errors (Help → Toggle Developer Tools)
- Verify backend is running and accessible

### Errors in output

- Enable debug logging: `"supremeai.logLevel": "debug"` in settings
- Check network tab for failed requests

## Contributors

Built for the SupremeAI project. See [main README](../README.md) for architecture details.

## License

MIT
