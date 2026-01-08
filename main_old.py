"""
EduParser - Pakistani Educational Document Parser
A Streamlit application for extracting data from educational documents using Groq AI
"""

import streamlit as st
import pandas as pd
import base64
import json
from io import BytesIO
from groq import Groq
import fitz  # PyMuPDF
from PIL import Image, ImageFile
import time
import os

# OCR imports
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Allow loading of truncated images
ImageFile.LOAD_TRUNCATED_IMAGES = True

# Note: Browser storage functions temporarily disabled due to compatibility issues
# Data persists within the same session/tab until page reload

# API Key Management with Fallback Support
def get_api_keys():
    """Get API keys from environment variables or session state with fallback support."""
    keys = []
    
    # Primary key from session state (Settings page)
    if 'groq_api_keys' in st.session_state and st.session_state['groq_api_keys']:
        keys.extend(st.session_state['groq_api_keys'])
    
    # Fallback keys from environment variables
    env_keys = [
        os.getenv('GROQ_API_KEY'),
        os.getenv('GROQ_API_KEY_2'),
        os.getenv('GROQ_API_KEY_3'),
        os.getenv('GROQ_API_KEY_4'),
        os.getenv('GROQ_API_KEY_5')
    ]
    
    # Add valid environment keys
    for key in env_keys:
        if key and key not in keys:
            keys.append(key)
    
    return keys if keys else ['']

def create_groq_client_with_fallback(api_keys, operation_func, *args, **kwargs):
    """Try operation with primary key, fallback to other keys on rate limit.
    
    Args:
        api_keys: List of API keys to try
        operation_func: Function to execute (should accept client as first arg)
        *args, **kwargs: Arguments to pass to operation_func
    
    Returns:
        Result from operation_func
    """
    last_error = None
    
    for idx, key in enumerate(api_keys):
        if not key:
            continue
            
        try:
            client = Groq(api_key=key)
            return operation_func(client, *args, **kwargs)
            
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a rate limit error
            if "rate_limit" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower():
                if idx < len(api_keys) - 1:  # If there are more keys to try
                    st.warning(f"[!] API Key {idx + 1} hit rate limit. Switching to fallback key {idx + 2}...")
                    last_error = e
                    continue
                else:
                    st.error(f"[X] All API keys exhausted. Rate limit reached on all keys.")
                    raise e
            else:
                # Not a rate limit error, raise it
                raise e
    
    # If we get here, all keys failed
    if last_error:
        raise last_error
    else:
        raise ValueError("No valid API keys provided")

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

6. Name Extraction Logic - CRITICAL (Read Carefully)
CRITICAL: Pakistani educational documents ALWAYS show TWO names - the student's name and their father's name. You MUST distinguish between them correctly.

DOCUMENT LAYOUT PATTERNS (common in Pakistani certificates):
Pattern 1 (Most Common):
  Name: [STUDENT NAME HERE]
  Father's Name: [FATHER NAME HERE]
  
Pattern 2 (Vertical Layout):
  Name
  [STUDENT NAME HERE]
  Father's Name
  [FATHER NAME HERE]

Pattern 3 (Alternative Labels):
  Candidate Name: [STUDENT NAME]
  S/O (Son Of) / D/O (Daughter Of): [FATHER NAME]

CRITICAL RULES FOR NAME EXTRACTION:
✓ The field labeled "Name", "Student Name", or "Candidate Name" is ALWAYS the student
✓ The field labeled "Father's Name", "Father Name", or following "S/O"/"D/O" is ALWAYS the father
✓ The student's name typically appears BEFORE the father's name in the document
✓ If you see two names on the document WITHOUT clear labels:
  - The FIRST name listed is usually the student
  - The SECOND name (after a label like "Father's Name" or "S/O") is the father
✓ NEVER assume the longer name is the student or father - read the labels carefully

