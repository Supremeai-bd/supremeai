# MERMD - Cloud Functions

## Overview

Firebase Cloud Functions for backend operations that don't require the main Spring Boot server.

## How It Works

### Architecture Flow

```
Firebase Trigger → Cloud Function → External Service → Response
```

## Key Functions

| File                      | Purpose                     |
| ------------------------- | --------------------------- |
| `scrapeEngine.ts`         | Web scraping orchestration  |
| `scrapeHistoryManager.ts` | Scraping history management |
| `chatClassifier.ts`       | Chat message classification |

## Usage

- Deployed to Firebase
- Triggered by Firestore events
- HTTP callable functions

## Integration

- Uses Firebase Admin SDK
- Connects to main backend via API
- Data stored in Firestore
