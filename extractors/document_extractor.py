"""
Educational Document Extractor
Processes Pakistani educational documents (Degrees, Transcripts, Marksheets)
using Groq Vision API with business logic for date calculation and standardization.
"""

import base64
import json
import time
from io import BytesIO
from PIL import Image
import fitz  # PyMuPDF

# System prompt with all business logic rules for educational documents
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
