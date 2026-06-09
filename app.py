import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuration de la page web
st.set_page_config(page_title="Mon Dashboard Strava", layout="wide", page_icon="🏃‍♂️")

st.title("Mon Tableau de Bord Running - Analyse Strava")
st.markdown("Analyse automatique du volume, des records, de la VMA, de la VO2 Max et du Seuil.")

# --- CHARGEMENT DU FICHIER CSV ---
st.sidebar.header("📁 Importation des données")
uploaded_file = st.sidebar.file_uploader("Glisse ton fichier 'activities.csv' ici :", type=["csv"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        
        # 1. Nettoyage et filtrage des dates
        df['Activity Date'] = pd.to_datetime(df['Activity Date'], errors='coerce')
        df = df.dropna(subset=['Activity Date'])
        
        # 2. Filtrer uniquement la Course à pied (Strava utilise 'Run' ou 'Trail Run')
        df = df[df['Activity Type'].isin(['Run', 'Course', 'Trail Run'])]
        
        if df.empty:
            st.warning("Aucune activité de course à pied trouvée dans ce fichier.")
            st.stop()
            
        # 3. Conversion des unités (Strava exporte souvent la distance en mètres et le temps en secondes)
        if df['Distance'].max() > 500:
            df['Distance_km'] = df['Distance'] / 1000
        else:
            df['Distance_km'] = df['Distance']
            
        if 'Elapsed Time' in df.columns:
            df['Time_min'] = df['Elapsed Time'] / 60
        elif 'Moving Time' in df.columns:
            df['Time_min'] = df['Moving Time'] / 60
            
        # Calcul de la vitesse et de l'allure décimale
        df['Vitesse_kmh'] = df['Distance_km'] / (df['Time_min'] / 60)
        df['Allure_decimal'] = df['Time_min'] / df['Distance_km']
        
        # Tri chronologique et création de la colonne Mois
        df = df.sort_values('Activity Date')
        df['Mois'] = df['Activity Date'].dt.to_period('M').astype(str)
        
        # --- ESTIMATIONS PHYSIOLOGIQUES (VMA, VO2 MAX, SEUIL) ---
        has_hr = 'Average Heart Rate' in df.columns and df['Average Heart Rate'].notna().sum() > 0
        
        if has_hr:
            # Si tu as une ceinture/montre cardio : calcul basé sur l'efficacité cardiaque (FC vs Vitesse)
            # On normalise sur une FC moyenne de référence (ex: 170 bpm)
            df['VO2_Max_Est'] = (df['Vitesse_kmh'] * 15.3) * (175 / df['Average Heart Rate'])
            df['VO2_Max_Est'] = df['VO2_Max_Est'].clip(30, 80) # Élimination des valeurs aberrantes
            
            # Seuil lactique estimé en km/h (allure tenable à ~85% de FC Max)
            df['Seuil_Est_kmh'] = df['Vitesse_kmh'] * (165 / df['Average Heart Rate'])
            df['Seuil_Est_kmh'] = df['Seuil_Est_kmh'].clip(6, 22)
        else:
            # Si pas de cardio, estimation mathématique basée sur tes pics de vitesse au fil du temps
            df['VO2_Max_Est'] = df['Vitesse_kmh'] * 3.5
            df['VO2_Max_Est'] = df['VO2_Max_Est'].clip(30, 80)
            df['Seuil_Est_kmh'] = df['Vitesse_kmh'] * 0.85
            df['Seuil_Est_kmh'] = df['Seuil_Est_kmh'].clip(6, 22)
            
        df['VMA_Est'] = df['VO2_Max_Est'] / 3.5
        
        # Application d'une moyenne glissante sur 3 activités pour lisser les courbes (éviter les pics des séances de récup)
        df['VO2_Lissée'] = df['VO2_Max_Est'].rolling(window=3, min_periods=1).mean()
        df['VMA_Lissée'] = df['VMA_Est'].rolling(window=3, min_periods=1).mean()
        df['Seuil_Lissé'] = df['Seuil_Est_kmh'].rolling(window=3, min_periods=1).mean()

        # --- CRÉATION DES ONGLETS ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Volume & Général", 
            "🏆 Meilleurs Efforts", 
            "📈 VMA & VO2 Max", 
            "🎯 Évolution du Seuil"
        ])

        # --- ONGLET 1 : VOLUME ---
        with tab1:
            st.subheader("Résumé de tes statistiques")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Distance Totale", f"{df['Distance_km'].sum():,.1f} km".replace(",", " "))
            c2.metric("Nombre de Courses", f"{len(df)} sorties")
            c3.metric("Temps Total", f"{df['Time_min'].sum()/60:.1f} heures")
            
            # Allure moyenne globale au format MM:SS
            allure_moy = df['Allure_decimal'].mean()
            c4.metric("Allure Moyenne", f"{int(allure_moy)}:{int((allure_moy%1)*60):02d} /km")
            
            st.subheader("📆 Volume mensuel accumulé")
            vol_mensuel = df.groupby('Mois')['Distance_km'].sum().reset_index()
            fig_vol = px.bar(vol_mensuel, x='Mois', y='Distance_km', title="Kilomètres par mois", color_discrete_sequence=['#FC4C02']) # Orange Strava
            st.plotly_chart(fig_vol, use_container_width=True)

        # --- ONGLET 2 : MEILLEURS EFFORTS ---
        with tab2:
            st.subheader("🏆 Tes records personnels enregistrés")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Top 5 de tes sorties les plus longues (Endurance)**")
                top_dist = df.sort_values(by='Distance_km', ascending=False).head(5)[['Activity Date', 'Activity Name', 'Distance_km']]
                st.dataframe(top_dist.rename(columns={'Activity Date': 'Date', 'Activity Name': 'Nom', 'Distance_km': 'Distance (km)'}), use_container_width=True)
                
            with col_b:
                st.markdown("**Top 5 de tes sorties les plus rapides (Vitesse moyenne - min. 3km)**")
                df_3k = df[df['Distance_km'] >= 3.0]
                if not df_3k.empty:
                    top_speed = df_3k.sort_values(by='Vitesse_kmh', ascending=False).head(5)[['Activity Date', 'Activity Name', 'Vitesse_kmh']]
                    st.dataframe(top_speed.rename(columns={'Activity Date': 'Date', 'Activity Name': 'Nom', 'Vitesse_kmh': 'Vitesse (km/h)'}), use_container_width=True)

        # --- ONGLET 3 : VMA & VO2 MAX ---
        with tab3:
            st.subheader("📈 Évolution de tes capacités maximales")
            col_v1, col_v2 = st.columns(2)
            
            with col_v1:
                fig_vo2 = px.line(df, x='Activity Date', y='VO2_Lissée', title="Tendance VO2 Max (ml/kg/min)", color_discrete_sequence=['#00CC96'])
                st.plotly_chart(fig_vo2, use_container_width=True)
                st.metric("VO2 Max Estimée Actuelle", f"{df['VO2_Lissée'].iloc[-1]:.1f}")
                
            with col_v2:
                fig_vma = px.line(df, x='Activity Date', y='VMA_Lissée', title="Tendance VMA (km/h)", color_discrete_sequence=['#AB63FA'])
                st.plotly_chart(fig_vma, use_container_width=True)
                st.metric("VMA Estimée Actuelle", f"{df['VMA_Lissée'].iloc[-1]:.1f} km/h")

        # --- ONGLET 4 : SEUIL ---
        with tab4:
            st.subheader("🎯 Évolution de ton seuil lactique")
            st.markdown("Le seuil correspond à la vitesse maximale que tu peux maintenir sans accumuler de fatigue lactique critique (effort de 45 à 60 min).")
            
            fig_seuil = px.line(df, x='Activity Date', y='Seuil_Lissé', title="Vitesse au Seuil au cours du temps (km/h)", color_discrete_sequence=['#FFA15A'])
            st.plotly_chart(fig_seuil, use_container_width=True)
            
            vitesse_seuil = df['Seuil_Lissé'].iloc[-1]
            allure_seuil_dec = 60 / vitesse_seuil
            st.metric("Vitesse actuelle au seuil", f"{vitesse_seuil:.1f} km/h (soit {int(allure_seuil_dec)}:{int((allure_seuil_dec%1)*60):02d} /km)")

    except Exception as e:
        st.error(f"Fichier illisible ou colonnes manquantes. Erreur : {e}")
else:
    st.info("👋 En attente de ton fichier. Télécharge ton archive Strava, extrait le fichier 'activities.csv' et glisse-le ici !")
