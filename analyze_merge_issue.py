import pandas as pd

print("="*70)
print("ANALYZING MERGE MISMATCH ISSUE")
print("="*70)

# Load both files - corrected assignment
emp = pd.read_excel('MjbyEl.xlsx')  # Employee file
edu = pd.read_excel('ZRTeII.xlsx')  # Education file

print("\n1. EMPLOYEE FILE (MjbyEl.xlsx)")
print(f"   Rows: {len(emp)}")
print(f"   Columns: {list(emp.columns)}")
print("\n   First 10 employee names:")
if 'FULL_NAME' in emp.columns:
    for i, name in enumerate(emp['FULL_NAME'].head(10)):
        print(f"   {i+1}. {name}")
else:
    print("   ERROR: FULL_NAME column not found!")

print("\n2. EDUCATION FILE (ZRTeII.xlsx)")
print(f"   Rows: {len(edu)}")
print(f"   Columns: {list(edu.columns)}")
print("\n   First 10 education names:")
if 'Name' in edu.columns:
    for i, name in enumerate(edu['Name'].head(10)):
        print(f"   {i+1}. {name}")
else:
    print("   ERROR: Name column not found!")

print("\n" + "="*70)
print("NAME COMPARISON ANALYSIS")
print("="*70)

# Normalize and compare names
emp_names_orig = emp['FULL_NAME'].str.strip() if 'FULL_NAME' in emp.columns else []
edu_names_orig = edu['Name'].str.strip() if 'Name' in edu.columns else []

emp_names_norm = emp['FULL_NAME'].str.lower().str.strip() if 'FULL_NAME' in emp.columns else []
edu_names_norm = edu['Name'].str.lower().str.strip() if 'Name' in edu.columns else []

# Create mapping dataframes
emp_df = pd.DataFrame({'original': emp_names_orig, 'normalized': emp_names_norm})
edu_df = pd.DataFrame({'original': edu_names_orig, 'normalized': edu_names_norm})

# Find matches
exact_matches = edu_df[edu_df['normalized'].isin(emp_df['normalized'].values)]
unmatched = edu_df[~edu_df['normalized'].isin(emp_df['normalized'].values)]

print(f"\nTotal employee records: {len(emp)}")
print(f"Total education records: {len(edu)}")
print(f"\n✅ Exact matches (case-insensitive): {len(exact_matches)}")
print(f"❌ Unmatched education records: {len(unmatched)}")

if len(unmatched) > 0:
    print(f"\n" + "="*70)
    print("UNMATCHED NAMES (Education names not in Employee list):")
    print("="*70)
    for idx, row in unmatched.head(20).iterrows():
        print(f"  {idx+1}. {row['original']}")
        
    print(f"\n" + "="*70)
    print("ANALYZING NAME PATTERNS IN UNMATCHED RECORDS")
    print("="*70)
    
    # Check for common issues
    print("\nChecking for name format differences...")
    for idx, edu_name in unmatched.head(10).iterrows():
        edu_orig = edu_name['original']
        edu_norm = edu_name['normalized']
        
        # Find similar names in employee list
        possible_matches = []
        for emp_name in emp_df['normalized'].values:
            # Check if substantial overlap
            edu_words = set(edu_norm.split())
            emp_words = set(emp_name.split())
            
            if len(edu_words) > 0:
                overlap = len(edu_words.intersection(emp_words))
                similarity = overlap / len(edu_words)
                
                if similarity > 0.5 and overlap >= 2:  # At least 50% overlap and 2 words match
                    emp_orig = emp_df[emp_df['normalized'] == emp_name]['original'].iloc[0]
                    possible_matches.append((emp_orig, similarity))
        
        if possible_matches:
            possible_matches.sort(key=lambda x: x[1], reverse=True)
            print(f"\n  Education: {edu_orig}")
            print(f"  Possible employee matches:")
            for match, sim in possible_matches[:3]:
                print(f"    - {match} (similarity: {sim:.1%})")
