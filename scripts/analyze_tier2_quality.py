import pandas as pd
import os

def analyze_v10():
    file_path = 'fast_gateway_results_v10.xlsx'
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return

    df = pd.read_excel(file_path)
    
    print("=== TIER 2 ANALYSIS SUMMARY ===")
    total_rows = len(df)
    tier2_rows = df[df['Tier 2 Verdict'].isin(['PASS', 'FAIL'])]
    print(f"Total rows in report: {total_rows}")
    print(f"Rows with Tier 2 Verdicts: {len(tier2_rows)}")
    
    print("\n--- Verdict Distribution ---")
    print(df['Tier 2 Verdict'].value_counts())
    
    print("\n--- Per-Charity Distribution ---")
    dist = df.groupby(['Charity Name', 'Tier 2 Verdict']).size().unstack(fill_value=0)
    print(dist)
    
    print("\n--- Detailed Critique: Why are they failing at Tier 2? ---")
    fails = df[df['Tier 2 Verdict'] == 'FAIL']
    for charity in fails['Charity Name'].unique():
        print(f"\nCharity: {charity}")
        charity_fails = fails[fails['Charity Name'] == charity].head(5)
        for _, row in charity_fails.iterrows():
            print(f"- Tender: {row['Tender Title']}")
            print(f"  Rationale: {row['Tier 2 Rationale']}")
            print(f"  Scores: Total={row['Overall Score']}, Semantic={row['Semantic Score']}, UKCAT={row['UKCAT Score']}")
            print(f"  CPVs: Notice={row['Notice CPV Codes']}")

if __name__ == "__main__":
    analyze_v10()
