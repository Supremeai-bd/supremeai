#!/usr/bin/env python
"""
auto_seed.py
============
Automatic database seeder for SupremeAI 2.0.

Seeds the database with initial data such as:
- Default skills
- Admin user (if not exists)
- Default configuration
- Free tier provider limits (if applicable)

This script should be idempotent - safe to run multiple times.
"""

import os
import sys
from pathlib import Path

# Add the backend directory to the path so we can import from core
backend_dir = Path(__file__).parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

def seed_database() -> None:
    """Seed the database with initial data."""
    try:
        # Import the necessary modules from your application
        # This will depend on your actual ORM and setup
        # For example, if using SQLAlchemy:
        from core.database import init_db, SessionLocal
        from core.models import User, Skill, Config
        from core.security import get_password_hash
        
        # Initialize database connection
        db = SessionLocal()
        
        try:
            # Check if we already have an admin user
            admin_email = "admin@supremeai.com"
            admin_user = db.query(User).filter(User.email == admin_email).first()
            if not admin_user:
                # Create admin user
                admin_user = User(
                    email=admin_email,
                    hashed_password=get_password_hash("SecureRandomPassword123!"),  # Should be changed on first login
                    is_admin=True,
                    is_active=True
                )
                db.add(admin_user)
                print("✅ Created admin user")
            else:
                print("ℹ️ Admin user already exists")
            
            # Seed default skills if none exist
            skill_count = db.query(Skill).count()
            if skill_count == 0:
                default_skills = [
                    {"name": "text_generation", "description": "Generate text from prompts", "category": "generation"},
                    {"name": "text_summarization", "description": "Summarize long texts", "category": "transformation"},
                    {"name": "question_answering", "description": "Answer questions based on context", "category": "reasoning"},
                    # Add more default skills as needed
                ]
                for skill_data in default_skills:
                    skill = Skill(**skill_data)
                    db.add(skill)
                print(f"✅ Seeded {len(default_skills)} default skills")
            else:
                print(f"ℹ️ Skipping seed - {skill_count} skills already exist")
            
            # Seed default configuration
            config_count = db.query(Config).count()
            if config_count == 0:
                default_configs = [
                    {"key": "system_maintenance_mode", "value": "false", "description": "Whether the system is in maintenance mode"},
                    {"key": "max_concurrent_requests", "value": "100", "description": "Maximum number of concurrent requests"},
                    # Add more default configs as needed
                ]
                for config_data in default_configs:
                    config = Config(**config_data)
                    db.add(config)
                print(f"✅ Seeded {len(default_configs)} default configurations")
            else:
                print(f"ℹ️ Skipping seed - {config_count} configurations already exist")
            
            # Commit all changes
            db.commit()
            print("✅ Database seeding completed successfully")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Error during seeding: {e}")
            raise
        finally:
            db.close()
            
    except ImportError as e:
        print(f"❌ Failed to import application modules: {e}")
        print("Make sure you're running this from the project root and the backend is in your PYTHONPATH")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    seed_database()