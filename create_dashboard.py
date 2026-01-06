import pandas as pd
import json
from datetime import datetime
import re

# Read the CSV file
print("Reading CSV file...")
df = pd.read_csv('nielsen_ad_intel_raos_all_competitors.csv', skiprows=2)
# Strip whitespace from column names
df.columns = df.columns.str.strip()
# Rename Dollars column if it exists with trailing space
if 'Dollars ' in df.columns:
    df = df.rename(columns={'Dollars ': 'Dollars'})

# Clean and prepare data
print("Cleaning data...")

# Clean Dollars column - remove $ and commas, convert to float
def clean_dollars(value):
    if pd.isna(value):
        return 0
    if isinstance(value, str):
        # Remove $ and commas
        cleaned = value.replace('$', '').replace(',', '').strip()
        try:
            return float(cleaned)
        except:
            return 0
    return float(value) if pd.notna(value) else 0

df['Dollars_Clean'] = df['Dollars'].apply(clean_dollars)

# Extract year and month for analysis
df['Month_Year'] = pd.to_datetime(df['Month'], format='%B %Y', errors='coerce')
df['Year'] = df['Month_Year'].dt.year
df['Month_Name'] = df['Month_Year'].dt.month_name()
df['Month_Num'] = df['Month_Year'].dt.month

# Brand mapping - map various brand name variations to standardized display names
BRAND_MAPPING = {
    'CAMPBELLS': 'Campbells',
    'RAOS': "Rao's",
    'RAO': "Rao's",
    'BOTTICELLI': 'Botticelli',
    'PREGO': 'Prego',
    'BERTOLI': 'Bertolli',
    'BERTOL': 'Bertolli',
    'RAGU': 'Ragu',
    'CLASSICO': 'Classico',
    'MEZZETTA': 'Mezzetta',
    'CARBONE': 'Carbone Fine Food'
}

# Group brands intelligently - identify main brand groups
def identify_main_brand(brand_name):
    if pd.isna(brand_name):
        return None
    
    brand_upper = str(brand_name).upper().strip()
    
    # Filter out invalid brand names
    invalid_names = ['NAN', 'DOLLARS', 'EXCLUDED', 'REPORT BUILDER', 'BUSINESS', 
                     'NATIONAL (NATIONAL)', '(STANDARD)START', '01/05/2026', '8277338']
    if brand_upper in invalid_names or len(brand_upper) < 2:
        return None
    
    # CAMPBELLS brands
    if 'CAMPBELL' in brand_upper:
        return 'Campbells'
    
    # RAOS brands
    if 'RAOS' in brand_upper or ('RAO' in brand_upper and "'" in str(brand_name)):
        return "Rao's"
    
    # BOTTICELLI brands
    if 'BOTTICELLI' in brand_upper:
        return 'Botticelli'
    
    # PREGO brands
    if 'PREGO' in brand_upper:
        return 'Prego'
    
    # BERTOLI brands
    if 'BERTOLI' in brand_upper or 'BERTOL' in brand_upper:
        return 'Bertolli'
    
    # RAGU brands
    if 'RAGU' in brand_upper:
        return 'Ragu'
    
    # CLASSICO brands
    if 'CLASSICO' in brand_upper:
        return 'Classico'
    
    # MEZZETTA brands
    if 'MEZZETTA' in brand_upper:
        return 'Mezzetta'
    
    # CARBONE brands - check for "FINE FOOD" or just "CARBONE"
    if 'CARBONE' in brand_upper:
        if 'FINE' in brand_upper or 'FOOD' in brand_upper:
            return 'Carbone Fine Food'
        return 'Carbone Fine Food'  # Default to full name
    
    return None

df['Brand_Main'] = df['Brand'].apply(identify_main_brand)

# Filter out rows with invalid brands
df = df[df['Brand_Main'].notna()]

# Additional filter: exclude brands that look like data errors
# Only keep brands with minimum spending threshold (at least $100 total)
brand_spending = df.groupby('Brand_Main')['Dollars_Clean'].sum()
valid_brands = brand_spending[brand_spending >= 100].index.tolist()
df = df[df['Brand_Main'].isin(valid_brands)]

