"""
API Client Management - Groq API with automatic fallback support
"""
import streamlit as st
from groq import Groq
import os
from config import ENV_API_KEY_PRIMARY, ENV_API_KEY_2, ENV_API_KEY_3, SESSION_API_KEYS


def get_api_keys():
    """
    Get API keys from environment variables or session state with fallback support.
    Returns up to 5 API keys.
    """
    keys = []
    
    # Primary key from session state (Settings page)
    if SESSION_API_KEYS in st.session_state and st.session_state[SESSION_API_KEYS]:
        keys.extend(st.session_state[SESSION_API_KEYS])
    
    # Additional keys from environment variables
    env_keys = [
        os.getenv(ENV_API_KEY_PRIMARY),
        os.getenv(ENV_API_KEY_2),
        os.getenv(ENV_API_KEY_3)
    ]
    
    for key in env_keys:
        if key and key not in keys:
            keys.append(key)
    
    return keys[:5]  # Limit to 5 keys


def create_groq_client_with_fallback(api_keys, operation_func, *args, **kwargs):
    """
    Create Groq client and execute operation with automatic key fallback on rate limits.
    
    Args:
        api_keys: List of API keys to try
        operation_func: Function to execute (must accept client as first argument)
        *args, **kwargs: Arguments to pass to operation_func
    
    Returns:
        Result from operation_func
    
    Raises:
        Last encountered error if all keys fail
    """
    if not api_keys:
        raise ValueError("No API keys provided")
    
    last_error = None
    
    for idx, key in enumerate(api_keys):
        try:
            client = Groq(api_key=key)
            # Execute the operation with this client
            result = operation_func(client, *args, **kwargs)
            return result
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a rate limit error
            if "rate_limit" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower():
                if idx < len(api_keys) - 1:  # If there are more keys to try
                    st.warning(f"⚠️ API Key {idx + 1} hit rate limit. Switching to fallback key {idx + 2}...")
                    last_error = e
                    continue
                else:
                    st.error(f"❌ All API keys exhausted. Rate limit reached on all keys.")
                    raise e
            else:
                # Not a rate limit error, raise it
                raise
    
    # If we get here, all keys failed with rate limits
    if last_error:
        raise last_error
    raise ValueError("Failed to execute operation with any API key")
