"""
Document Parser Page
UI for processing Pakistani educational documents (Degrees, Transcripts, Marksheets)
"""

import streamlit as st
import pandas as pd
import json
import time

from utils.api_client import get_api_keys, create_groq_client_with_fallback
from utils.excel_export import convert_df_to_excel
from extractors.document_extractor import process_document


def document_parser_page(person_number: str):
    """Document Parser Page - Extract data from educational documents."""
    st.markdown('<div class="main-header">🎓 EduParser</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Pakistani Educational Document Parser powered by Groq (Lightning Fast & Free)</div>', unsafe_allow_html=True)
    
    # File uploader
    st.markdown("### 📤 Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload educational documents (Degrees, Transcripts, Marksheets)",
        type=["jpg", "jpeg", "png", "pdf"],
        accept_multiple_files=True,
        help="Accepts JPG, PNG, and PDF files. PDFs will be converted to images automatically."
    )
    
    # Display uploaded files preview
    if uploaded_files:
        st.markdown(f"**📁 {len(uploaded_files)} file(s) uploaded**")
        
        # Show preview in columns
        cols = st.columns(min(len(uploaded_files), 4))
        for idx, file in enumerate(uploaded_files):
            with cols[idx % 4]:
                if file.name.lower().endswith('.pdf'):
                    st.markdown(f"📄 **{file.name}**")
                    st.caption("PDF file (will be converted to image)")
                else:
                    try:
                        st.image(file, caption=file.name, use_container_width=True)
                    except Exception as e:
                        st.warning(f"⚠️ Could not preview {file.name}")
                        st.caption(f"Image may be corrupted but will still be processed")
    
    st.markdown("---")
    
    # Process button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Get API keys
        api_keys = get_api_keys()
        has_valid_keys = any(k for k in api_keys)
        
        process_button = st.button(
            "🚀 Process Documents",
            type="primary",
            use_container_width=True,
            disabled=not (uploaded_files and has_valid_keys)
        )
    
    # Initialize session state for results
    if "results_df" not in st.session_state:
        st.session_state.results_df = None
    
    if "processed_files" not in st.session_state:
        st.session_state.processed_files = set()
    
    if "show_clear_confirmation" not in st.session_state:
        st.session_state.show_clear_confirmation = False
    
    # Processing logic
    if process_button:
        api_keys = get_api_keys()
        
        if not any(k for k in api_keys):
            st.error("⚠️ Please configure your Groq API Keys in Settings page.")
        elif not uploaded_files:
            st.error("⚠️ Please upload at least one document image.")
        elif not person_number:
            st.warning("⚠️ Person Number is empty. Records will be created without it.")
            
        if any(k for k in api_keys) and uploaded_files:
            # Process each document with fallback support
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, file in enumerate(uploaded_files):
                status_text.text(f"Processing {file.name}... ({idx + 1}/{len(uploaded_files)})")
                
                try:
                    # Process the document using fallback keys
                    documents = create_groq_client_with_fallback(api_keys, process_document, file)
                    
                    # Add person number and source file to each document
                    for doc_idx, result in enumerate(documents):
                        result["Person Number"] = person_number if person_number else ""
                        result["Source File"] = file.name
                        
                        # If multiple docs in one file, add document number
                        if len(documents) > 1:
                            result["Source File"] = f"{file.name} (Doc {doc_idx + 1}/{len(documents)})"
                        
                        results.append(result)
                    
                    # Show info if multiple documents detected
                    if len(documents) > 1:
                        st.info(f"ℹ️ {file.name}: Found {len(documents)} documents in this file")
                    
                    # Add delay between requests to avoid rate limits (2 seconds)
                    if idx < len(uploaded_files) - 1:  # Don't delay after last file
                        time.sleep(2.0)
                    
                except json.JSONDecodeError as e:
                    st.error(f"❌ Failed to parse response for {file.name}: {str(e)}")
                except Exception as e:
                    error_msg = str(e)
                    
                    # Handle invalid/corrupted images
                    if "Invalid or corrupted image" in error_msg:
                        st.warning(f"⚠️ Skipped {file.name}: Invalid or corrupted image file")
                    else:
                        st.error(f"❌ Error processing {file.name}: {str(e)}")
                
                # Update progress
                progress_bar.progress((idx + 1) / len(uploaded_files))
            
            status_text.text("✅ Processing complete!")
            
            # Create DataFrame
            if results:
                # Define column order for Oracle compatibility
                column_order = [
                    "Person Number",
                    "Name",
                    "Degree Start Date",
                    "Degree End Date",
                    "Average Grade",
                    "Education Level",
                    "Degree Name",
                    "Major",
                    "School",
                    "Percentage",
                    "Graduated",
                    "Country Code",
                    "Source File"
                ]
                
                df = pd.DataFrame(results)
                
                # Reorder columns (only include columns that exist)
                existing_cols = [col for col in column_order if col in df.columns]
                other_cols = [col for col in df.columns if col not in column_order]
                df = df[existing_cols + other_cols]
                
                # Append to existing results instead of replacing
                if st.session_state.results_df is not None:
                    st.session_state.results_df = pd.concat([st.session_state.results_df, df], ignore_index=True)
                else:
                    st.session_state.results_df = df
                
                # Track processed files
                for file in uploaded_files:
                    st.session_state.processed_files.add(file.name)
                
                st.success(f"✅ Successfully processed {len(results)} document(s)! Total records: {len(st.session_state.results_df)}")
    
    # Display results
    if st.session_state.results_df is not None and not st.session_state.results_df.empty:
        st.markdown("---")
        
        # Info banner and clear button
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📌 **{len(st.session_state.results_df)} records** | Processed files: {len(st.session_state.processed_files)} | Data persists during session")
        with col2:
            if st.button("🗑️ Clear All", use_container_width=True, type="secondary"):
                st.session_state.show_clear_confirmation = True
        
        # Confirmation modal
        if st.session_state.show_clear_confirmation:
            st.warning("⚠️ **Are you sure you want to clear all data?** This action cannot be undone.")
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                if st.button("✅ Yes, Clear", type="primary", use_container_width=True):
                    # Clear session state
                    st.session_state.results_df = None
                    st.session_state.processed_files = set()
                    st.session_state.show_clear_confirmation = False
                    st.rerun()
            with col2:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.show_clear_confirmation = False
                    st.rerun()
        
        st.markdown("### 📊 Extracted Data")
        
        # Display DataFrame
        st.dataframe(
            st.session_state.results_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Download button
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            excel_data = convert_df_to_excel(st.session_state.results_df)
            st.download_button(
                label="📥 Download Excel File",
                data=excel_data,
                file_name="education_data_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
        
        # Summary statistics
        st.markdown("---")
        st.markdown("### 📈 Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Records", len(st.session_state.results_df))
        
        with col2:
            if "Education Level" in st.session_state.results_df.columns:
                unique_levels = st.session_state.results_df["Education Level"].nunique()
                st.metric("Education Levels", unique_levels)
        
        with col3:
            if "School" in st.session_state.results_df.columns:
                unique_schools = st.session_state.results_df["School"].nunique()
                st.metric("Institutions", unique_schools)
        
        with col4:
            if "Graduated" in st.session_state.results_df.columns:
                graduated = (st.session_state.results_df["Graduated"] == "Y").sum()
                st.metric("Graduated", graduated)
