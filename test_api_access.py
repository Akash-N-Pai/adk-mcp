#!/usr/bin/env python3
"""
Test script to verify API key access for the semantic evaluator.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_api_key_access():
    """Test if the API key is accessible."""
    print("Testing API key access...")
    
    # Check if API key is loaded
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        print(f"✅ API key found: {api_key[:10]}...{api_key[-4:]}")
        print(f"   Length: {len(api_key)} characters")
    else:
        print("❌ API key not found in environment")
        return False
    
    # Test ADK import
    try:
        from google.adk.agents import LlmAgent
        print("✅ Google ADK import successful")
    except ImportError as e:
        print(f"❌ Google ADK import failed: {e}")
        return False
    
    # Test model environment variable
    model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    print(f"✅ Model configuration: {model}")
    
    # Test LLM agent creation
    try:
        agent = LlmAgent(
            model=model,
            name="test_evaluator",
            instruction="You are a test evaluator."
        )
        print("✅ LLM agent creation successful")
        return True
    except Exception as e:
        print(f"❌ LLM agent creation failed: {e}")
        return False

if __name__ == "__main__":
    success = test_api_key_access()
    if success:
        print("\n🎉 All tests passed! The semantic evaluator should work correctly.")
    else:
        print("\n⚠️ Some tests failed. Check your setup.")
