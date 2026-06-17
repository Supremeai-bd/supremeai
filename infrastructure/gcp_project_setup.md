# GCP Project Setup for SupremeAI 2.0

## 1. Create GCP Project
```bash
gcloud projects create supremeai-2-${UNIQUE_ID} --name="SupremeAI 2.0"
gcloud config set project supremeai-2-${UNIQUE_ID}
```

## 2. Enable Required APIs
Run the following once inside the chosen billing-linked project.

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  firestore.googleapis.com \
  pubsub.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com
```

## 3. Firestore
- Native mode recommended; database `(default)`, location `nam5` (multi-region us-central) or another multi-region.
- If required, `gcloud firestore databases create --region=nam5`

## 4. Pub/Sub
Create topic and subscription:
```bash
gcloud pubsub topics create supremeai-tasks
gcloud pubsub subscriptions create supremeai-tasks-sub --topic=supremeai-tasks
```

## 5. Artifact Registry
```bash
gcloud artifacts repositories create supremeai-repo \
  --repository-format=docker \
  --location=us-central1 \
  --description="SupremeAI container images"
```

## 6. Service Account for Local / CI
Create a dedicated service account and download JSON key:
```bash
gcloud iam service-accounts create supremeai-runner \
  --display-name="SupremeAI Cloud Run Runner"

gcloud projects add-iam-policy-binding supremeai-2-${UNIQUE_ID} \
  --member="serviceAccount:supremeai-runner@supremeai-2-${UNIQUE_ID}.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud iam service-accounts keys create ~/gcp-sa-key.json \
  --iam-account=supremeai-runner@supremeai-2-${UNIQUE_ID}.iam.gserviceaccount.com
```

## 7. Required Environment Variables

| Variable | Description | Example |
|---|---|-----|
| `GCP_PROJECT_ID` | Project ID | `supremeai-2-abc123` |
| `GCP_REGION` | Cloud Run region | `us-central1` |
| `GCP_SERVICE_NAME` | Cloud Run service | `supremeai-api` |
| `GCP_CLOUD_RUN_URL` | Deployed service URL | `https://supremeai-api-xyz.a.run.app` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to SA JSON key | `/absolute/path/gcp-sa-key.json` |
| `GCP_FIRESTORE_COLLECTION` | Firestore collection for queue | `verification_queue` |
| `GCP_FIRESTORE_SQLITE_PATH` | Local fallback DB path | `data/gcp_firestore.db` |
| `GCP_PUBSUB_TOPIC` | Topic for job submission | `supremeai-tasks` |
| `GCP_PUBSUB_SUBSCRIPTION` | Subscription consumer name | `supremeai-tasks-sub` |
| `GCP_PUBSUB_SQLITE_PATH` | Pub/Sub local state | `data/pubsub.db` |
| `GCP_ARTIFACT_REPO` | Artifact registry repo | `us-central1-docker.pkg.dev/<PROJECT>/supremeai-repo/supremeai` |

## 8. Deploy to Cloud Run
```bash
gcloud run deploy supremeai-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8000
```

## 9. Verify
```bash
gcloud run services describe supremeai-api --region us-central1
curl https://<SERVICE_URL>/health
```
