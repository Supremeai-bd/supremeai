# DFD-001: New Tenant Signup Data Flow

**Date:** 2026-07-08

**Status:** Draft

This document describes the data flow for the new tenant setup process, as orchestrated by the `auto_tenant_setup.py` script.

## Diagram

The following diagram illustrates how data moves from user signup to the final provisioning of a new tenant environment.

```mermaid
graph TD
    A[User Signs Up via Frontend] -->|Signup Request| B(Authentication Service);
    B -->|Triggers Event (e.g., Pub/Sub)| C(auto_tenant_setup.py);

    subgraph Tenant Setup Process
        C -->|Reads Tenant Info| C;
        C -->|1. Create Tenant Document| D[Firestore Database];
        C -->|2. Create Subcollections (users, config, limits)| D;
        C -->|3. Assign Default Skills| D;
        C -->|4. Send Welcome Email| E(SMTP Service);
        C -->|5. Notify Admin| F(Admin Notification Channel);
    end

    D -->|Tenant Data| G(SupremeAI Backend);
    E -->|Welcome Email| H[New User's Email];
    F -->|New Tenant Alert| I[Admin's Email/Slack];
```

## Flow Description

1.  **User Signup:** A new user registers through a frontend application (e.g., `studio-client`).
2.  **Authentication & Trigger:** An authentication service handles the registration and then triggers an event, invoking the `auto_tenant_setup.py` script with the new user's details (Tenant ID, Email, Name).
3.  **Tenant Document Creation:** The script connects to Firestore and creates a primary document for the new tenant in the `tenants` collection.
4.  **Subcollection Provisioning:** Based on the selected template ("starter", "professional", etc.), the script creates several subcollections under the tenant's document, such as `config`, `usage`, and `limits`, populating them with default values.
5.  **Skill Assignment:** A set of default skills (e.g., "Text Generation") are assigned to the tenant by creating documents in the `skills` subcollection.
6.  **Notifications:**
    - A welcome email is sent to the new tenant via an SMTP service.
    - A notification is sent to the system administrator to inform them of the new registration.
7.  **System Access:** Once provisioned, the main SupremeAI backend can read the tenant's configuration and data from Firestore to provide services.
