import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuration de la page
st.set_page_config(page_title="Mon Dashboard Strava", layout="wide", page_icon="🏃‍♂️")

st.title("Mon Tableau de Bord Running")

# Fonctions utilitaires
def parser_date_francaise(date_str):
    if not isinstance(date_str, str): return pd.NaT
    months = {
        "janv.": "01", "janvier": "01", "févr.": "02", "février": "02",
        "mars": "03", "avr.": "04", "avril": "04", "mai": "05", "juin": "06",
        "juil.": "07", "juillet": "07", "août": "08", "sept.": "09", 
        "septembre": "09", "oct.": "10", "octobre": "10", "nov.": "11", 
        "novembre": "11", "déc.": "12", "décembre": "12"
    }
    res = date_str.lower().replace(",", " ")
    for fr, num in months.items():
        if fr in res:
            res = res.replace(fr, f" {num} ")
            break
    return pd.to_datetime(res, format="%d %m %Y %H:%M:%S", errors='coerce')

def format_allure(allure_dec):
    if np.isnan(allure_dec) or np.isinf(allure_dec): return "--:--"
    minutes = int(allure_dec)
    secondes = int((allure_dec % 1) * 60)
    return f"{minutes}:{secondes:02d} /km"

def mins_to_clock(minutes_totales):
    if np.isnan(minutes_totales) or np.isinf(minutes_totales): return "-"
    heures = int(minutes_totales // 60)
    minutes = int(minutes_totales % 60)
    secondes = int((minutes_totales % 1) * 60)
    return f"{heures}h {minutes:02d}m {secondes:02d}s" if heures > 0 else f"{minutes}m {secondes:02d}s"

# Sidebar
st.sidebar.header("⚙️ Profil")
vma = st.sidebar.number_input("VMA (km/h)", 8.0, 25.0, 16.0, 0.1)
fc_max = st.sidebar.number_input("FC Max (bpm)", 120, 230, 185, 1)
uploaded_file = st.sidebar.file_uploader("Upload 'activities.csv'", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df['Date_Clean'] = df["Date de l'activité"].apply(parser_date_francaise)
    df = df[df["Type d'activité"].isin(['Course à pied', 'Run', 'Trail Run'])].copy()
    df['Distance_km'] = df['Distance.1'] / 1000
    df['Time_min'] = df['Durée de déplacement'] / 60
    df['Vitesse_kmh'] = df['Distance_km'] / (df['Time_min'] / 60)
    
    # Préparation données temporelles
    df = df.sort_values('Date_Clean')
    df['Année'] = df['Date_Clean'].dt.year.astype(str)
    df['Mois'] = df['Date_Clean'].dt.to_period('M').astype(str)
    df['Trimestre'] = "T" + df['Date_Clean'].dt.quarter.astype(str) + " " + df['Date_Clean'].dt.year.astype(str)
    df['Semaine'] = df['Date_Clean'].dt.strftime('%Y-W%V')

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Volumes", "🏆 Records", "🎯 Zones", "❤️ Cardio", "⚖️ Charge"])

    with tab1:
        st.subheader("Bilan Annuel")
        stats_an = df.groupby('Année').agg(Distance=('Distance_km', 'sum'), Runs=('ID de l\'activité', 'count'), Temps=('Time_min', 'sum')).reset_index()
        stats_an['Distance'] = stats_an['Distance'].round(1)
        st.dataframe(stats_an, use_container_width=True)
        
        st.subheader("Bilan Trimestriel")
        stats_trim = df.groupby('Trimestre').agg(Distance=('Distance_km', 'sum'), Runs=('ID de l\'activité', 'count')).reset_index().sort_values('Trimestre')
        stats_trim['Distance'] = stats_trim['Distance'].round(1)
        fig_trim = px.bar(stats_trim, x='Trimestre', y='Distance', text_auto='.1f', color_discrete_sequence=['#FF8C00'])
        st.plotly_chart(fig_trim, use_container_width=True)

        st.subheader("Progression Hebdomadaire (depuis 2023)")
        df_recents = df[df['Date_Clean'] >= '2023-01-01']
        vol_sem = df_recents.groupby('Semaine')['Distance_km'].sum().reset_index()
        vol_sem['Distance'] = vol_sem['Distance_km'].round(1)
        fig_sem = px.bar(vol_sem, x='Semaine', y='Distance', text_auto='.1f', color_discrete_sequence=['#20B2AA'])
        st.plotly_chart(fig_sem, use_container_width=True)

    with tab5:
        st.subheader("⚖️ Ratio de Charge (ACWR)")
        vol_hebdo = df_recents.groupby('Semaine')['Distance_km'].sum().reset_index().sort_values('Semaine')
        vol_hebdo['Chronique'] = vol_hebdo['Distance_km'].rolling(window=4, min_periods=1).mean()
        vol_hebdo['Ratio'] = vol_hebdo['Distance_km'] / vol_hebdo['Chronique']
        
        def get_zone(r):
            if r > 1.5: return "Rouge (Risque)"
            if r < 0.8: return "Bleu (Sous-charge)"
            return "Vert (Optimal)"
        
        vol_hebdo['Zone'] = vol_hebdo['Ratio'].apply(get_zone)
        
        fig_ratio = px.scatter(vol_hebdo, x='Semaine', y='Ratio', color='Zone', 
                               color_discrete_map={"Vert (Optimal)": "green", "Bleu (Sous-charge)": "blue", "Rouge (Risque)": "red"})
        fig_ratio.add_trace(px.line(vol_hebdo, x='Semaine', y='Ratio').data[0])
        fig_ratio.add_hline(y=1.5, line_dash="dash", line_color="red")
        fig_ratio.add_hline(y=0.8, line_dash="dash", line_color="blue")
        st.plotly_chart(fig_ratio, use_container_width=True)
        
        last = vol_hebdo['Ratio'].iloc[-1]
        if last > 1.5: st.error(f"Ratio actuel : {last:.2f} (Surcharge)")
        elif last < 0.8: st.info(f"Ratio actuel : {last:.2f} (Sous-charge)")
        else: st.success(f"Ratio actuel : {last:.2f} (Optimal)")

    # ... (Ajoute ici le code des onglets 2, 3 et 4 des messages précédents)
