"""
EduParser - Pakistani Educational Document Parser
A Streamlit application for extracting data from educational documents using Google Gemini
"""

import streamlit as st
import pandas as pd
import base64
import json
from io import BytesIO
import google.generativeai as genai
import fitz  # PyMuPDF
from PIL import Image

# System prompt with all business logic rules
SYSTEM_PROMPT = """
You are an intelligent "Education Document Parser & Data Entry Specialist" for an Oracle system. Your job is to extract text from images of Pakistani educational documents (Degrees, Transcripts, Marksheets) and structure the data into a strict JSON format.

Objective:
Analyze the attached image(s), extract key details, and apply specific business logic to generate missing dates and codes.

CRITICAL RULES (Must Follow):
1. Date Calculation Logic (The "Hectic" Part)
Do not look for "Start Date" or "End Date" on the document; they are rarely written. You must calculate them based on the "Examination Year" (e.g., "Annual 2021", "Held in 2022") usually found at the top of the document. Do not use the "Date of Issue" found at the bottom.

If Matriculation / SSC / O-Level:
Degree End Date: 7/7/[Exam Year]
Degree Start Date: 5/5/[Exam Year - 2]
Example: "Annual 2022" -> Start: 5/5/2020, End: 7/7/2022.

If Intermediate / HSSC / FSc / FA / A-Level:
Degree End Date: 7/7/[Exam Year]
Degree Start Date: 8/8/[Exam Year - 2]
Example: "Annual 2024" -> Start: 8/8/2022, End: 7/7/2024.

If Associate's Degree / Diploma (DAE):
Degree End Date: 7/7/[Exam Year]
Degree Start Date: 8/8/[Exam Year - 2] Or 3 Year if specified by document.
Example: "Annual 2024" -> Start: 8/8/2022, End: 7/7/2024.

If University (Bachelor's/Master's) - Fall Session (Standard):
Degree End Date: 6/6/[Exam Year]
Degree Start Date: 9/9/[Exam Year - Duration] (Default duration: 4 years for BS, 2 years for BA/B.Com/Master's).

If University - Spring Session:
Degree End Date: 1/1/[Exam Year]
Degree Start Date: 1/1/[Exam Year - Duration].

2. Education Level Codes (Oracle Lookup)
Map the extracted degree to these exact codes:
32: Matriculation / SSC
30: Intermediate / HSSC / FSc / FA / I.Com
27: Bachelor's (BS, BA, B.Com, BSc, BBA)
26: Master's (MS, MSc, MBA, MA)
28: Associate's Degree
33: Diploma (DAE)

3. School/Board Name Standardization (Case Sensitive)
The system is case-sensitive. You must normalize the Board/University name.
For Matric/Inter: Do not write "Bise Lahore" or "Sargodha Board". Use the strict format: "BISE, [City]".
Valid List: BISE, Lahore; BISE, Gujranwala; BISE, Rawalpindi; BISE, Sargodha; BISE, Faisalabad; BISE, Multan; BISE, Bahawalpur; BISE, Dera Ghazi Khan; BISE, Sahiwal; BISE, Karachi; BISE, Hyderabad; BISE, Sukkur; BISE, Larkana; BISE, Mirpur Khas; BISE, Quetta; BISE, Peshawar; BISE, Abbottabad; BISE, Swat; BISE, Malakand; BISE, Kohat; BISE, Bannu; BISE, Mardan; BISE, Dera Ismail Khan; Federal Board, Islamabad; ZIAUDDIN UNIVERSITY EXAMINATION BOARD SINDH; Allama Iqbal Open University, Islamabad; Aga Khan University Examination Board.
For Technical: "Punjab Board of Technical Education" OR "Sindh Technical Education and Vocational Training Authority.
For University: Use the full official name (e.g., "University of Karachi", "University of the Punjab").

4. Grading Logic
Average Grade: Extract the letter grade (A1, A, B, C, D).
Conversion: If only "Division" is listed:
"First Division" = B (unless percentage is >80%, then A).
"Second Division" = C.
Percentage: Calculate as (Obtained Marks / Total Marks) * 100. Format as "XX.XX%".
GPA: Only extract if explicitly printed (e.g., 3.5). Otherwise, leave blank.

5. Multiple Documents Handling
IMPORTANT: Some images may contain MULTIPLE educational documents (e.g., Matric + Intermediate + Bachelor's all in one scan).
You MUST detect if there are multiple distinct educational documents in the image.
If multiple documents are found, extract each one separately.

6. Output Format (JSON)
Return ONLY a JSON object with a "documents" array. Do not include markdown formatting.

For SINGLE or MULTIPLE documents in image use same format:
{
  "documents": [
    {
      "Name": "Full name of the person (as written on the document)",
      "Degree Start Date": "D/M/YYYY",
      "Degree End Date": "D/M/YYYY",
      "Average Grade": "Grade or Converted Division",
      "Education Level": "Code",
      "Degree Name": "String",
      "Major": "String",
      "School": "Standardized Board Name",
      "Percentage": "XX.XX%",
      "Graduated": "Y",
      "Country Code": "PK"
    }
  ]
}
You must follow ALL rules strictly. Any deviation will lead to data rejection in the Oracle system."""


