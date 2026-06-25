#!/usr/bin/env python
"""
auto_firestore_backup.py
========================
Automatically creates backups of Firestore databases and exports them to Google Cloud Storage.

This script creates a managed export of Firestore data to a Cloud Storage bucket,
which can be used for disaster recovery, auditing, or data migration.

Environment Variables:
- GOOGLE_CLOUD_PROJECT: Google Cloud project ID
- FIRESTORE_DATABASE_ID: Firestore database ID (default: "(default)")
- BACKUP_BUCKET: Google Cloud Storage bucket for backups (required)
- BACKUP_PREFIX: Prefix for backup files (default: "firestore-backup")
- RETENTION_DAYS: Number of days to retain backups (default: 30)
- LOCATION_ID: Firestore database location (optional, uses project default if not set)
- USE_SNAPSHOT: Whether to use consistent snapshot (default: true)
- COLLECTION_IDS: Comma-separated list of collection IDs to export (empty = all)
"""

import os
import sys
import json
from datetime import datetime, timedelta
from google.cloud import firestore, storage
from google.api_core import exceptions
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID", "(default)")
BACKUP_BUCKET = os.getenv("BACKUP_BUCKET")
BACKUP_PREFIX = os.getenv("BACKUP_PREFIX", "firestore-backup")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
LOCATION_ID = os.getenv("LOCATION_ID")
USE_SNAPSHOT = os.getenv("USE_SNAPSHOT", "true").lower() == "true"
COLLECTION_IDS_STR = os.getenv("COLLECTION_IDS", "")

def validate_config() -> bool:
    """Validate required configuration."""
    if not PROJECT_ID:
        print("❌ Error: GOOGLE_CLOUD_PROJECT environment variable is not set")
        return False
    
    if not BACKUP_BUCKET:
        print("❌ Error: BACKUP_BUCKET environment variable is not set")
        return False
    
    # Validate bucket name format
    if not re.match(r'^[a-z0-9][a-z0-9\-_.]{1,61}[a-z0-9]$', BACKUP_BUCKET):
        print(f"⚠️  Warning: Bucket name '{BACKUP_BUCKET}' may not be valid")
    
    return True

def get_firestore_client():
    """Get a Firestore client instance."""
    try:
        if DATABASE_ID == "(default)":
            client = firestore.Client(project=PROJECT_ID)
        else:
            client = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)
        return client
    except Exception as e:
        logger.error(f"Failed to create Firestore client: {e}")
        return None

def get_storage_client():
    """Get a Cloud Storage client instance."""
    try:
        return storage.Client(project=PROJECT_ID)
    except Exception as e:
        logger.error(f"Failed to create Storage client: {e}")
        return None

def list_existing_backups(storage_client, bucket_name: str, prefix: str) -> list:
    """List existing backup files in the bucket."""
    try:
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=prefix)
        return [blob for blob in blobs if blob.name.endswith('.overall_export_metadata')]
    except Exception as e:
        logger.error(f"Error listing existing backups: {e}")
        return []

def delete_old_backups(storage_client, bucket_name: str, prefix: str, days_to_keep: int):
    """Delete backups older than the retention period."""
    try:
        bucket = storage_client.bucket(bucket_name)
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        
        blobs = bucket.list_blobs(prefix=prefix)
        deleted_count = 0
        
        for blob in blobs:
            # Check if the blob is older than the cutoff
            if blob.time_created < cutoff_time:
                blob.delete()
                deleted_count += 1
                logger.info(f"Deleted old backup: {blob.name}")
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old backup(s)")
        else:
            logger.info("No old backups to delete")
            
    except Exception as e:
        logger.error(f"Error deleting old backups: {e}")

def create_firestore_backup() -> bool:
    """Create a Firestore backup and export to Cloud Storage."""
    # Validate configuration
    if not validate_config():
        return False
    
    # Initialize clients
    firestore_client = get_firestore_client()
    storage_client = get_storage_client()
    
    if not firestore_client or not storage_client:
        return False
    
    # Generate backup timestamp and path
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{BACKUP_PREFIX}_{timestamp}"
    backup_path = f"gs://{BACKUP_BUCKET}/{backup_name}/"
    
    print(f"🔥 Starting Firestore backup...")
    print(f"📁 Project: {PROJECT_ID}")
    print(f"🗄️  Database: {DATABASE_ID}")
    print(f"📦 Bucket: {BACKUP_BUCKET}")
    print(f"📍 Backup path: {backup_path}")
    
    try:
        # Prepare export parameters
        database_path = f"projects/{PROJECT_ID}/databases/{DATABASE_ID}"
        
        # Build output URL prefix
        output_uri_prefix = backup_path
        
        # Prepare partition options if specific collections are requested
        partition_options = None
        collection_ids = None
        if COLLECTION_IDS_STR:
            collection_ids = [cid.strip() for cid in COLLECTION_IDS_STR.split(",") if cid.strip()]
            if collection_ids:
                partition_options = {
                    "collection_ids": collection_ids
                }
                print(f"📋 Exporting specific collections: {', '.join(collection_ids)}")
        
        # Create the export request
        request = {
            "name": f"{database_path}/exportDocuments/{backup_name}",
            "output_uri_prefix": output_uri_prefix,
        }
        
        if USE_SNAPSHOT:
            request["snapshot_time"] = {"seconds": int(datetime.utcnow().timestamp())}
        
        if partition_options:
            request["collection_ids"] = partition_options["collection_ids"]
        
        # Start the export operation
        print("⏳ Starting export operation...")
        operation = firestore_client._firestore_api.document_service_client.export_documents(
            request=request
        )
        
        print(f"✅ Export operation started: {operation.name}")
        print(f"💾 Backup will be available at: {backup_path}")
        print(f"⏳ Operation ID: {operation.name}")
        
        # Note: The operation runs asynchronously. In a production environment,
        # you would want to poll the operation status or use a Cloud Function
        # triggered by Pub/Sub when the operation completes.
        # For this script, we'll consider it started successfully.
        
        # Clean up old backups
        print(f"🧹 Cleaning up backups older than {RETENTION_DAYS} days...")
        delete_old_backups(storage_client, BACKUP_BUCKET, f"{BACKUP_PREFIX}_", RETENTION_DAYS)
        
        # Provide instructions for monitoring
        print("\n📋 Next steps:")
        print(f"   1. Monitor operation: gcloud firestore operations describe {operation.name} --project={PROJECT_ID}")
        print(f"   2. Check backup files: gsutil ls {backup_path}")
        print(f"   3. To restore: gcloud firestore import gs://{BACKUP_BUCKET}/{backup_name}/[latest-export-file]")
        
        return True
        
    except exceptions.GoogleAPICallError as e:
        logger.error(f"Google API error during backup: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during backup: {e}")
        return False

def main() -> int:
    """Main function to execute Firestore backup."""
    print("☁️  Starting Firestore Auto Backup...")
    
    success = create_firestore_backup()
    
    if success:
        print("\n✅ Firestore backup initiated successfully!")
        return 0
    else:
        print("\n❌ Failed to initiate Firestore backup!")
        return 1

if __name__ == "__main__":
    import re  # Import regex for validation
    sys.exit(main())