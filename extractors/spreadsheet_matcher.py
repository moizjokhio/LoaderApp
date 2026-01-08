"""
Spreadsheet Matcher
AI-powered and fuzzy name matching for merging employee and education data
"""

import json
import re
import pandas as pd


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
        # Return empty dict on failure - caller will handle fallback
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
    name = re.sub(r'\s+', ' ', name)
    
    # Remove extra punctuation but keep hyphens in names
    name = re.sub(r'[^a-z0-9\s\-]', '', name)
    
    return name.strip()


def fuzzy_match_names(merged_df, emp_df_unique, unmatched_mask):
    """
    Perform fuzzy matching using word overlap method.
    
    Args:
        merged_df: DataFrame with education and employee data
        emp_df_unique: Unique employee records
        unmatched_mask: Boolean mask for unmatched records
        
    Returns:
        tuple: (merged_df, fuzzy_matched_count)
    """
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
    
    return merged_df, fuzzy_matched_count