def convert_pdf_to_image(pdf_file) -> BytesIO:
    """Convert first page of PDF to image."""
    # Open PDF from bytes
    pdf_bytes = pdf_file.getvalue()
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Get first page
    page = pdf_document[0]
    
    # Render page to image at high resolution
    mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
    pix = page.get_pixmap(matrix=mat)
    
    # Convert to PIL Image
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    
    # Save to BytesIO
    img_bytes = BytesIO()
    img.save(img_bytes, format="JPEG", quality=95)
    img_bytes.seek(0)
    
    pdf_document.close()
    return img_bytes


def encode_image_to_base64(image_file) -> str:
    """Encode uploaded image file to base64 string."""
    return base64.b64encode(image_file.getvalue()).decode("utf-8")


def get_image_media_type(filename: str) -> str:
    """Get the media type based on file extension."""
    extension = filename.lower().split(".")[-1]
    media_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
    }
    return media_types.get(extension, "image/jpeg")


def process_document(model, image_file) -> list:
    """
    Process a single document image using Google Gemini.
    Can handle multiple documents in one image.
    
    Args:
        model: Gemini GenerativeModel instance
        image_file: Uploaded image file (JPG, PNG, or PDF)
        
    Returns:
        List of dictionaries (one per document found in the image)
    """
    # Handle PDF files - convert to image first
    if image_file.name.lower().endswith('.pdf'):
        image_bytes = convert_pdf_to_image(image_file)
        # Convert BytesIO to PIL Image for Gemini
        image_bytes.seek(0)
        img = Image.open(image_bytes)
    else:
        # Open image file directly
        img = Image.open(image_file)
    
    # Prepare the prompt
    prompt = f"""{SYSTEM_PROMPT}

Please analyze this image. It may contain ONE or MULTIPLE Pakistani educational documents. Extract all documents found and return them in the documents array.

Return ONLY valid JSON with no markdown formatting."""
    
    # Create the API request with Gemini
    response = model.generate_content(
        [prompt, img],
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1
        )
    )
    
    # Parse the JSON response
    response_text = response.text
    parsed_response = json.loads(response_text)
    
    # Handle both new format (with documents array) and legacy format (single object)
    if "documents" in parsed_response:
        return parsed_response["documents"]
    else:
        # Legacy format - wrap in array for consistency
        return [parsed_response]


def convert_df_to_excel(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to Excel bytes for download."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Education Data")
    return output.getvalue()


