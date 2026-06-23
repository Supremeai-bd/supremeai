// ============================================================================
// file >> ocrTrigger.ts
// project >> SupremeAI 2.0
// purpose >> OCR and document
// module >> infrastructure
// ============================================================================
// ============================================================================
// file >> ocrTrigger.ts
// project >> SupremeAI 2.0
// purpose >> OCR and document
// module >> infrastructure
// ============================================================================
// ============================================================================
// file >> ocrTrigger.ts\n// project >> SupremeAI 2.0\n// purpose >> OCR and document\n// module >> infrastructure\n// ============================================================================\n// ============================================================================
// file >> ocrTrigger.ts
// project >> SupremeAI 2.0
// purpose >> OCR and document processing
// module >> infrastructure
// lang >> bangla + english
// ============================================================================
// ============================================================================
// File >> ocrTrigger.ts
// Project >> SupremeAI 2.0
// Purpose >> OCR and document processing
// Module >> infrastructure
// ============================================================================
// ============================================================================
// File >> ocrTrigger.ts
// Project >> SupremeAI 2.0
// Purpose >> OCR and document processing
// Module >> infrastructure
// ============================================================================
// ============================================================================
// File: ocrTrigger.ts
// Project: SupremeAI 2.0
// Purpose: OCR and document processing
// Module: infrastructure
// ============================================================================
// ============================================================================
// File: ocrTrigger.ts
// Project: SupremeAI 2.0
// Purpose: OCR and document processing
// Module: infrastructure
// ============================================================================
Provides a sample Cloud Function (Realtime Database + Firestore) that initiates an OCR task when a document is queued.
Use this as a reference; integrate into your actual functions source.

### Realtime Database reference implementation
- Database path: `/ocr-queue/{pushId}`
- Expected fields: `{ file_path: string, mime: string }`
- Result: writes `{ status: 'completed', result: any }` under `/ocr-results/{pushId}`