EXAMPLES (Learn from these):
Example 1:
  Document shows:
    Name: SHEHARYAR
    Father's Name: MUHAMMAD ARIF
  Correct Extraction:
    "Name": "SHEHARYAR"
    "Father Name": "MUHAMMAD ARIF"

Example 2:
  Document shows:
    Name: MUHAMMAD SHOAIB KHAN
    Father's Name: MUHAMMAD ARIF
  Correct Extraction:
    "Name": "MUHAMMAD SHOAIB KHAN"
    "Father Name": "MUHAMMAD ARIF"

Example 3:
  Document shows:
    Candidate Name: AYESHA KHAN
    D/O: AHMED KHAN
  Correct Extraction:
    "Name": "AYESHA KHAN"
    "Father Name": "AHMED KHAN"

TAKE YOUR TIME: Carefully read the field labels. Do NOT rush. Accuracy is more important than speed.

7. Output Format (JSON)
Return ONLY a JSON object with a "documents" array. Do not include markdown formatting.

For SINGLE or MULTIPLE documents in image use same format:
{
  "documents": [
    {
      "Name": "Full name of the candidate (student's name only)",
      "Father Name": "Father's full name (if available on document)",
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

FINAL REMINDER:
✓ Accuracy is MORE important than speed
✓ Take your time to carefully read each field label on the document
✓ Double-check that you are putting the correct name in the correct field
✓ The student's name goes in "Name" - NOT the father's name
✓ You must follow ALL rules strictly. Any deviation will lead to data rejection in the Oracle system."""


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


def process_document(client, image_file) -> list:
    """
    Process a single document image using Groq Vision API.
    Can handle multiple documents in one image.
    
    Args:
        client: Groq client instance
        image_file: Uploaded image file (JPG, PNG, or PDF)
        
    Returns:
        List of dictionaries (one per document found in the image)
    """
    # Handle PDF files - convert to image first
    if image_file.name.lower().endswith('.pdf'):
        image_bytes = convert_pdf_to_image(image_file)
        base64_image = base64.b64encode(image_bytes.getvalue()).decode("utf-8")
    else:
        # Validate image before encoding
        try:
            image_file.seek(0)  # Reset file pointer
            test_image = Image.open(image_file)
            test_image.verify()  # Verify it's a valid image
            image_file.seek(0)  # Reset again for encoding
        except Exception as e:
            raise Exception(f"Invalid or corrupted image file. The image may be damaged or in an unsupported format.")
        
        # Encode image to base64
        base64_image = encode_image_to_base64(image_file)
    
    # Prepare the prompt
    prompt = f"""{SYSTEM_PROMPT}

Please analyze this image. It may contain ONE or MULTIPLE Pakistani educational documents. Extract all documents found and return them in the documents array.

CRITICAL REMINDER: Look carefully at the field labels on the document:
- The field labeled "Name" or "Student Name" = Candidate's Name (put this in "Name" field)
- The field labeled "Father's Name" or "S/O"/"D/O" = Father's Name (put this in "Father Name" field)
- DO NOT mix these up. Read the labels carefully before extracting.

Return ONLY valid JSON with no markdown formatting."""
    
    # Retry logic for rate limiting
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # Create the API request with Groq
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.05,  # Lower temperature for more consistent, accurate extraction
                max_tokens=3000     # Increased tokens to give model more capacity for careful analysis
            )
            
            # Parse the JSON response
            response_text = response.choices[0].message.content
            
            # Clean markdown formatting if present
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            parsed_response = json.loads(response_text)
            
            # Handle both formats
            if "documents" in parsed_response:
                return parsed_response["documents"]
            else:
                return [parsed_response]
                
        except Exception as e:
            error_msg = str(e)
            
            # Handle rate limiting with retry
            if "rate" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(f"Rate limit exceeded after {max_retries} attempts. Please wait and try again.")
            
            # Handle invalid image data
            if "invalid image" in error_msg.lower() or "400" in error_msg:
                raise Exception(f"Invalid or corrupted image file. The image may be damaged or in an unsupported format.")
            
            # Re-raise other errors
            raise


def convert_df_to_excel(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to Excel bytes for download."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Education Data")
    return output.getvalue()


def extract_text_with_ocr(page, page_num: int, pdf_bytes: bytes) -> tuple:
    """
    Extract text from PDF page with OCR fallback.
    Returns: (text, used_ocr)
    """
    # Try normal text extraction first
    text = page.get_text()
    
    # If text is too short (likely scanned image), use OCR
    if len(text.strip()) < 50 and OCR_AVAILABLE:
        try:
            # Convert specific page to image
            images = convert_from_bytes(pdf_bytes, first_page=page_num+1, last_page=page_num+1, dpi=300)
            if images:
                # Perform OCR
                ocr_text = pytesseract.image_to_string(images[0], lang='eng')
                if len(ocr_text.strip()) > len(text.strip()):
                    return ocr_text, True
        except Exception as e:
            # OCR failed, use original text
            pass
    
    return text, False


def process_cv_multipage(client, pdf_file) -> dict:
    """
    TWO-PASS HYBRID + OCR APPROACH:
    
    Pass 1: Document Structure Discovery (AI analyzes sample pages)
        - Identify which pages contain: CIF, Resume, Experience Letters
        - Returns page ranges for each section
    
    Pass 2: Targeted Deep Extraction (3 focused AI calls)
        - Extract CIF experience (FULL text of CIF pages)
        - Extract Resume experience (FULL text of Resume pages)
        - Extract Experience Letters (FULL text of Letter pages)
    
    OCR: Automatic fallback for scanned/image pages
    
    Args:
        client: Groq client instance
        pdf_file: Uploaded PDF file
        
    Returns:
        Dictionary with extracted data
    """
    # Open PDF
    pdf_bytes = pdf_file.getvalue()
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(pdf_document)
    
    # Extract all pages with OCR fallback
    pages_data = []
    ocr_used_pages = []
    
    for page_num in range(total_pages):
        page = pdf_document[page_num]
        page_text, used_ocr = extract_text_with_ocr(page, page_num, pdf_bytes)
        
        pages_data.append({
            'page_num': page_num + 1,
            'text': page_text
        })
        
        if used_ocr:
            ocr_used_pages.append(page_num + 1)
    
    pdf_document.close()
    
    Args:
        client: Groq client instance
        pdf_file: Uploaded PDF file
        
    Returns:
        Dictionary with extracted data
    """
    # Open PDF and extract pages
    pdf_bytes = pdf_file.getvalue()
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Step 1: Extract and classify each page
    pages_data = []
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        page_text = page.get_text()
        page_type = classify_page_type(page_text)
        
        pages_data.append({
            'page_num': page_num + 1,
            'text': page_text,
            'type': page_type
        })
    
    pdf_document.close()
    
    # ========== PASS 1: DOCUMENT STRUCTURE DISCOVERY ==========
    # Create a sample of pages for structure analysis (first 3, middle 2, last 3)
    sample_pages = []
    
    # First 3 pages
    sample_pages.extend(pages_data[:3])
    
    # Middle 2 pages
    mid_point = total_pages // 2
    if total_pages > 6:
        sample_pages.extend(pages_data[mid_point:mid_point+2])
    
    # Last 3 pages
    if total_pages > 3:
        sample_pages.extend(pages_data[-3:])
    
    # Build sample text with page numbers
    sample_text = ""
    for p in sample_pages:
        sample_text += f"\n{'='*60}\nPAGE {p['page_num']} of {total_pages}\n{'='*60}\n"
        sample_text += p['text'][:1000]  # First 1000 chars of each sample page
    
    # AI: Analyze structure and identify page ranges
    structure_prompt = f"""Analyze this {total_pages}-page merged candidate document and identify which pages contain each section.

SAMPLE PAGES (showing snippets from beginning, middle, and end):
{sample_text}

TASK: Identify page ranges for each section type:
1. CIF (Candidate Information Form) - look for "Professional Information", "Present Employer"
2. Resume/CV - look for "Experience", "Skills", "Summary", formatted CV layout
3. Experience Letters - look for "EXPERIENCE CERTIFICATE", company letterheads, "worked as"

Return ONLY valid JSON:
{{
  "cif_pages": [1, 2, 3],
  "resume_pages": [4, 5, 6, 7, 8, 9, 10],
  "experience_letter_pages": [25, 26, 27]
}}

Rules:
- Return empty array [] if section not found
- Estimate page ranges based on patterns you see
- CIF is usually first 1-3 pages
- Resume is usually middle pages  
- Experience letters are usually last pages
- If uncertain, include the pages"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": structure_prompt}],
            temperature=0.05,
            max_tokens=500
        )
        
        response_text = response.choices[0].message.content.strip()
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            structure = json.loads(response_text[start:end])
        else:
            # Fallback: assume standard structure
            structure = {
                "cif_pages": list(range(1, min(4, total_pages+1))),
                "resume_pages": list(range(4, total_pages-2)) if total_pages > 6 else [],
                "experience_letter_pages": list(range(max(1, total_pages-2), total_pages+1))
            }
    except:
        # Fallback structure if AI fails
        structure = {
            "cif_pages": list(range(1, min(4, total_pages+1))),
            "resume_pages": list(range(4, total_pages-2)) if total_pages > 6 else [],
            "experience_letter_pages": list(range(max(1, total_pages-2), total_pages+1))
        }
    
    # ========== PASS 2: TARGETED DEEP EXTRACTION ==========
    
    # Extract personal info from first few pages
    personal_info = {}
    first_pages_text = '\n\n'.join([p['text'] for p in pages_data[:3]])
    
    try:
        personal_prompt = f"""Extract personal information:

{first_pages_text[:5000]}

Return ONLY valid JSON:
{{
  "full_name": "Extract candidate name",
  "cnic": "Extract CNIC (format: 00000-0000000-0)",
  "email": "Extract email",
  "contact": "Extract phone"
}}"""

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": personal_prompt}],
            temperature=0.05,
            max_tokens=500
        )
        
        response_text = response.choices[0].message.content.strip()
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            personal_info = json.loads(response_text[start:end])
    except:
        personal_info = {"full_name": "Unknown", "cnic": "", "email": "", "contact": ""}
    
    # Initialize results
    cif_experience = {"found": False, "details": ""}
    resume_experience = {"found": False, "details": ""}
    exp_letter_found = {"found": False, "details": ""}
    all_experiences = []
    
    # Extract CIF experience (FULL TEXT of identified CIF pages)
    if structure.get("cif_pages"):
        cif_page_nums = structure["cif_pages"]
        cif_pages_filtered = [p for p in pages_data if p['page_num'] in cif_page_nums]
        
        if cif_pages_filtered:
            cif_full_text = '\n\n'.join([f"PAGE {p['page_num']}:\n{p['text']}" for p in cif_pages_filtered])
            
            cif_prompt = f"""Extract work experience from CIF Professional Information section:

{cif_full_text}

Return ONLY valid JSON:
{{
  "found": true/false,
  "details": "Brief summary if found",
  "experiences": [
    {{
      "employer": "Company name",
      "designation": "Job title",
      "date_joining": "DD/MM/YYYY",
      "date_leaving": "DD/MM/YYYY or Present",
      "duration_months": "Number",
      "monthly_salary": "Amount if mentioned",
      "responsibilities": "Brief summary"
    }}
  ]
}}

found = true ONLY if actual work experience exists (not empty fields)."""

            try:
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role": "user", "content": cif_prompt}],
                    temperature=0.05,
                    max_tokens=3000
                )
                
                response_text = response.choices[0].message.content.strip()
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end > start:
                    cif_data = json.loads(response_text[start:end])
                    cif_experience = {"found": cif_data.get("found", False), "details": cif_data.get("details", "")}
                    
                    for exp in cif_data.get("experiences", []):
                        exp['source'] = 'CIF'
                        all_experiences.append(exp)
            except:
                pass
    
    # Extract Resume experience (FULL TEXT of identified Resume pages)
    if structure.get("resume_pages"):
        resume_page_nums = structure["resume_pages"]
        resume_pages_filtered = [p for p in pages_data if p['page_num'] in resume_page_nums]
        
        if resume_pages_filtered:
            resume_full_text = '\n\n'.join([f"PAGE {p['page_num']}:\n{p['text']}" for p in resume_pages_filtered])
            
            resume_prompt = f"""Extract ALL work experience from this Resume/CV:

{resume_full_text}

Return ONLY valid JSON:
{{
  "found": true/false,
  "details": "Brief summary if found",
  "experiences": [
    {{
      "employer": "Company name",
      "designation": "Job title",
      "date_joining": "DD/MM/YYYY",
      "date_leaving": "DD/MM/YYYY or Present",
      "duration_months": "Number",
      "monthly_salary": "Amount if mentioned",
      "responsibilities": "Brief summary"
    }}
  ]
}}

found = true if work experience exists in resume."""

            try:
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role": "user", "content": resume_prompt}],
                    temperature=0.05,
                    max_tokens=4000
                )
                
                response_text = response.choices[0].message.content.strip()
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end > start:
                    resume_data = json.loads(response_text[start:end])
                    resume_experience = {"found": resume_data.get("found", False), "details": resume_data.get("details", "")}
                    
                    for exp in resume_data.get("experiences", []):
                        exp['source'] = 'Resume'
                        all_experiences.append(exp)
            except:
                pass
    
    # Extract Experience Letters (FULL TEXT of identified Letter pages)
    if structure.get("experience_letter_pages"):
        letter_page_nums = structure["experience_letter_pages"]
        letter_pages_filtered = [p for p in pages_data if p['page_num'] in letter_page_nums]
        
        if letter_pages_filtered:
            letter_full_text = '\n\n'.join([f"PAGE {p['page_num']}:\n{p['text']}" for p in letter_pages_filtered])
            
            letter_prompt = f"""Extract work experience from these Experience Certificates/Letters:

{letter_full_text}

Return ONLY valid JSON:
{{
  "found": true/false,
  "details": "List company names issuing letters",
  "experiences": [
    {{
      "employer": "Company name from letterhead",
      "designation": "Job title",
      "date_joining": "DD/MM/YYYY",
      "date_leaving": "DD/MM/YYYY",
      "duration_months": "Number",
      "monthly_salary": "Amount if mentioned",
      "responsibilities": "Brief from letter"
    }}
  ]
}}

found = true if experience certificate/letter exists."""

            try:
                response = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role": "user", "content": letter_prompt}],
                    temperature=0.05,
                    max_tokens=4000
                )
                
                response_text = response.choices[0].message.content.strip()
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end > start:
                    letter_data = json.loads(response_text[start:end])
                    exp_letter_found = {"found": letter_data.get("found", False), "details": letter_data.get("details", "")}
                    
                    for exp in letter_data.get("experiences", []):
                        exp['source'] = 'Experience Letter'
                        all_experiences.append(exp)
            except:
                pass
    
    # Return merged results
    return {
        "personal_info": personal_info,
        "experience_in_cif": cif_experience,
        "experience_in_resume": resume_experience,
        "experience_letter_found": exp_letter_found,
        "all_experiences": all_experiences,
        "ocr_used_pages": ocr_used_pages,
        "structure": structure
    }


def cv_experience_parser_page():
    """CV/Experience Parser Page - Extract EXPERIENCE data from merged candidate documents."""
    st.markdown('<div class="main-header">👔 Experience Parser</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Extract experience from CIF, Resume/CV & Experience Letters</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.info("📋 Upload merged candidate documents (multi-page PDFs). Extracts experience from: **Candidate Information Form**, **Resume/CV**, and **Experience Letters**")
    
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
        has_valid_keys = any(k for k in api_keys)
        
        process_cv_button = st.button(
            "🚀 Process CVs",
            type="primary",
            use_container_width=True,
            disabled=not (uploaded_cv_files and has_valid_keys),
            key="process_cv_button"
        )
    
    # Initialize session state for CV results
    if "cv_results" not in st.session_state:
        st.session_state.cv_results = []
    
    # Processing logic
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
                
                # Show processing steps
                with st.expander(f"🔍 Processing Details: {file.name}", expanded=False):
                    step_info = st.empty()
                    step_info.info("📑 Step 1/4: Classifying pages by type...")
                
                try:
                    # Process CV using fallback keys
                    cv_data = create_groq_client_with_fallback(api_keys, process_cv_multipage, file)
                    cv_data['source_file'] = file.name
                    results.append(cv_data)
                    
                    # Show classification results
                    with st.expander(f"🔍 Processing Details: {file.name}", expanded=False):
                        step_info.success("✅ Processing complete!")
                    
                    # Add delay between requests
                    if idx < len(uploaded_cv_files) - 1:
                        time.sleep(2.0)
                    
                except Exception as e:
                    st.error(f"❌ Error processing {file.name}: {str(e)}")
                
                # Update progress
                progress_bar.progress((idx + 1) / len(uploaded_cv_files))
            
            status_text.text("✅ Processing complete!")
            
            # Append to existing results
            st.session_state.cv_results.extend(results)
            st.success(f"✅ Successfully processed {len(results)} CV(s)! Total: {len(st.session_state.cv_results)}")
    
    # Display results
    if st.session_state.cv_results:
        st.markdown("---")
        
        # Clear button
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"📌 **{len(st.session_state.cv_results)} candidate(s) processed**")
        with col2:
            if st.button("🗑️ Clear All", use_container_width=True, type="secondary", key="clear_cv_button"):
                st.session_state.cv_results = []
                st.rerun()
        
        # EXPERIENCE SUMMARY TABLE
        st.markdown("### 📊 Experience Summary")
        summary_data = []
        for cv in st.session_state.cv_results:
            personal = cv.get('personal_info', {})
            exp_cif = cv.get('experience_in_cif', {})
            exp_resume = cv.get('experience_in_resume', {})
            exp_letter = cv.get('experience_letter_found', {})
            
            summary_data.append({
                'Name': personal.get('full_name', 'Unknown'),
                'CNIC': personal.get('cnic', ''),
                'Contact': personal.get('contact', ''),
                'Email': personal.get('email', ''),
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
        for cv in st.session_state.cv_results:
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
                summary_excel = convert_df_to_excel(df_summary)
                st.download_button(
                    label="📥 Experience Summary",
                    data=summary_excel,
                    file_name="experience_summary.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        
        with col2:
            if detailed_exp:
                detailed_excel = convert_df_to_excel(df_detailed)
                st.download_button(
                    label="📥 Detailed Experience",
                    data=detailed_excel,
                    file_name="detailed_experience.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )


def main():
    """Main application function."""
    # Page configuration
    st.set_page_config(
        page_title="EduParser",
        page_icon="🎓",
        layout="wide"
    )
    
    # Custom CSS for better styling
    st.markdown('''
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
    ''', unsafe_allow_html=True)
    
    # Sidebar configuration
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/graduation-cap.png", width=80)
        st.title("⚙️ Navigation")
        st.markdown("---")
        
        # Navigation
        page = st.radio(
            "Select Page",
            ["📄 Document Parser", "📊 Spreadsheet Loader", "👔 CV/Experience Parser", "⚙️ Settings"],
            label_visibility="collapsed"
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
        st.markdown("### 📋 Quick Guide")
        st.markdown("""
        1. Configure API keys in Settings
        2. Upload documents or spreadsheets
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
        - Bachelor Degrees
        - Master Degrees
        - Diplomas (DAE)
        """)
    
    # Check if CV/Experience Parser page
    if page == "👔 CV/Experience Parser":
        cv_experience_parser_page()
        return  # Exit early
    
    # Check if Settings page
    if page == "⚙️ Settings":
        # Settings Page
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
        
        return  # Exit early, don't show main content
    
    # Main area - Document Parser
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
    
    # Initialize session state for results - Simple session state only
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


def ai_match_names(client, edu_names: list, emp_names: list) -> dict:
    """Use AI to match names with variations/typos."""
    prompt = f"""You are a name matching expert. Match names from List A (education records) to List B (employee records).
Names may have slight spelling variations, typos, or different transliterations (e.g., "Wajahat" vs "Wajahet", "Muhammad" vs "Mohammad").

List A (Education Names):
{json.dumps(edu_names, indent=2)}

List B (Employee Names):
{json.dumps(emp_names, indent=2)}

Return a JSON object mapping each name from List A to its best match in List B.
If no good match exists, map to null.
Only match names that are clearly the same person (similar spelling/sound).

Return ONLY valid JSON in this format:
{{
  "matches": {{
    "Education Name 1": "Employee Name Match or null",
    "Education Name 2": "Employee Name Match or null"
  }}
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=4000
        )
        
        response_text = response.choices[0].message.content
        
        # Clean markdown formatting if present
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]
        
        result = json.loads(response_text.strip())
        return result.get("matches", {})
    except Exception as e:
        st.warning(f"AI matching failed: {e}. Falling back to exact matching.")
        return {}


def normalize_name(name):
    """
    Normalize a name for robust matching.
    Handles multiple spaces, trailing dots, case differences.
    """
    if pd.isna(name):
        return ""
    
    # Convert to string and lowercase
    name = str(name).lower().strip()
    
    # Remove trailing dots and commas
    name = name.rstrip('.,')
    
    # Replace multiple spaces with single space
    import re
    name = re.sub(r'\s+', ' ', name)
    
    # Remove extra punctuation but keep hyphens in names
    name = re.sub(r'[^a-z0-9\s\-]', '', name)
    
    return name.strip()


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
                
                fuzzy_matched_count = 0
                for idx in merged_df[unmatched_mask].index:
                    edu_name_norm = merged_df.loc[idx, 'name_normalized']
                    edu_words = set(edu_name_norm.split())
                    
                    # Find best match based on word overlap
                    best_match = None
                    best_score = 0
                    
                    for _, emp_row in emp_df_unique.iterrows():
                        emp_name_norm = emp_row['name_normalized']
                        emp_words = set(emp_name_norm.split())
                        
                        if len(edu_words) >= 2 and len(emp_words) >= 2:
                            # Calculate word overlap score
                            common_words = edu_words.intersection(emp_words)
                            
                            # At least 2 words must match
                            if len(common_words) >= 2:
                                # Score based on proportion of education name matched
                                score = len(common_words) / len(edu_words)
                                
                                # Boost score if all education words are matched
                                if len(common_words) == len(edu_words):
                                    score += 0.5
                                
                                if score > best_score:
                                    best_score = score
                                    best_match = emp_row
                    
                    # Apply match if score is high enough (>= 80%)
                    if best_match is not None and best_score >= 0.8:
                        merged_df.loc[idx, 'CNIC'] = best_match['CNIC']
                        merged_df.loc[idx, 'EMPLOYEE_NUMBER'] = best_match['EMPLOYEE_NUMBER']
                        merged_df.loc[idx, 'FULL_NAME'] = best_match['FULL_NAME']
                        fuzzy_matched_count += 1
                
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


if __name__ == "__main__":
    main()
    
    # Add Spreadsheet Loader section
    st.markdown("---")
    st.markdown("---")
    spreadsheet_loader()
