#!/usr/bin/env python3
"""
Gemini API Client — Singleton pattern for Hermes
Provides access to Google Gemini model for conversational AI
Uses google-generativeai SDK: https://github.com/google/generative-ai-python
"""

import os
import google.generativeai as genai

_model_instance = None
GEMINI_MODEL = "gemini-2.0-flash-lite"


class GeminiClientError(Exception):
    """Gemini client initialization error"""
    pass


def get_gemini_model():
    """Get or create Gemini model instance (singleton pattern)"""
    global _model_instance

    if _model_instance is None:
        # Try GOOGLE_API_KEY first, fallback to GEMINI_API_KEY
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise GeminiClientError("GOOGLE_API_KEY or GEMINI_API_KEY not found in environment")

        try:
            genai.configure(api_key=api_key)
            _model_instance = genai.GenerativeModel(GEMINI_MODEL)
        except Exception as e:
            raise GeminiClientError(f"Failed to initialize Gemini model: {str(e)}")

    return _model_instance


def reset_model():
    """Reset model instance (for testing)"""
    global _model_instance
    _model_instance = None
