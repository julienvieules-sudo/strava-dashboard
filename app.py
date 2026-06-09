import pandas as pd
import numpy as np

df = pd.read_csv('activities.csv')

# Let's inspect the parsing of dates carefully.
mois_trad = {
    "janv.": "01", "févr.": "02", "mars": "03", "avr.": "04",
    "mai": "05", "juin": "06", "juil.": "07", "août": "08",
    "sept.": "09", "oct.": "10", "nov.": "11", "déc.": "12"
}
date_brute = df["Date de l'activité"].copy()
for fr, num in mois_trad.items():
    date_brute = date_brute.str.replace(fr, num, case=False, regex=False)

df['Date_Clean'] = pd.to_datetime(date_brute, errors='coerce')

# Print info about total rows and types
print("Total rows in CSV:", len(df))
print("Activity types value counts:\n", df["Type d'activité"].value_counts())

df_runs = df[df["Type d'activité"].isin(['Course à pied', 'Run', 'Trail Run'])].copy()
print("Total runs identified before date filtering:", len(df_runs))
print("NaT in Date_Clean for runs:", df_runs['Date_Clean'].isna().sum())

# Let's see some example rows where Date_Clean is NaT
print("Example NaT date strings:\n", df_runs[df_runs['Date_Clean'].isna()]["Date de l'activité"].head(10))
