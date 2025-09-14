#!/usr/bin/env python3
"""
One-time database setup script for Render deployment
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from deploy_db import create_production_database

if __name__ == "__main__":
    print("🚀 Running database setup for Render deployment...")
    success = create_production_database()
    
    if success:
        print("\n🎉 Database setup completed successfully!")
        print("Your MediCare AI Assistant is ready!")
    else:
        print("\n❌ Database setup failed!")
        sys.exit(1)
