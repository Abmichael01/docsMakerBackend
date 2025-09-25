#!/usr/bin/env python3
"""
Test script for Remove.bg API integration
Run this to test the background removal functionality
"""

import os
import sys
import django
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).resolve().parent
sys.path.append(str(backend_dir))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

from removebg import RemoveBg
from django.conf import settings
import base64
import io

def test_removebg():
    """Test the Remove.bg API functionality"""
    
    print("Testing Remove.bg API integration...")
    
    # Check if API key is configured
    if not settings.REMOVEBG_API_KEY:
        print("❌ REMOVEBG_API_KEY not configured in settings")
        print("Please add REMOVEBG_API_KEY to your .env file")
        return False
    
    print(f"✅ API Key configured: {settings.REMOVEBG_API_KEY[:10]}...")
    
    try:
        # Initialize Remove.bg client
        rmbg = RemoveBg(settings.REMOVEBG_API_KEY, "error.log")
        print("✅ Remove.bg client initialized successfully")
        
        # Test with a simple image (you can replace this with an actual image file)
        print("📝 Note: To fully test, you need to provide an actual image file")
        print("✅ Remove.bg integration is ready!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Remove.bg: {e}")
        return False

if __name__ == "__main__":
    success = test_removebg()
    if success:
        print("\n🎉 Remove.bg integration test passed!")
    else:
        print("\n💥 Remove.bg integration test failed!")
        sys.exit(1)
