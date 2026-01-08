"""
EduParser - Pakistani Educational Document Parser
A Streamlit application for extracting data from educational documents using Groq AI

NEW MODULAR STRUCTURE:
- config.py: Configuration and constants
- utils/: Helper modules (API client, PDF processor, Excel export)
- extractors/: AI extraction modules (CV, Document, Spreadsheet)
- pages/: Streamlit page components
"""
import streamlit as st
from config import APP_TITLE, APP_ICON, APP_LAYOUT

# Import page modules
from pages.document_parser import document_parser_page
from pages.spreadsheet_loader import spreadsheet_loader_page
from pages.experience_parser import experience_parser_page
from pages.settings import settings_page


def apply_custom_css():
    """Apply custom CSS styling to the app."""
    st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: bold;
            color: #1E88E5;
            text-align: center;
            margin-bottom: 1rem;
        }
        .sub-header {
            font-size: 1.2rem;
            color: #424242;
            text-align: center;
            margin-bottom: 2rem;
        }
        .stButton>button {
            width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)


def main():
    """Main application function."""
    # Page configuration
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon=APP_ICON,
        layout=APP_LAYOUT
    )
    
    # Apply custom CSS
    apply_custom_css()
    
    # Sidebar navigation
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/graduation-cap.png", width=80)
        st.title("⚙️ Navigation")
        st.markdown("---")
        
        # Navigation
        page = st.radio(
            "Select Page",
            ["📄 Document Parser", "📊 Spreadsheet Loader", "👔 Experience Parser", "⚙️ Settings"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        
        # Person Number input (used by Document Parser)
        person_number = st.text_input(
            "👤 Person Number",
            placeholder="Enter Oracle Person Number",
            help="This number will be added to each record for Oracle import"
        )
        
        st.markdown("---")
        
        # Instructions
        st.markdown("### 📋 Quick Guide")
        st.markdown("""
        1. Configure API keys in Settings
        2. Upload documents or spreadsheets
        3. Enter the Person Number (for Document Parser)
        4. Click Process/Merge button
        5. Download the Excel file
        """)
        
        st.markdown("---")
        
        # Supported formats
        st.markdown("### 📄 Supported Documents")
        st.markdown("""
        - Matriculation / SSC
        - Intermediate / HSSC / FSc / FA
        - Bachelor Degrees
        - Master Degrees
        - Diplomas (DAE)
        - CV/Resume (multi-page PDF)
        - Experience Letters
        """)
    
    # Route to selected page
    if page == "📄 Document Parser":
        document_parser_page(person_number)
    elif page == "📊 Spreadsheet Loader":
        spreadsheet_loader_page()
    elif page == "👔 Experience Parser":
        experience_parser_page()
    elif page == "⚙️ Settings":
        settings_page()


if __name__ == "__main__":
    main()
