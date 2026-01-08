"""
School Name Standardizer
Standardizes school names to match case-sensitive reference names from a master list
Uses fuzzy matching to handle variations in spacing, punctuation, and abbreviations
"""

import pandas as pd
import re
from difflib import SequenceMatcher


def normalize_for_comparison(name):
    """
    Aggressively normalize school name for fuzzy comparison.
    Removes ALL punctuation, spaces, and converts to lowercase.
    
    Args:
        name: School name string
        
    Returns:
        Normalized school name for comparison
    """
    if pd.isna(name):
        return ""
    
    # Convert to string and lowercase
    name = str(name).lower().strip()
    
    # Remove all punctuation and spaces for comparison
    name = re.sub(r'[^a-z0-9]', '', name)
    
    return name


def normalize_school_name(name):
    """
    Normalize school name for matching (case-insensitive, trimmed).
    Removes extra spaces and some punctuation for comparison.
    
    Args:
        name: School name string
        
    Returns:
        Normalized school name for matching
    """
    if pd.isna(name):
        return ""
    
    # Convert to string and strip
    name = str(name).strip()
    
    # Replace multiple spaces with single space
    name = re.sub(r'\s+', ' ', name)
    
    # Convert to lowercase for matching
    name = name.lower()
    
    return name


def extract_keywords(name):
    """
    Extract meaningful keywords from a school name.
    Removes common words and keeps distinctive terms.
    """
    if not name:
        return set()
    
    # Common words to ignore for keyword matching
    stop_words = {
        'of', 'the', 'and', 'for', 'in', 'at', '&', 'a', 'an'
    }
    
    # Extract words
    name_lower = name.lower()
    # Remove punctuation and split
    words = re.sub(r'[^a-z0-9\s]', ' ', name_lower).split()
    
    # Keep meaningful words (but NOT location names alone as they're not distinctive)
    keywords = {w for w in words if w not in stop_words and len(w) >= 2}
    
    return keywords


# Known abbreviation mappings for Pakistani education boards/institutions
ABBREVIATION_MAP = {
    'fbise': ['federal board', 'federal', 'fbise'],
    'bise': ['bise', 'board of intermediate'],
    'aiou': ['allama iqbal open university', 'aiou', 'a.i.o.u'],
    'szabist': ['szabist', 'shaheed zulfikar ali bhutto'],
    'pbte': ['punjab board of technical education', 'pbte'],
    'iqra': ['iqra', 'aqra'],  # Common misspelling
}


def get_abbreviation_matches(name):
    """
    Get potential abbreviation matches for a school name.
    """
    name_lower = name.lower()
    matches = set()
    
    for abbrev, patterns in ABBREVIATION_MAP.items():
        for pattern in patterns:
            if pattern in name_lower:
                matches.add(abbrev)
                break
    
    return matches


def calculate_similarity(str1, str2):
    """
    Calculate similarity ratio between two strings.
    Uses multiple methods and returns the highest score.
    """
    if not str1 or not str2:
        return 0
    
    # Skip invalid reference entries (like "---")
    if str2 in ['---', '--', '-', '']:
        return 0
    
    # Check for abbreviation matches first (highest priority)
    abbrev1 = get_abbreviation_matches(str1)
    abbrev2 = get_abbreviation_matches(str2)
    
    if abbrev1 and abbrev2:
        if abbrev1 & abbrev2:  # Common abbreviation match
            # Both refer to the same institution type
            # Now check if location also matches
            norm1 = normalize_for_comparison(str1)
            norm2 = normalize_for_comparison(str2)
            
            # Check for location matches (city names)
            locations = ['islamabad', 'lahore', 'karachi', 'multan', 'faisalabad', 
                        'gujranwala', 'sargodha', 'hyderabad', 'quetta', 'peshawar',
                        'rawalpindi', 'sukkur', 'mirpurkhas', 'jamshoro', 'balochistan',
                        'sindh', 'punjab']
            
            loc1 = set(loc for loc in locations if loc in str1.lower())
            loc2 = set(loc for loc in locations if loc in str2.lower())
            
            if loc1 and loc2 and loc1 == loc2:
                return 1.0  # Same institution type + same location = perfect match
            elif not loc1 or not loc2:
                return 0.95  # Same institution type, location not specified
            else:
                return 0.5  # Same institution type but different location
        elif abbrev1 and abbrev2:
            # Different abbreviations - penalize heavily
            return 0.3
    
    # Method 1: Direct sequence matching on lowercased strings
    ratio1 = SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    # Method 2: Aggressive normalization matching (removes all punctuation/spaces)
    norm1 = normalize_for_comparison(str1)
    norm2 = normalize_for_comparison(str2)
    
    if not norm1 or not norm2:
        return ratio1
    
    ratio2 = SequenceMatcher(None, norm1, norm2).ratio()
    
    # Method 3: Check if normalized strings match exactly
    if norm1 == norm2:
        return 1.0
    
    # Method 4: Check if one normalized string contains the other
    # Only valid if the contained string is substantial (>= 60% length of container)
    if len(norm1) >= 4 and len(norm2) >= 4:
        if norm1 in norm2:
            containment_ratio = len(norm1) / len(norm2)
            if containment_ratio >= 0.6:
                ratio3 = 0.85 + (containment_ratio * 0.15)
            else:
                ratio3 = 0
        elif norm2 in norm1:
            containment_ratio = len(norm2) / len(norm1)
            if containment_ratio >= 0.6:
                ratio3 = 0.85 + (containment_ratio * 0.15)
            else:
                ratio3 = 0
        else:
            ratio3 = 0
    else:
        ratio3 = 0
    
    # Method 5: Word-based matching (excluding very common words)
    words1 = set(re.sub(r'[^a-z0-9\s]', ' ', str1.lower()).split())
    words2 = set(re.sub(r'[^a-z0-9\s]', ' ', str2.lower()).split())
    
    # Remove common words for better matching
    common_stops = {'of', 'the', 'and', 'for', 'in', 'at', 'a', 'an'}
    words1 = words1 - common_stops
    words2 = words2 - common_stops
    
    if words1 and words2:
        common = words1 & words2
        if common:
            # Check if at least 2 meaningful words match, or all words match
            if len(common) >= 2 or (len(common) == len(words1) or len(common) == len(words2)):
                word_score = len(common) / max(len(words1), len(words2))
                ratio4 = 0.7 + (word_score * 0.3)
            else:
                ratio4 = 0
        else:
            ratio4 = 0
    else:
        ratio4 = 0
    
    return max(ratio1, ratio2, ratio3, ratio4)


