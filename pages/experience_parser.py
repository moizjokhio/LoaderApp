"""
Experience Parser Page - Extract experience from merged candidate documents
"""
import streamlit as st
import pandas as pd
import time
from config import SESSION_CV_RESULTS
from utils.api_client import get_api_keys, create_groq_client_with_fallback
from utils.excel_export import convert_df_to_excel
from extractors.cv_extractor import process_cv_multipage


def experience_parser_page():
    """CV/Experience Parser Page - Extract EXPERIENCE data from merged candidate documents."""
    st.markdown('<div class="main-header">👔 Experience Parser</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Extract experience from CIF, Resume/CV & Experience Letters</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.info("📋 **Two-Pass Hybrid + OCR**: Upload merged candidate documents (multi-page PDFs). System intelligently identifies document sections and extracts experience with OCR support for scanned pages.")
    
    # File uploader
    st.markdown("### 📤 Upload Candidate Documents")
    uploaded_cv_files = st.file_uploader(
        "Upload merged candidate PDFs (contains CIF + CV + Experience Letters)",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload complete merged candidate documents. System extracts experience from all sections.",
        key="cv_uploader"
    )
    
    # Display uploaded files
    if uploaded_cv_files:
        st.markdown(f"**📁 {len(uploaded_cv_files)} file(s) uploaded**")
        for file in uploaded_cv_files:
            st.markdown(f"- 📄 **{file.name}**")
    
    st.markdown("---")
    
    # Process button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        api_keys = get_api_keys()
        process_cv_button = st.button(
            "🔍 Extract Experience Data",
            type="primary",
            use_container_width=True,
            disabled=(not api_keys or not uploaded_cv_files)
        )
    
    # Process CVs
    if process_cv_button:
        api_keys = get_api_keys()
        
        if not any(k for k in api_keys):
            st.error("⚠️ Please configure your Groq API Keys in Settings page.")
        elif not uploaded_cv_files:
            st.error("⚠️ Please upload at least one CV/Resume PDF.")
        else:
            # Process each CV
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, file in enumerate(uploaded_cv_files):
                status_text.text(f"📄 Processing {file.name}... ({idx + 1}/{len(uploaded_cv_files)})")
                
                try:
                    # Process CV using fallback keys
                    cv_data = create_groq_client_with_fallback(api_keys, process_cv_multipage, file)
                    cv_data['source_file'] = file.name
                    results.append(cv_data)
                    
                    # Show OCR info if used
                    if cv_data.get('ocr_used_pages'):
                        st.info(f"🔍 OCR used for pages: {', '.join(map(str, cv_data['ocr_used_pages']))}")
                    
                    # Add delay between requests
                    if idx < len(uploaded_cv_files) - 1:
                        time.sleep(2.0)
                    
                except Exception as e:
                    st.error(f"❌ Error processing {file.name}: {str(e)}")
                
                # Update progress
                progress_bar.progress((idx + 1) / len(uploaded_cv_files))
            
            # Store results in session state (append mode)
            if SESSION_CV_RESULTS not in st.session_state:
                st.session_state[SESSION_CV_RESULTS] = []
            st.session_state[SESSION_CV_RESULTS].extend(results)
            
            status_text.empty()
            progress_bar.empty()
            st.success(f"✅ Successfully processed {len(results)} candidate document(s)!")
            st.rerun()
    
    # Display results
    if SESSION_CV_RESULTS in st.session_state and st.session_state[SESSION_CV_RESULTS]:
        st.markdown("---")
        st.markdown("## 📊 Extraction Results")
        
        # Clear button
        if st.button("🗑️ Clear All Results", use_container_width=True):
            st.session_state[SESSION_CV_RESULTS] = []
            st.rerun()
        
        st.markdown("---")
        
        # SUMMARY TABLE
        st.markdown("### 📋 Experience Summary")
        summary_data = []
        for cv in st.session_state[SESSION_CV_RESULTS]:
            personal = cv.get('personal_info', {})
            exp_cif = cv.get('experience_in_cif', {})
            exp_resume = cv.get('experience_in_resume', {})
            exp_letter = cv.get('experience_letter_found', {})
            
            summary_data.append({
                'Name': personal.get('full_name', 'Unknown'),
                'CNIC': personal.get('cnic', ''),
                'Email': personal.get('email', ''),
                'Contact': personal.get('contact', ''),
                'Experience in CIF': 'YES' if exp_cif.get('found') else 'NO',
                'CIF Details': exp_cif.get('details', ''),
                'Experience in Resume': 'YES' if exp_resume.get('found') else 'NO',
                'Resume Details': exp_resume.get('details', ''),
                'Experience Letter Attached': 'YES' if exp_letter.get('found') else 'NO',
                'Letter Details': exp_letter.get('details', ''),
                'Total Experience Records': len(cv.get('all_experiences', [])),
                'Source File': cv.get('source_file', '')
            })
        
        df_summary = pd.DataFrame(summary_data)
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
        
        # DETAILED EXPERIENCE TABLE
        st.markdown("### 💼 Detailed Work Experience")
        detailed_exp = []
        for cv in st.session_state[SESSION_CV_RESULTS]:
            personal = cv.get('personal_info', {})
            name = personal.get('full_name', 'Unknown')
            cnic = personal.get('cnic', '')
            
            for exp in cv.get('all_experiences', []):
                detailed_exp.append({
                    'Name': name,
                    'CNIC': cnic,
                    'Source': exp.get('source', ''),
                    'Employer': exp.get('employer', ''),
                    'Designation/Grade': exp.get('designation', ''),
                    'Date of Joining': exp.get('date_joining', ''),
                    'Date of Leaving': exp.get('date_leaving', ''),
                    'Duration (Months)': exp.get('duration_months', ''),
                    'Monthly Salary': exp.get('monthly_salary', ''),
                    'Responsibilities': exp.get('responsibilities', ''),
                    'Source File': cv.get('source_file', '')
                })
        
        if detailed_exp:
            df_detailed = pd.DataFrame(detailed_exp)
            st.dataframe(df_detailed, use_container_width=True, hide_index=True)
        else:
            st.warning("⚠️ No experience records found in processed documents")
        
        # Download buttons
        st.markdown("---")
        st.markdown("### 📥 Download Extracted Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if not df_summary.empty:
                summary_excel = convert_df_to_excel(df_summary, "Experience Summary")
                st.download_button(
                    label="📥 Download Experience Summary",
                    data=summary_excel,
                    file_name="experience_summary.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        
        with col2:
            if detailed_exp:
                detailed_excel = convert_df_to_excel(df_detailed, "Detailed Experience")
                st.download_button(
                    label="📥 Download Detailed Experience",
                    data=detailed_excel,
                    file_name="detailed_experience.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
