"""
Settings Page
API Key management and configuration
"""

import streamlit as st

from utils.api_client import get_api_keys


def settings_page():
    """Settings Page - Configure API Keys and Application Settings."""
    st.markdown('<div class="main-header">⚙️ Settings</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Configure API Keys and Application Settings</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🔑 API Key Management")
    st.info("💡 Add multiple API keys for automatic fallback when rate limits are reached.")
    
    # Initialize session state for API keys
    if 'groq_api_keys' not in st.session_state:
        st.session_state['groq_api_keys'] = get_api_keys()
    
    # Display current keys
    st.markdown("#### Current API Keys:")
    
    keys_to_remove = []
    for idx, key in enumerate(st.session_state['groq_api_keys']):
        col1, col2 = st.columns([4, 1])
        with col1:
            masked_key = f"{key[:10]}...{key[-8:]}" if key and len(key) > 18 else "Empty"
            st.text_input(
                f"API Key {idx + 1}",
                value=masked_key,
                disabled=True,
                key=f"key_display_{idx}"
            )
        with col2:
            if st.button("🗑️", key=f"remove_{idx}"):
                keys_to_remove.append(idx)
    
    # Remove keys marked for deletion
    for idx in reversed(keys_to_remove):
        st.session_state['groq_api_keys'].pop(idx)
        st.rerun()
    
    # Add new key
    st.markdown("#### Add New API Key:")
    new_key = st.text_input(
        "Enter API Key",
        type="password",
        placeholder="gsk_...",
        key="new_api_key_input"
    )
    
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("➕ Add Key", use_container_width=True):
            if new_key and new_key not in st.session_state['groq_api_keys']:
                st.session_state['groq_api_keys'].append(new_key)
                st.success("✅ API Key added successfully!")
                st.rerun()
            elif new_key in st.session_state['groq_api_keys']:
                st.warning("⚠️ This key already exists!")
            else:
                st.error("⚠️ Please enter a valid API key")
    
    st.markdown("---")
    st.markdown("### 📚 Resources")
    st.markdown("""
    - Get free API keys: [Groq Console](https://console.groq.com/keys)
    - API Documentation: [Groq Docs](https://console.groq.com/docs)
    - Rate Limits: 30 requests/minute per key
    """)
    
    st.markdown("---")
    st.markdown(f"**Total Keys Configured:** {len([k for k in st.session_state['groq_api_keys'] if k])}")