# Get unique brands for dashboard (sorted by total spending)
brand_totals = df.groupby('Brand_Main')['Dollars_Clean'].sum().sort_values(ascending=False)
unique_brands = brand_totals.index.tolist()
print(f"\nUnique brand groups identified: {len(unique_brands)}")
for brand in unique_brands:
    count = len(df[df['Brand_Main'] == brand])
    print(f"  - {brand}: {count} records")

# Handle YouTube channels - group by YouTube but keep channel details
df['Distributor_Clean'] = df['Distributor'].fillna('')
df['Is_YouTube'] = df['Distributor_Clean'].str.contains('YOUTUBE', case=False, na=False)
df['YouTube_Channel'] = df.apply(lambda row: row['Distributor'] if row['Is_YouTube'] else None, axis=1)

# For digital media, use Distributor when Program Name is empty
df['Display_Name'] = df.apply(
    lambda row: row['Program Name'] if pd.notna(row['Program Name']) and str(row['Program Name']).strip() != '' 
    else (row['Distributor'] if pd.notna(row['Distributor']) else 'Unknown'), 
    axis=1
)

print(f"\nTotal records: {len(df)}")
print(f"Date range: {df['Month_Year'].min()} to {df['Month_Year'].max()}")
print(f"Brands: {df['Brand_Main'].value_counts().to_dict()}")

# Prepare data for dashboard
data_summary = {
    'total_records': len(df),
    'date_range': {
        'start': str(df['Month_Year'].min()),
        'end': str(df['Month_Year'].max())
    },
    'brands': df['Brand_Main'].value_counts().to_dict(),
    'unique_brands': unique_brands,
    'media_categories': df['Media Category'].value_counts().to_dict(),
    'media_types': df['Media Type'].value_counts().to_dict()
}

# Create aggregated datasets for different analyses
print("\nCreating aggregated datasets...")

# Year-over-year comparison
yoy_data = df.groupby(['Year', 'Brand_Main', 'Month_Num'])['Dollars_Clean'].sum().reset_index()
yoy_data['Month_Name'] = yoy_data['Month_Num'].map({
    1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
    7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December'
})

# Media Category analysis
media_category_data = df.groupby(['Media Category', 'Brand_Main', 'Year'])['Dollars_Clean'].sum().reset_index()

# Media Type analysis
media_type_data = df.groupby(['Media Type', 'Brand_Main', 'Year'])['Dollars_Clean'].sum().reset_index()

# Top programs/distributors by brand (for all brands)
top_programs_by_brand = {}
for brand in unique_brands:
    brand_data = df[df['Brand_Main'] == brand]
    top_programs_by_brand[brand] = brand_data.groupby(['Display_Name', 'Media Type', 'Year'])['Dollars_Clean'].sum().reset_index()

# Monthly spending by brand
monthly_spending = df.groupby(['Year', 'Month_Num', 'Month_Name', 'Brand_Main'])['Dollars_Clean'].sum().reset_index()

# YouTube analysis
youtube_data = df[df['Is_YouTube']].groupby(['Distributor', 'Brand_Main', 'Year'])['Dollars_Clean'].sum().reset_index()

# Convert to JSON for JavaScript
def df_to_json(df):
    records = df.to_dict('records')
    # Convert Timestamp objects to strings
    for record in records:
        for key, value in record.items():
            if pd.isna(value):
                record[key] = None
            elif isinstance(value, pd.Timestamp):
                record[key] = str(value)
    return records

# Convert top_programs_by_brand to JSON format
top_programs_json = {}
for brand, brand_df in top_programs_by_brand.items():
    top_programs_json[brand] = df_to_json(brand_df)

data_json = {
    'raw_data': df_to_json(df),
    'yoy_data': df_to_json(yoy_data),
    'media_category_data': df_to_json(media_category_data),
    'media_type_data': df_to_json(media_type_data),
    'top_programs_by_brand': top_programs_json,
    'monthly_spending': df_to_json(monthly_spending),
    'youtube_data': df_to_json(youtube_data),
    'summary': data_summary
}

# Save data as JSON
print("\nSaving data to JSON...")
with open('dashboard_data.json', 'w', encoding='utf-8') as f:
    json.dump(data_json, f, indent=2, default=str)

print("Data preparation complete!")
print(f"JSON file size: {len(json.dumps(data_json, default=str))} characters")
print(f"\nBrands available in dashboard: {', '.join(unique_brands)}")
