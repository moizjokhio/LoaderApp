"""
Spreadsheet Loader Page
Merge employee data with education records using exact, fuzzy, and AI matching
"""

import streamlit as st
import pandas as pd
import time

from utils.api_client import get_api_keys, create_groq_client_with_fallback
from utils.excel_export import convert_df_to_excel
from extractors.spreadsheet_matcher import ai_match_names, normalize_name, fuzzy_match_names


def spreadsheet_loader_page():
    """Spreadsheet Loader: Merge employee data with education data."""
    st.markdown('<div class="main-header">📊 Spreadsheet Loader</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Merge employee data (CNIC, Employee Number, Name) with education records</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📁 File A: Employee Data")
        employee_file = st.file_uploader(
            "Upload employee file (CNIC, EMPLOYEE_NUMBER, FULL_NAME)",
            type=["xlsx", "xls", "csv"],
            key="employee_file",
            help="Excel file with columns: CNIC, EMPLOYEE_NUMBER, FULL_NAME"
        )
        
        if employee_file:
            try:
                if employee_file.name.endswith('.csv'):
                    emp_df = pd.read_csv(employee_file)
                else:
                    emp_df = pd.read_excel(employee_file)
                
                st.success(f"✅ Loaded {len(emp_df)} employee records")
                st.dataframe(emp_df.head(3), use_container_width=True)
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")
                emp_df = None
    
    with col2:
        st.markdown("### 📁 File B: Education Data")
        education_file = st.file_uploader(
            "Upload education file (from document parser)",
            type=["xlsx", "xls", "csv"],
            key="education_file",
            help="Excel file with education records (must have 'Name' column)"
        )
        
        if education_file:
            try:
                if education_file.name.endswith('.csv'):
                    edu_df = pd.read_csv(education_file)
                else:
                    edu_df = pd.read_excel(education_file)
                
                st.success(f"✅ Loaded {len(edu_df)} education records")
                st.dataframe(edu_df.head(3), use_container_width=True)
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")
                edu_df = None
    
    # Merge button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        merge_button = st.button(
            "🔗 Merge Files",
            type="primary",
            use_container_width=True,
            disabled=not (employee_file and education_file)
        )
    
    if merge_button and employee_file and education_file:
        try:
            # Load dataframes
            if employee_file.name.endswith('.csv'):
                emp_df = pd.read_csv(employee_file)
            else:
                emp_df = pd.read_excel(employee_file)
            
            if education_file.name.endswith('.csv'):
                edu_df = pd.read_csv(education_file)
            else:
                edu_df = pd.read_excel(education_file)
            
            # Normalize column names (case-insensitive)
            emp_df.columns = emp_df.columns.str.strip().str.upper()
            edu_df.columns = edu_df.columns.str.strip().str.title()
            
            # Check required columns
            required_emp_cols = ['CNIC', 'EMPLOYEE_NUMBER', 'FULL_NAME']
            missing_emp = [col for col in required_emp_cols if col not in emp_df.columns]
            
            if missing_emp:
                st.error(f"❌ Employee file missing columns: {', '.join(missing_emp)}")
                st.info(f"Available columns: {', '.join(emp_df.columns)}")
                return
            
            if 'Name' not in edu_df.columns:
                st.error("❌ Education file missing 'Name' column")
                st.info(f"Available columns: {', '.join(edu_df.columns)}")
                return
            
            # Get API keys for AI matching
            api_keys = get_api_keys()
            has_api_keys = any(k for k in api_keys)
            
            # Normalize names for matching using robust normalization
            emp_df['name_normalized'] = emp_df['FULL_NAME'].apply(normalize_name)
            edu_df['name_normalized'] = edu_df['Name'].apply(normalize_name)
            
            # Remove duplicates from employee data (keep first occurrence)
            emp_df_unique = emp_df.drop_duplicates(subset=['name_normalized'], keep='first')
            
            # First try exact matching
            merged_df = edu_df.merge(
                emp_df_unique[['CNIC', 'EMPLOYEE_NUMBER', 'FULL_NAME', 'name_normalized']],
                on='name_normalized',
                how='left'
            )
            
            # Find unmatched records for fuzzy matching
            unmatched_mask = merged_df['CNIC'].isna()
            unmatched_count_exact = unmatched_mask.sum()
            
            # Try fuzzy matching for unmatched records (word overlap method)
            if unmatched_count_exact > 0:
                st.info(f"🔍 Attempting fuzzy matching for {unmatched_count_exact} unmatched names...")
                
                merged_df, fuzzy_matched_count = fuzzy_match_names(merged_df, emp_df_unique, unmatched_mask)
                
                if fuzzy_matched_count > 0:
                    st.success(f"✅ Fuzzy matching found {fuzzy_matched_count} additional matches!")
            
            # Find remaining unmatched records for AI matching
            unmatched_mask = merged_df['CNIC'].isna()
            unmatched_edu_names = merged_df.loc[unmatched_mask, 'Name'].unique().tolist()
            
            # If there are unmatched records and API keys exist, use AI matching
            if len(unmatched_edu_names) > 0 and has_api_keys:
                st.info(f"🤖 Using AI to match {len(unmatched_edu_names)} unmatched names...")
                
                emp_names_list = emp_df_unique['FULL_NAME'].tolist()
                
                # AI matching in batches of 20 to avoid token limits
                ai_matches = {}
                batch_size = 20
                progress_bar = st.progress(0)
                
                for i in range(0, len(unmatched_edu_names), batch_size):
                    batch = unmatched_edu_names[i:i+batch_size]
                    # Use fallback keys for AI matching
                    batch_matches = create_groq_client_with_fallback(api_keys, ai_match_names, batch, emp_names_list)
                    ai_matches.update(batch_matches)
                    progress_bar.progress(min((i + batch_size) / len(unmatched_edu_names), 1.0))
                    time.sleep(0.5)  # Rate limiting
                
                progress_bar.empty()
                
                # Apply AI matches
                ai_matched_count = 0
                for edu_name, emp_match in ai_matches.items():
                    if emp_match:
                        emp_match_normalized = normalize_name(emp_match)
                        if emp_match_normalized in emp_df_unique['name_normalized'].values:
                            # Find the employee record
                            emp_row = emp_df_unique[emp_df_unique['name_normalized'] == emp_match_normalized].iloc[0]
                        
                            # Update the merged dataframe
                            mask = (merged_df['Name'] == edu_name) & (merged_df['CNIC'].isna())
                            merged_df.loc[mask, 'CNIC'] = emp_row['CNIC']
                            merged_df.loc[mask, 'EMPLOYEE_NUMBER'] = emp_row['EMPLOYEE_NUMBER']
                            merged_df.loc[mask, 'FULL_NAME'] = emp_row['FULL_NAME']
                            ai_matched_count += mask.sum()
                
                if ai_matched_count > 0:
                    st.success(f"✨ AI matched {ai_matched_count} additional records!")
            
            # Drop the normalized column
            merged_df = merged_df.drop('name_normalized', axis=1)
            
            # Reorder columns for Oracle format
            final_columns = [
                'CNIC',
                'EMPLOYEE_NUMBER',
                'FULL_NAME',
                'Father Name',
                'Country Code',
                'Degree Start Date',
                'Degree End Date',
                'Average Grade',
                'Education Level',
                'Degree Name',
                'Graduated',
                'Major',
                'School'
            ]
            
            # Only include columns that exist
            existing_final_cols = [col for col in final_columns if col in merged_df.columns]
            other_cols = [col for col in merged_df.columns if col not in final_columns]
            merged_df = merged_df[existing_final_cols + other_cols]
            
            # Rename columns to match Oracle format
            column_mapping = {
                'EMPLOYEE_NUMBER': 'EMP',
                'FULL_NAME': 'NAME',
                'Country Code': 'Nationality'
            }
            merged_df = merged_df.rename(columns=column_mapping)
            
            # Sort by date to ensure chronological order within each person's records
            # Convert date columns to datetime for proper sorting
            if 'Degree Start Date' in merged_df.columns:
                merged_df['Degree Start Date'] = pd.to_datetime(merged_df['Degree Start Date'], errors='coerce')
            if 'Degree End Date' in merged_df.columns:
                merged_df['Degree End Date'] = pd.to_datetime(merged_df['Degree End Date'], errors='coerce')
            
            # Sort by CNIC (to group each person together) and then by Degree Start Date (chronological order)
            sort_columns = ['CNIC']
            if 'Degree Start Date' in merged_df.columns:
                sort_columns.append('Degree Start Date')
            merged_df = merged_df.sort_values(by=sort_columns, na_position='last').reset_index(drop=True)
            
            # Convert dates back to M/D/YYYY format (without time) - cross-platform compatible
            def format_date(date_val):
                """Format datetime to M/D/YYYY without leading zeros"""
                if pd.isna(date_val):
                    return date_val
                return f"{date_val.month}/{date_val.day}/{date_val.year}"
            
            if 'Degree Start Date' in merged_df.columns:
                merged_df['Degree Start Date'] = merged_df['Degree Start Date'].apply(format_date)
            if 'Degree End Date' in merged_df.columns:
                merged_df['Degree End Date'] = merged_df['Degree End Date'].apply(format_date)
            
            # Check for unmatched records
            unmatched = merged_df[merged_df['CNIC'].isna()]
            matched = merged_df[merged_df['CNIC'].notna()]
            
            # Display results
            st.markdown("---")
            st.markdown("### ✅ Merge Complete!")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Records", len(merged_df))
            with col2:
                st.metric("Matched", len(matched))
            with col3:
                st.metric("Unmatched", len(unmatched))
            
            if len(unmatched) > 0:
                st.warning(f"⚠️ {len(unmatched)} education records could not be matched to employees")
                with st.expander("View unmatched records"):
                    st.dataframe(unmatched[['Name', 'Degree Name', 'School']], use_container_width=True)
            
            # Display merged data
            st.markdown("---")
            st.markdown("### 📊 Merged Data")
            st.dataframe(merged_df, use_container_width=True, hide_index=True)
            
            # Download button
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                excel_data = convert_df_to_excel(merged_df)
                st.download_button(
                    label="📥 Download Merged Excel File",
                    data=excel_data,
                    file_name="oracle_education_loader.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            
            # Show sample output format
            st.markdown("---")
            st.markdown("### 📋 Sample Output (First 3 Rows)")
            st.code(merged_df.head(3).to_string(index=False), language="text")
            
        except Exception as e:
            st.error(f"❌ Error merging files: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
