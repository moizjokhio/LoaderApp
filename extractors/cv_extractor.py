"""
CV/Experience Extractor with Two-Pass Hybrid + OCR Approach
"""
import json
from config import GROQ_MODEL, DEFAULT_TEMPERATURE
from utils.pdf_processor import extract_all_pages


def discover_document_structure(client, pages_data: list, total_pages: int) -> dict:
    """
    PASS 1: Analyze document structure and identify page ranges for each section.
    
    Args:
        client: Groq client instance
        pages_data: List of page dictionaries with 'page_num' and 'text'
        total_pages: Total number of pages
    
    Returns:
        dict: Page ranges for CIF, Resume, and Experience Letters
    """
    # Create a sample of pages (first 3, middle 2, last 3)
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
    
    # AI: Analyze structure
    structure_prompt = f"""Analyze this {total_pages}-page merged candidate document and identify which pages contain each section.

SAMPLE PAGES:
{sample_text}

TASK: Identify page ranges for each section:
1. CIF (Candidate Information Form) - "Professional Information", "Present Employer"
2. Resume/CV - "Experience", "Skills", "Summary"
3. Experience Letters - "EXPERIENCE CERTIFICATE", company letterheads

Return ONLY valid JSON:
{{
  "cif_pages": [1, 2, 3],
  "resume_pages": [4, 5, 6, 7],
  "experience_letter_pages": [25, 26, 27]
}}

Rules:
- Return empty array [] if section not found
- CIF usually first 1-3 pages
- Resume usually middle pages
- Experience letters usually last pages"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": structure_prompt}],
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=500
        )
        
        response_text = response.choices[0].message.content.strip()
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(response_text[start:end])
    except:
        pass
    
    # Fallback structure
    return {
        "cif_pages": list(range(1, min(4, total_pages+1))),
        "resume_pages": list(range(4, total_pages-2)) if total_pages > 6 else [],
        "experience_letter_pages": list(range(max(1, total_pages-2), total_pages+1))
    }


def extract_personal_info(client, pages_data: list) -> dict:
    """Extract personal information from first few pages."""
    first_pages_text = '\n\n'.join([p['text'] for p in pages_data[:3]])
    
    personal_prompt = f"""Extract personal information:

{first_pages_text[:5000]}

Return ONLY valid JSON:
{{
  "full_name": "Extract candidate name",
  "cnic": "Extract CNIC (format: 00000-0000000-0)",
  "email": "Extract email",
  "contact": "Extract phone"
}}"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": personal_prompt}],
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=500
        )
        
        response_text = response.choices[0].message.content.strip()
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(response_text[start:end])
    except:
        pass
    
    return {"full_name": "Unknown", "cnic": "", "email": "", "contact": ""}


