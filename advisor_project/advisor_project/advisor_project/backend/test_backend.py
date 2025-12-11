from advisor_backend import load_or_scrape_catalog
    
print("Import SUCCESS")

df = load_or_scrape_catalog("MAT", force_refresh=False)

print("DATAFRAME LOADED")
print(df.head())
