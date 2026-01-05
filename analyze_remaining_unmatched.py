"""Analyze the remaining 14 unmatched names"""
import pandas as pd
import re

def normalize_name(name):
    if pd.isna(name):
        return ""
    name = str(name).lower().strip()
    name = name.rstrip('.,')
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[^a-z0-9\s\-]', '', name)
    return name.strip()

emp = pd.read_excel('MjbyEl.xlsx')
edu = pd.read_excel('ZRTeII.xlsx')

emp['name_normalized'] = emp['FULL_NAME'].apply(normalize_name)
edu['name_normalized'] = edu['Name'].apply(normalize_name)

unmatched = edu[~edu['name_normalized'].isin(emp['name_normalized'].values)]

print("="*70)
print("ANALYZING REMAINING 14 UNMATCHED RECORDS")
print("="*70)

print(f"\nTotal unmatched: {len(unmatched)}")
print("\nUnmatched education names:")
for idx, name in enumerate(unmatched['Name'].unique(), 1):
    normalized = normalize_name(name)
    count = (unmatched['Name'] == name).sum()
    print(f"{idx}. '{name}' (normalized: '{normalized}') - {count} record(s)")

print("\n" + "="*70)
print("CHECKING FOR SIMILAR EMPLOYEE NAMES")
print("="*70)

for edu_name in unmatched['Name'].unique():
    edu_norm = normalize_name(edu_name)
    edu_words = set(edu_norm.split())
    
    best_matches = []
    for emp_name in emp['FULL_NAME'].values:
        emp_norm = normalize_name(emp_name)
        emp_words = set(emp_norm.split())
        
        if len(edu_words) > 0:
            common = edu_words.intersection(emp_words)
            if len(common) >= 2:  # At least 2 words in common
                similarity = len(common) / len(edu_words)
                best_matches.append((emp_name, emp_norm, similarity, common))
    
    if best_matches:
        best_matches.sort(key=lambda x: x[2], reverse=True)
        print(f"\nEducation: '{edu_name}'")
        print(f"  Normalized: '{edu_norm}'")
        print(f"  Possible matches:")
        for emp_orig, emp_norm, sim, common in best_matches[:3]:
            print(f"    - '{emp_orig}' (similarity: {sim:.1%}, common: {common})")
    else:
        print(f"\nEducation: '{edu_name}' → NO similar employee names found")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)
print("""
These 14 unmatched records are likely:
1. Typos in names (e.g., WAHJ vs WAHAJ)
2. Names not in the employee list
3. Duplicate education records for same person

RECOMMENDATION:
Use AI matching for these remaining 14 names to catch typos and variations.
The improved normalization already handled the whitespace/punctuation issues.
""")
