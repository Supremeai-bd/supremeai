#!/usr/bin/env python
"""
auto_secret_rotate.py
=====================
Automatic secret rotation for SupremeAI 2.0.

Rotates API keys and other secrets stored in Google Secret Manager
on a scheduled basis (e.g., every 30 days) to prevent credential leakage.

Supports:
- Google Secret Manager
- Future extensions for AWS Secrets Manager, HashiCorp Vault, etc.

Environment Variables:
- GOOGLE_CLOUD_PROJECT: GCP project ID
- SECRET_IDS: Comma-separated list of secret IDs to rotate (e.g., "firebase-api-key,openrouter-api-key,gemini-api-key")
- ROTATION_DAYS: How often to rotate (default: 30)
- For each secret, you can optionally set:
  * SECRET_ID_VALUE: If set, use this value; otherwise generate a random string
"""

import os
import sys
import string
import secrets
from datetime import datetime, timedelta
from typing import List, Optional

# Add the backend directory to the path
backend_dir = os.path.join(os.path.dirname(__file__), '../../backend')
sys.path.insert(0, backend_dir)

def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*()_+-=[]{}|;:,.<>?'
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def rotate_secret(secret_id: str, project_id: str, value: Optional[str] = None) -> bool:
    """
    Rotate a secret by adding a new version.
    
    Args:
        secret_id: The ID of the secret to rotate
        project_id: The GCP project ID
        value: The new value for the secret. If None, a random value is generated.
        
    Returns:
        True if successful, False otherwise
    """
    try:
        from google.cloud import secretmanager
        
        # Create the Secret Manager client
        client = secretmanager.SecretManagerServiceClient()
        
        # Build the resource name of the parent secret
        parent = f"projects/{project_id}/secrets/{secret_id}"
        
        # Check if the secret exists
        try:
            client.get_secret(request={"name": parent})
        except Exception:
            print(f"⚠️  Secret {secret_id} does not exist. Creating it.")
            # Create the secret if it doesn't exist
            secret = {
                "replication": {"automatic": {}},
                "labels": {"environment": "production"}
            }
            client.create_secret(
                request={
                    "parent": f"projects/{project_id}",
                    "secret_id": secret_id,
                    "secret": secret
                }
            )
            print(f"✅ Created secret {secret_id}")
        
        # Determine the value to set
        if value is None:
            value = generate_secure_token()
            print(f"🔑 Generated new random value for {secret_id}")
        else:
            print(f"🔑 Using provided value for {secret_id}")
        
        # Add a new version of the secret
        response = client.add_secret_version(
            request={
                "parent": parent,
                "payload": {"data": value.encode("UTF-8")}
            }
        )
        
        print(f"✅ Successfully rotated secret {secret_id} (version: {response.name.split('/')[-1]})")
        
        # Optional: Destroy old versions (keep only the last N versions)
        # For simplicity, we'll keep all versions, but in production you might want to limit
        # Uncomment the following lines to destroy versions older than 30 days
        # cutoff_time = datetime.utcnow() - timedelta(days=30)
        # versions = client.list_secret_versions(request={"parent": parent})
        # for version in versions:
        #     if version.create_time < cutoff_time and version.state != secretmanager.SecretVersion.State.DESTROYED:
        #         client.destroy_secret_version(request={"name": version.name})
        #         print(f"🗑️  Destroyed old version {version.name.split('/')[-1]} of {secret_id}")
        
        return True
        
    except ImportError:
        print("❌ Error: google-cloud-secret-manager is not installed")
        print("Install it with: pip install google-cloud-secret-manager")
        return False
    except Exception as e:
        print(f"❌ Failed to rotate secret {secret_id}: {e}")
        return False

def main() -> None:
    """Main function to rotate secrets based on environment variables."""
    # Get configuration from environment
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        print("❌ Error: GOOGLE_CLOUD_PROJECT environment variable is not set")
        sys.exit(1)
    
    secret_ids_str = os.getenv("SECRET_IDS", "")
    if not secret_ids_str:
        print("❌ Error: SECRET_IDS environment variable is not set")
        print("Set it to a comma-separated list of secret IDs to rotate")
        sys.exit(1)
    
    secret_ids = [sid.strip() for sid in secret_ids_str.split(",") if sid.strip()]
    if not secret_ids:
        print("❌ Error: No valid secret IDs provided in SECRET_IDS")
        sys.exit(1)
    
    # Optional: rotation frequency check (if you want to skip if recently rotated)
    # We'll skip this for simplicity and rotate every time the script runs
    # In a production cron job, you might want to check the last rotation time
    
    print(f"🔐 Starting secret rotation for {len(secret_ids)} secret(s) in project {project_id}")
    print(f"📋 Secrets to rotate: {', '.join(secret_ids)}")
    
    success_count = 0
    for secret_id in secret_ids:
        # Allow per-secret value override via env var: e.g., FIREBASE_API_KEY_VALUE
        value_env = f"{secret_id.upper().replace('-', '_')}_VALUE"
        value = os.getenv(value_env)
        
        if rotate_secret(secret_id, project_id, value):
            success_count += 1
    
    print(f"\n📊 Rotation complete: {success_count}/{len(secret_ids)} secrets rotated successfully")
    
    if success_count < len(secret_ids):
        sys.exit(1)
    else:
        print("🎉 All secrets rotated successfully!")

if __name__ == "__main__":
    main()