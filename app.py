import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuration
st.set_page_config(page_title="Dashboard Running Complet", layout="wide", page_icon="🏃‍♂️")
st.title("Mon Tableau de Bord Running")

# --- FONCTIONS ---
def parser_date_francaise(date_str):
    if not isinstance(date_str, str): return pd.NaT
    months = {"janv.": "01", "févr.": "02", "mars": "03", "avr.": "04", "mai": "05", "juin": "06", 
              "juil.": "07", "août": "08", "sept.": "09", "oct.": "10", "nov.": "11", "déc.": "12"}
    res = date_str.lower().replace(",", " ")
    for fr, num in months.items():
        if fr in res: res = res.replace(fr, f" {num} "); break
    return pd.to_datetime(res, format="%d %m %Y %H:%M:%S", errors='coerce')

def format_allure(allure_dec):
    if np.isnan(allure_dec) or np.isinf(allure_dec): return "--:--"
    return f"{int(allure_dec)}:{int((allure_dec % 1) * 60):02d} /km"

def mins_to_clock(minutes_totales):
    if np.isnan(minutes_totales) or np.isinf(minutes_totales): return "-"
    h, m = divmod(int(minutes_totales), 60)
    s = int((minutes_totales % 1) * 60)
    return f"{h}h {m:02d}m {s:02d}s" if h > 0 else f"{m}m {s:02d}s"

# --- SIDEBAR ---
vma = st.sidebar.number_input("VMA actuelle (km/h)", 8.0, 25.0, 16.0, 0.1)
fc_max = st.sidebar.number_input("FC Max (bpm)", 120, 230, 185, 1)
uploaded_file = st.sidebar.file_uploader("Upload 'activities.csv'", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df['Date_Clean'] = df["Date de l'activité"].apply(parser_date_francaise)
    df = df.dropna(subset=['Date_Clean'])
    df = df[df["Type d'activité"].isin(['Course à pied', 'Run', 'Trail Run'])].copy()
    
    # Calculs
    df['Distance_km'] = df['Distance.1'] / 1000
    df['Time_min'] = df['Durée de déplacement'] / 60
    df['Vitesse_kmh'] = df['Distance_km'] / (df['Time_min'] / 60)
    df['Année'] = df['Date_Clean'].dt.year.astype(str)
    df['Trimestre'] = "T" + df['Date_Clean'].dt.quarter.astype(str) + " " + df['Date_Clean'].dt.year.astype(str)
    df['Semaine'] = df['Date_Clean'].dt.strftime('%Y-W%V')

    # --- ONGLETS ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Volumes", "🏆 Records", "🎯 Zones", "❤️ Cardio", "⚖️ Charge"])

    with tab1:
        st.subheader("Bilan par Période")
        # Années
        stats_an = df.groupby('Année').agg(Distance=('Distance_km', 'sum'), Runs=('ID de l\'activité', 'count')).reset_index()
        stats_an['Distance'] = stats_an['Distance'].round(1)
        st.dataframe(stats_an, use_container_width=True)
        # Trimestres
        stats_trim = df.groupby('Trimestre').agg(Distance=('Distance_km', 'sum')).reset_index()
        fig_t = px.bar(stats_trim, x='Trimestre', y='Distance', text_auto='.1f', color_discrete_sequence=['#FF8C00'])
        st.plotly_chart(fig_t, use_container_width=True)
        # Hebdo
        df_rec = df[df['Date_Clean'] >= '2023-01-01']
        vol_s = df_rec.groupby('Semaine')['Distance_km'].sum().reset_index()
        fig_s = px.bar(vol_s, x='Semaine', y='Distance_km', text_auto='.1f', color_discrete_sequence=['#20B2AA'])
        st.plotly_chart(fig_s, use_container_width=True)

    with tab2:
        st.subheader("Records Réels vs Prédictions")
        zones = {"5 km": {"d": 5.0, "p": 0.94}, "10 km": {"d": 10.0, "p": 0.86}, "Semi": {"d": 21.1, "p": 0.80}, "Marathon": {"d": 42.2, "p": 0.72}}
        records = []
        for nom, config in zones.items():
            run = df[df['Distance_km'] >= (config['d'] * 0.95)]
            best = mins_to_clock((config['d'] / run['Vitesse_kmh']) * 60).min() if not run.empty else "-"
            records.append({"Distance": nom, "Record Strava": best, "Objectif VMA": mins_to_clock((config['d'] / (vma * config['p'])) * 60)})
        st.table(pd.DataFrame(records).set_index("Distance"))

    with tab3:
        st.subheader("Zones de travail")
        zones_data = {"Type": ["EF", "Marathon", "Seuil", "VMA"], "Vitesse (km/h)": [f"{vma*0.6:.1f}-{vma*0.7:.1f}", f"{vma*0.75:.1f}-{vma*0.8:.1f}", f"{vma*0.83:.1f}-{vma*0.87:.1f}", f"{vma*0.95:.1f}-{vma:.1f}"]}
        st.table(pd.DataFrame(zones_data))

    with tab4:
        st.subheader("Efficacité Cardio")
        df_c = df[df['Fréquence cardiaque moyenne'] > 0].copy()
        df_c['Indice'] = df_c['Fréquence cardiaque moyenne'] / df_c['Vitesse_kmh']
        fig_c = px.line(df_c, x='Date_Clean', y=df_c['Indice'].rolling(5).mean())
        st.plotly_chart(fig_c, use_container_width=True)

    with tab5:
        st.subheader("⚖️ Ratio de Charge")
        vol = df_rec.groupby('Semaine')['Distance_km'].sum().reset_index()
        vol['Ratio'] = vol['Distance_km'] / vol['Distance_km'].rolling(4, min_periods=1).mean()
        vol['Zone'] = pd.cut(vol['Ratio'], bins=[0, 0.8, 1.5, 10], labels=["Bleu (Sous-charge)", "Vert (Optimal)", "Rouge (Risque)"])
        fig_r = px.scatter(vol, x='Semaine', y='Ratio', color='Zone', color_discrete_map={"Vert (Optimal)": "green", "Bleu (Sous-charge)": "blue", "Rouge (Risque)": "red"})
        fig_r.add_trace(px.line(vol, x='Semaine', y='Ratio').data[0])
        st.plotly_chart(fig_r, use_container_width=True)
