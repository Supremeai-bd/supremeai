# SEQ-001: Canary Deployment Process

**Date:** 2026-07-08

**Status:** Draft

This sequence diagram illustrates the process of a canary deployment, which is a common strategy for rolling out new versions of an application with minimal risk. This is a hypothetical implementation based on best practices.

## Diagram

```mermaid
sequenceDiagram
    actor User
    participant GitHub
    participant GitHubActions as GitHub Actions
    participant CanaryScript as canary-deploy.py
    participant GCR as Google Container Registry
    participant CloudRun as Google Cloud Run

    User->>GitHub: git push origin main
    GitHub->>GitHubActions: Trigger Workflow on push

    GitHubActions->>CanaryScript: Run script
    CanaryScript->>GCR: Build and Push new Docker image (v2)
    GCR-->>CanaryScript: Image pushed successfully

    CanaryScript->>CloudRun: Deploy new revision (v2) without routing traffic
    CloudRun-->>CanaryScript: Revision ready

    CanaryScript->>CloudRun: Split traffic: 95% to stable (v1), 5% to canary (v2)

    loop For 10 minutes
        CanaryScript->>CloudRun: Monitor metrics (errors, latency)
    end

    alt Metrics are healthy
        CanaryScript->>CloudRun: Gradually increase traffic to 100% for v2
        CanaryScript->>CloudRun: Mark v2 as the new 'stable' revision
    else Metrics show errors
        CanaryScript->>CloudRun: Rollback: Route 100% traffic back to v1
        CanaryScript->>GitHubActions: Fail workflow and notify developers
    end
```

## Process Description

1.  **Trigger:** A developer pushes new code to the `main` branch on GitHub.
2.  **CI/CD Pipeline Starts:** GitHub Actions triggers the CI/CD workflow.
3.  **Build & Push:** The `canary-deploy.py` script (or a similar tool) builds a new Docker image for the application and pushes it to Google Container Registry (GCR).
4.  **Deploy Canary Revision:** The script deploys the new image to Google Cloud Run as a new revision but does not yet send any user traffic to it.
5.  **Traffic Splitting:** Once the new revision is ready, the script instructs Cloud Run to split incoming traffic. A small percentage (e.g., 5%) is directed to the new "canary" revision, while the majority (95%) continues to go to the existing "stable" revision.
6.  **Monitoring:** The script enters a monitoring phase, observing key metrics like error rates and response times for the canary revision over a set period (e.g., 10 minutes).
7.  **Decision:**
    - **Success (Promote):** If the metrics for the canary revision are healthy and within acceptable thresholds, the script gradually shifts more traffic to it until it receives 100%. The new revision is then promoted to "stable".
    - **Failure (Rollback):** If the canary revision shows a high error rate or other problems, the script immediately rolls back by routing 100% of the traffic back to the old stable revision. The workflow is marked as failed, and developers are notified.