def extract_section_experience(client, pages_data: list, page_nums: list, section_type: str) -> tuple:
    """
    PASS 2: Extract experience from a specific section (CIF, Resume, or Experience Letter).
    
    Args:
        client: Groq client instance
        pages_data: All pages data
        page_nums: Page numbers to extract from
        section_type: "CIF", "Resume", or "Experience Letter"
    
    Returns:
        tuple: (found_dict, experiences_list)
    """
    if not page_nums:
        return {"found": False, "details": ""}, []
    
    # Filter pages
    filtered_pages = [p for p in pages_data if p['page_num'] in page_nums]
    if not filtered_pages:
        return {"found": False, "details": ""}, []
    
    # Build full text
    full_text = '\n\n'.join([f"PAGE {p['page_num']}:\n{p['text']}" for p in filtered_pages])
    
    # Section-specific prompts
    if section_type == "CIF":
        prompt = f"""Extract work experience from CIF Professional Information:

{full_text}

Return ONLY valid JSON:
{{
  "found": true/false,
  "details": "Brief summary",
  "experiences": [
    {{
      "employer": "Company",
      "designation": "Title",
      "date_joining": "DD/MM/YYYY",
      "date_leaving": "DD/MM/YYYY or Present",
      "duration_months": "Number",
      "monthly_salary": "Amount",
      "responsibilities": "Summary"
    }}
  ]
}}

found = true ONLY if actual work experience exists"""
        max_tokens = 3000
        
    elif section_type == "Resume":
        prompt = f"""Extract ALL work experience from Resume/CV:

{full_text}

Return ONLY valid JSON:
{{
  "found": true/false,
  "details": "Brief summary",
  "experiences": [
    {{
      "employer": "Company",
      "designation": "Title",
      "date_joining": "DD/MM/YYYY",
      "date_leaving": "DD/MM/YYYY or Present",
      "duration_months": "Number",
      "monthly_salary": "Amount",
      "responsibilities": "Summary"
    }}
  ]
}}"""
        max_tokens = 4000
        
    else:  # Experience Letter
        prompt = f"""Extract work experience from Experience Certificates/Letters:

{full_text}

Return ONLY valid JSON:
{{
  "found": true/false,
  "details": "Company names",
  "experiences": [
    {{
      "employer": "Company from letterhead",
      "designation": "Title",
      "date_joining": "DD/MM/YYYY",
      "date_leaving": "DD/MM/YYYY",
      "duration_months": "Number",
      "monthly_salary": "Amount",
      "responsibilities": "Brief"
    }}
  ]
}}"""
        max_tokens = 4000
    
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=max_tokens
        )
        
        response_text = response.choices[0].message.content.strip()
        start = response_text.find('{')
        end = response_text.rfind('}') + 1
        if start != -1 and end > start:
            data = json.loads(response_text[start:end])
            found_info = {"found": data.get("found", False), "details": data.get("details", "")}
            experiences = data.get("experiences", [])
            
            # Add source to each experience
            for exp in experiences:
                exp['source'] = section_type
            
            return found_info, experiences
    except:
        pass
    
    return {"found": False, "details": ""}, []


def process_cv_multipage(client, pdf_file) -> dict:
    """
    TWO-PASS HYBRID + OCR APPROACH for CV/Experience extraction.
    
    Pass 1: Document Structure Discovery (AI analyzes sample pages)
    Pass 2: Targeted Deep Extraction (3 focused AI calls)
    OCR: Automatic fallback for scanned/image pages
    
    Args:
        client: Groq client instance
        pdf_file: Uploaded PDF file
    
    Returns:
        dict: Extracted personal info, experience data, metadata
    """
    # Extract all pages with OCR
    pages_data, ocr_used_pages = extract_all_pages(pdf_file)
    total_pages = len(pages_data)
    
    # PASS 1: Discover document structure
    structure = discover_document_structure(client, pages_data, total_pages)
    
    # Extract personal info
    personal_info = extract_personal_info(client, pages_data)
    
    # PASS 2: Extract experience from each section
    all_experiences = []
    
    # CIF Experience
    cif_experience, cif_exp_list = extract_section_experience(
        client, pages_data, structure.get("cif_pages", []), "CIF"
    )
    all_experiences.extend(cif_exp_list)
    
    # Resume Experience
    resume_experience, resume_exp_list = extract_section_experience(
        client, pages_data, structure.get("resume_pages", []), "Resume"
    )
    all_experiences.extend(resume_exp_list)
    
    # Experience Letters
    exp_letter_found, letter_exp_list = extract_section_experience(
        client, pages_data, structure.get("experience_letter_pages", []), "Experience Letter"
    )
    all_experiences.extend(letter_exp_list)
    
    # Return complete results
    return {
        "personal_info": personal_info,
        "experience_in_cif": cif_experience,
        "experience_in_resume": resume_experience,
        "experience_letter_found": exp_letter_found,
        "all_experiences": all_experiences,
        "ocr_used_pages": ocr_used_pages,
        "structure": structure
    }
