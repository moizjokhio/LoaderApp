"""
School Name Standardizer Page
Standardize school names in education data files using a reference school names list
"""

import streamlit as st
import pandas as pd

from utils.school_name_standardizer import load_reference_school_names, standardize_school_names
from utils.excel_export import convert_df_to_excel


def school_name_standardizer_page():
    """School Name Standardizer: Update school names to match case-sensitive reference."""
    st.markdown('<div class="main-header">🏫 School Name Standardizer</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Standardize school names to match Oracle\'s case-sensitive reference list</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Information box
    st.info("""
    **How it works:**
    1. Upload your education data file (with a 'School' column)
    2. Upload the reference school names file (School_names.xlsx)
    3. The tool uses **fuzzy matching** to find the best match from the reference list
    
    **Handles variations like:** 
    - "BISE, Sukkur" → "BISE,Sukkur" (spacing/punctuation differences)
    - "Federal Board, Islamabad" → "FBISE,ISLAMABAD" (abbreviations)
    - Case differences, extra spaces, etc.
    """)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📁 Education Data File")
        education_file = st.file_uploader(
            "Upload education data file",
            type=["xlsx", "xls", "csv"],
            key="education_data_file",
            help="Excel file with a 'School' column that needs standardization"
        )
        
        edu_df = None
        if education_file:
            try:
                if education_file.name.endswith('.csv'):
                    edu_df = pd.read_csv(education_file)
                else:
                    edu_df = pd.read_excel(education_file)
                
                if 'School' not in edu_df.columns:
                    st.error("❌ File must contain a 'School' column")
                    st.info(f"Available columns: {', '.join(edu_df.columns)}")
                    edu_df = None
                else:
                    st.success(f"✅ Loaded {len(edu_df)} records")
                    unique_schools = edu_df['School'].nunique()
                    st.info(f"📊 Found {unique_schools} unique school names")
                    
                    with st.expander("View sample data (first 5 rows)"):
                        st.dataframe(edu_df.head(5), use_container_width=True)
                    
                    with st.expander(f"View unique schools (first 20 of {unique_schools})"):
                        schools_list = edu_df['School'].dropna().unique()[:20]
                        for i, school in enumerate(schools_list, 1):
                            st.text(f"{i}. {school}")
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")
                edu_df = None
    
    with col2:
        st.markdown("### 📚 Reference School Names")
        reference_file = st.file_uploader(
            "Upload reference school names file",
            type=["xlsx", "xls", "csv"],
            key="school_reference_file",
            help="Excel file with correct case-sensitive school names (School_names.xlsx)"
        )
        
        school_lookup = None
        if reference_file:
            try:
                school_lookup = load_reference_school_names(reference_file)
                st.success(f"✅ Loaded {len(school_lookup)} reference school names")
                
                with st.expander("View reference schools (first 20)"):
                    sample_schools = school_lookup[:20]
                    for i, school in enumerate(sample_schools, 1):
                        st.text(f"{i}. {school}")
            except Exception as e:
                st.error(f"❌ Error reading reference file: {e}")
                school_lookup = None
    
    # Standardize button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        standardize_button = st.button(
            "🔧 Standardize School Names",
            type="primary",
            use_container_width=True,
            disabled=not (edu_df is not None and school_lookup is not None)
        )
    
    if standardize_button and edu_df is not None and school_lookup is not None:
        try:
            with st.spinner("Standardizing school names..."):
                # Standardize the school names
                standardized_df, stats = standardize_school_names(edu_df.copy(), school_lookup)
            
            # Display results
            st.markdown("---")
            st.markdown("### ✅ Standardization Complete!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", stats['total_schools'])
            with col2:
                st.metric("Updated", stats['updated_count'], 
                         delta=f"{(stats['updated_count']/stats['total_schools']*100):.1f}%" if stats['total_schools'] > 0 else "0%")
            with col3:
                st.metric("Not Found", stats['not_found_count'])
            
            # Show what was updated
            if stats['updated_count'] > 0:
                st.success(f"✅ Successfully updated {stats['updated_count']} school names to match reference!")
                
                # Show before/after comparison for updated schools with match scores
                with st.expander("View updated school names (before → after)"):
                    if stats.get('match_details'):
                        changes_df = pd.DataFrame(stats['match_details'])
                        changes_df.columns = ['Original', 'Matched To', 'Similarity Score']
                        changes_df['Similarity Score'] = changes_df['Similarity Score'].apply(lambda x: f"{x:.0%}")
                        st.dataframe(changes_df, use_container_width=True)
            else:
                st.info("ℹ️ No school names needed updating - they all match the reference!")
            
            # Show schools not found in reference
            if stats['not_found_count'] > 0:
                st.warning(f"⚠️ {stats['not_found_count']} school names not found in reference file (kept as-is)")
                with st.expander("View schools not in reference"):
                    for i, school in enumerate(stats['not_found_list'][:30], 1):
                        st.text(f"{i}. {school}")
                    if len(stats['not_found_list']) > 30:
                        st.text(f"... and {len(stats['not_found_list']) - 30} more")
            
            # Display standardized data
            st.markdown("---")
            st.markdown("### 📊 Standardized Data")
            st.dataframe(standardized_df, use_container_width=True, hide_index=True)
            
            # Download button
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                excel_data = convert_df_to_excel(standardized_df)
                st.download_button(
                    label="📥 Download Standardized Excel File",
                    data=excel_data,
                    file_name="standardized_school_names.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            
            # Show comparison sample
            st.markdown("---")
            st.markdown("### 📋 Sample Comparison (First 5 Rows)")
            comparison_cols = ['School'] + [col for col in standardized_df.columns if col != 'School'][:3]
            st.code(standardized_df[comparison_cols].head(5).to_string(index=False), language="text")
            
        except Exception as e:
            st.error(f"❌ Error standardizing school names: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