def main():
    """Main application function."""
    # Page configuration
    st.set_page_config(
        page_title="EduParser",
        page_icon="🎓",
        layout="wide"
    )
    
    # Custom CSS for better styling
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
            color: #666;
            text-align: center;
            margin-bottom: 2rem;
        }
        .success-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #E8F5E9;
            border: 1px solid #4CAF50;
        }
        .error-box {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #FFEBEE;
            border: 1px solid #F44336;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Sidebar configuration
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/graduation-cap.png", width=80)
        st.title("⚙️ Configuration")
        st.markdown("---")
        
        # API Key input
        api_key = st.text_input(
            "🔑 Google Gemini API Key",
            type="password",
            value="",
            help="Enter your Google Gemini API key (free tier available at https://aistudio.google.com/apikey)"
        )
        
        st.markdown("---")
        
        # Person Number input
        person_number = st.text_input(
            "👤 Person Number",
            placeholder="Enter Oracle Person Number",
            help="This number will be added to each record for Oracle import"
        )
        
        st.markdown("---")
        
        # Instructions
        st.markdown("### 📋 Instructions")
        st.markdown("""
        1. Get free API key from [Google AI Studio](https://aistudio.google.com/apikey)
        2. Enter your Gemini API Key
        3. Enter the Person Number
        4. Upload document images/PDFs
        5. Click **Process Documents**
        6. Download the Excel file
        """)
        
        st.markdown("---")
        
        # Supported formats
        st.markdown("### 📄 Supported Documents")
        st.markdown("""
        - Matriculation / SSC
        - Intermediate / HSSC / FSc / FA
        - Bachelor's Degrees
        - Master's Degrees
        - Diplomas (DAE)
        """)
    
    # Main area
    st.markdown('<div class="main-header">🎓 EduParser</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Pakistani Educational Document Parser powered by Google Gemini/div>', unsafe_allow_html=True)
    
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
                    st.image(file, caption=file.name, use_container_width=True)
    
    st.markdown("---")
    
    # Process button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        process_button = st.button(
            "🚀 Process Documents",
            type="primary",
            use_container_width=True,
            disabled=not (uploaded_files and api_key)
        )
    
    # Initialize session state for results
    if "results_df" not in st.session_state:
        st.session_state.results_df = None
    
    # Processing logic
    if process_button:
        if not api_key:
            st.error("⚠️ Please enter your Google Gemini API Key in the sidebar.")
        elif not uploaded_files:
            st.error("⚠️ Please upload at least one document image.")
        elif not person_number:
            st.warning("⚠️ Person Number is empty. Records will be created without it.")
            
        if api_key and uploaded_files:
            # Initialize Gemini
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # Process each document
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, file in enumerate(uploaded_files):
                status_text.text(f"Processing {file.name}... ({idx + 1}/{len(uploaded_files)})")
                
                try:
                    # Process the document (may return multiple records if merged)
                    documents = process_document(model, file)
                    
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
                    
                except json.JSONDecodeError as e:
                    st.error(f"❌ Failed to parse response for {file.name}: {str(e)}")
                except Exception as e:
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
                
                st.session_state.results_df = df
                st.success(f"✅ Successfully processed {len(results)} document(s)!")
    
    # Display results
    if st.session_state.results_df is not None and not st.session_state.results_df.empty:
        st.markdown("---")
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


def spreadsheet_loader():
    """Spreadsheet Loader: Merge employee data with education data."""
    st.markdown("---")
    st.markdown("## 📊 Spreadsheet Loader")
    st.markdown("Merge employee data (CNIC, Employee Number, Name) with education records by matching names.")
    
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
            
            # Normalize names for matching (lowercase, strip whitespace)
            emp_df['name_normalized'] = emp_df['FULL_NAME'].str.lower().str.strip()
            edu_df['name_normalized'] = edu_df['Name'].str.lower().str.strip()
            
            # Remove duplicates from employee data (keep first occurrence)
            emp_df_unique = emp_df.drop_duplicates(subset=['name_normalized'], keep='first')
            
            # Perform merge
            merged_df = edu_df.merge(
                emp_df_unique[['CNIC', 'EMPLOYEE_NUMBER', 'FULL_NAME', 'name_normalized']],
                on='name_normalized',
                how='left'
            )
            
            # Drop the normalized column
            merged_df = merged_df.drop('name_normalized', axis=1)
            
            # Reorder columns for Oracle format
            final_columns = [
                'CNIC',
                'EMPLOYEE_NUMBER',
                'FULL_NAME',
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


if __name__ == "__main__":
    main()
    
    # Add Spreadsheet Loader section
    st.markdown("---")
    st.markdown("---")
    spreadsheet_loader()
