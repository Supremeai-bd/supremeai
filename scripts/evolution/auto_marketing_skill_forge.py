#!/usr/bin/env python
"""
auto_marketing_skill_forge.py
=============================
Automatically creates marketing-related skills based on user demand.

Monitors a Firestore collection for skill requests matching marketing platforms
and triggers the skill forging endpoint to generate new skills.

Environment Variables:
- GOOGLE_CLOUD_PROJECT: Google Cloud project ID
- FIREBASE_DATABASE_URL: Firebase Realtime Database URL (if using RTDB) 
  OR FIRESTORE_DATABASE_ID: Firestore database ID
- SUPREMEAI_API_BASE_URL: Base URL for the SupremeAI API (default: http://localhost:8000)
- SUPREMEAI_API_KEY: API key for authenticating to the internal API
- POLL_INTERVAL_SECONDS: How often to check for new requests (default: 300)
- MARKETING_PLATFORMS: Comma-separated list of platforms to watch for 
  (default: twitter,instagram,facebook,linkedin,tiktok,youtube)
"""

import os
import sys
import time
import json
import logging
from typing import Dict, List, Optional
import requests
from datetime import datetime, timezone, timedelta

# Add the backend directory to the path
backend_dir = os.path.join(os.path.dirname(__file__), '../../../backend')
sys_path_added = False
if backend_dir not in sys.path:
    sys.path.append(backend_dir)
    sys_path_added = True

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    print("⚠️  Firebase Admin SDK not installed. Install with: pip install firebase-admin")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
FIREBASE_DATABASE_ID = os.getenv("FIRESTORE_DATABASE_ID")  # Optional, defaults to project ID
API_BASE_URL = os.getenv("SUPREMEAI_API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("SUPREMEAI_API_KEY")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))  # 5 minutes
MARKETING_PLATFORMS = os.getenv(
    "MARKETING_PLATFORMS", 
    "twitter,instagram,facebook,linkedin,tiktok,youtube"
).lower().split(",")

# Collection names
REQUESTS_COLLECTION = "skill_requests"
PROCESSED_COLLECTION = "processed_skill_requests"

def initialize_firebase() -> Optional[firestore.Client]:
    """Initialize Firebase Admin SDK and return Firestore client."""
    if not FIREBASE_AVAILABLE:
        logger.error("Firebase SDK not available")
        return None
    
    try:
        # Check if already initialized
        app = firebase_admin.get_app()
    except ValueError:
        # Initialize with application default credentials
        cred = credentials.ApplicationDefault()
        options = {}
        if PROJECT_ID:
            options['projectId'] = PROJECT_ID
        if FIREBASE_DATABASE_ID:
            options['databaseId'] = FIREBASE_DATABASE_ID
        
        app = firebase_admin.initialize_app(cred, options)
    
    return firestore.client()

def get_pending_requests(db: firestore.Client) -> List[dict]:
    """
    Fetch pending skill requests that match marketing platforms.
    
    Returns a list of request documents that need processing.
    """
    try:
        # Check if not in the marketing.platform lower in the recently created_at - Exactly the user.
        we
    to
    try:
        # Check if already initialized
        app = firebase_admin.get_app()
    except ValueError:
        # Initialize with application default credentials
        cred = credentials.ApplicationDefault()
        options = {}
        if PROJECT_ID:
            options['projectId'] = PROJECT_ID
        if FIREBASE_DATABASE_ID:
            options['databaseId'] = FIREBASE_DATABASE_ID
        
        app = firebase_admin.initialize_app(cred, options)
    return firestore.client()
except Exception as e:
        logger.error(f"Error fetching pending requests: {e}")
        return []

def forge_skill(request_data: dict) -> bool:
    """
    Call the skill forging API to create a new skill based on the request.
    
    Args:
        request_data: The request document data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Prepare the payload for the forge endpoint
        # Based on the user's example: /api/evolution/forge
        payload = {
            "skill_name": f"{request_data.get('platform', 'unknown')}_marketing_bot",
            "user_demand": request_data.get('description', 
                                          f"Create a {request_data.get('platform')} marketing automation skill"),
            "category": "marketing",
            "platform": request_data.get('platform =_get('platform'),
            "requested_by": request_data.get('user_id', 'anonymous'),
            "priority": request_data.get('priority', 'medium')
        }
        
        # Make the API call
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}" if API_KEY else ""
        }
        
        url = f"{API_BASE_URL}/api/evolution/forge"
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Successfully forged skill: {result.get('skill_name')}")
            return True
        else:
            logger.error(f"Failed to forge skill. Status: {response.status_code}, Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error when forging skill: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error when forging skill: {e}")
        return False

def mark_request_as_processed(db: firestore.Client, request_id: str, success: bool) -> None:
    """
    Move the request to the processed collection and update the original with status.
    
    Args:
        db: Firestore client
        request_id: The ID of the request document
        success: Whether the forging was successful
    """
    try:
        # Get the original document
        doc_ref = db.collection(REQUESTS_COLLECTION).document(request_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            logger.warning(f"Request document {request_id} not found")
            return
        
        # Prepare update data
        update_data = {
            "processed_at": datetime.now(timezone.utc),
            "processed_success": success,
            "processing_log": f"Skill forging attempted at {datetime.now(timezone.utc).isoformat()}"
        }
        
        if success:
            update_data["status"] = "completed"
        else:
            update_data["status"] = "failed"
        
        # Update the original document
        doc_ref.update(update_data)
        
        # Optionally, copy to processed collection for audit
        # processed_ref = db.collection(PROCESSED_COLLECTION).document(request_id)
        # processed_ref.set(doc.to_dict() | update_data)
        
        logger.info(f"Marked request {request_id} as {'success' if success else 'failed'}")
        
    except Exception as e:
        logger.error(f"Error marking request {request_id} as processed: {e}")

def main() -> None:
    """Main loop that polls for requests and processes them."""
    if not PROJECT_ID:
        print("❌ Error: GOOGLE_CLOUD_PROJECT environment variable is not set")
        return
    
    if not API_KEY:
        print("⚠️  Warning: SUPREMEAI_API_KEY not set - API calls may fail")
    
    print(f"🤖 Starting Marketing Skill Forger")
    print(f"📊 Monitoring for platforms: {', '.join(MARKETING_PLATFORMS)}")
    print(f"⏱️  Polling interval: {POLL_INTERVAL} seconds")
    print(f"🔗 API endpoint: {API_BASE_URL}/api/evolution/forge")
    
    # Initialize Firebase
    db = initialize_firebase()
    if not db:
        print("❌ Failed to initialize Firebase. Exiting.")
        return
    
    print("✅ Firebase initialized successfully")
    
    try:
        while True:
            print(f"\n🔍 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for new requests...")
            
            # Get pending requests
            pending_requests = get_pending_requests(db)
            
            if not pending_requests:
                print("📭 No pending requests found")
            else:
                print(f"📥 Found {len(pending_requests)} pending request(s)")
                
                for request in pending_requests:
                    request_id = request.get('doc_id')
                    platform = request.get('platform', 'unknown')
                    print(f"  ⚙️  Processing request {request_id} for platform '{platform}'")
                    
                    # Attempt to forge the skill
                    success = forge_skill(request)
                    
                    # Mark the request as processed
                    mark_request_as_processed(db, request_id, success)
                    
                    if success:
                        print(f"  ✅ Successfully processed request {request_id}")
                    else:
                        print(f"  ❌ Failed to process request {request_id}")
            
            # Wait for the next poll
            print(f"😴 Sleeping for {POLL_INTERVAL} seconds...")
            time.sleep(POLL_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n� received. Shutting down gracefully...")
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()