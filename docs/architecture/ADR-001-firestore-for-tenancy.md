# ADR-001: Firestore for Tenant Data Management

**Date:** 2026-07-08

**Status:** Accepted

## Context

The SupremeAI 2.0 platform requires a multi-tenant architecture to support individual users or organizations. When a new user signs up, the system must automatically provision a dedicated set of resources, configurations, and data structures for them. The `auto_tenant_setup.py` script is responsible for this process. We needed to choose a database solution that is scalable, serverless, and integrates well with our existing Google Cloud ecosystem.

The key requirements are:
- Automatic scaling to handle a large number of tenants.
- Isolation of data between tenants.
- Real-time capabilities for future features.
- Integration with Google Cloud Functions and other services.
- A flexible schema to accommodate different tenant configurations and templates (e.g., "starter", "professional").

## Decision

We have decided to use **Google Cloud Firestore** as the primary database for storing all tenant-specific data.

This includes:
- The main `tenants` collection to store high-level information about each tenant.
- Subcollections under each tenant document for `users`, `config`, `usage`, `limits`, and `skills`.

The `auto_tenant_setup.py` script will interact directly with Firestore to create and configure these documents and subcollections upon new user registration.

## Consequences

### Positive Consequences

- **Scalability:** Firestore scales automatically, so we don't need to manage database servers or worry about performance as the number of tenants grows.
- **Serverless Integration:** It integrates seamlessly with our serverless architecture, especially with Firebase Functions and Google Cloud Run services.
- **Data Model Flexibility:** Firestore's document-based structure allows us to easily store and modify complex, nested configurations for each tenant without rigid schemas.
- **Real-time Features:** The real-time listeners can be used in the future for features like live dashboards or collaborative editing within the `studio-client`.
- **Strong Security Rules:** We can enforce strict data isolation between tenants using Firestore Security Rules, ensuring one tenant cannot access another's data.

### Negative Consequences

- **Complex Queries:** Firestore is not a relational database, so complex queries, joins, and aggregations can be difficult or inefficient to perform. This might require us to denormalize data or use a separate analytics database (like BigQuery) in the future.
- **Vendor Lock-in:** Deep integration with Firestore ties us more closely to the Google Cloud ecosystem, making a future migration to another cloud provider more complex.
- **Cost Model:** The cost is based on reads, writes, and document storage. For highly active tenants, this could become more expensive than a provisioned-throughput model if not managed carefully. We will need to monitor usage closely.