def find_best_match(school_name, reference_schools, threshold=0.75):
    """
    Find the best matching school name from the reference list using fuzzy matching.
    
    Args:
        school_name: The school name to match
        reference_schools: List of reference school names
        threshold: Minimum similarity score to consider a match (0-1)
        
    Returns:
        Tuple of (best_match, similarity_score) or (None, 0) if no match found
    """
    if pd.isna(school_name) or not school_name:
        return None, 0
    
    school_name = str(school_name).strip()
    school_normalized = normalize_for_comparison(school_name)
    school_lower = normalize_school_name(school_name)
    
    # Skip empty or too short names
    if len(school_normalized) < 3:
        return None, 0
    
    best_match = None
    best_score = 0
    best_match_length = float('inf')
    
    for ref_school in reference_schools:
        # Skip invalid entries
        if not ref_school or ref_school in ['---', '--', '-']:
            continue
            
        ref_normalized = normalize_for_comparison(ref_school)
        ref_lower = normalize_school_name(ref_school)
        
        # Skip empty normalized names
        if len(ref_normalized) < 3:
            continue
        
        # Check for exact match (case-insensitive, punctuation-insensitive)
        if school_normalized == ref_normalized:
            return ref_school, 1.0
        
        # Check for exact match with normal normalization
        if school_lower == ref_lower:
            return ref_school, 1.0
        
        # Calculate fuzzy similarity
        score = calculate_similarity(school_name, ref_school)
        
        # Prefer shorter matches when scores are similar (within 0.05)
        # This helps pick "IQRA UNIVERSITY" over "Asian Management Institute, Iqra University"
        if score > best_score or (score >= best_score - 0.05 and len(ref_school) < best_match_length):
            if score > best_score or (score >= threshold and len(ref_school) < best_match_length * 0.7):
                best_score = score
                best_match = ref_school
                best_match_length = len(ref_school)
    
    if best_score >= threshold:
        return best_match, best_score
    
    return None, 0


def load_reference_school_names(file):
    """
    Load reference school names from Excel file.
    
    Args:
        file: File-like object (uploaded file from Streamlit)
        
    Returns:
        List of all reference school names (preserving original case)
    """
    try:
        # Read the Excel file
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Assuming the school names are in the first column or a column named 'School' or 'School Name'
        if 'School' in df.columns:
            school_column = 'School'
        elif 'School Name' in df.columns:
            school_column = 'School Name'
        elif 'INSTITUTE_NAME' in df.columns:
            school_column = 'INSTITUTE_NAME'
        else:
            # Use the first column
            school_column = df.columns[0]
        
        # Return list of all school names (preserving case)
        school_list = [str(name).strip() for name in df[school_column].dropna().unique() if str(name).strip()]
        
        return school_list
    
    except Exception as e:
        raise Exception(f"Error loading reference school names: {str(e)}")


def standardize_school_names(df, reference_schools, threshold=0.75):
    """
    Standardize school names in a DataFrame using fuzzy matching against reference list.
    
    Args:
        df: DataFrame containing a 'School' column
        reference_schools: List of reference school names
        threshold: Minimum similarity score to accept a match (0-1)
        
    Returns:
        DataFrame with standardized school names and statistics
    """
    if 'School' not in df.columns:
        raise ValueError("DataFrame must contain a 'School' column")
    
    # Track statistics
    total_schools = df['School'].notna().sum()
    updated_count = 0
    not_found = []
    match_details = []  # Track what was matched to what
    
    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()
    
    # Get unique schools to process (for efficiency)
    unique_schools = df['School'].dropna().unique()
    
    # Build a cache of matches for each unique school
    match_cache = {}
    for school_name in unique_schools:
        school_str = str(school_name).strip()
        if school_str not in match_cache:
            best_match, score = find_best_match(school_str, reference_schools, threshold)
            match_cache[school_str] = (best_match, score)
            
            if best_match and school_str != best_match:
                match_details.append({
                    'original': school_str,
                    'matched_to': best_match,
                    'score': score
                })
    
    # Apply matches to dataframe
    for idx, school_name in df['School'].items():
        if pd.isna(school_name):
            continue
        
        school_str = str(school_name).strip()
        best_match, score = match_cache.get(school_str, (None, 0))
        
        if best_match:
            if school_str != best_match:
                df.loc[idx, 'School'] = best_match
                updated_count += 1
        else:
            # Keep track of schools not found in reference
            if school_str and school_str not in not_found:
                not_found.append(school_str)
    
    stats = {
        'total_schools': total_schools,
        'updated_count': updated_count,
        'not_found_count': len(not_found),
        'not_found_list': not_found,
        'match_details': match_details
    }
    
    return df, stats
