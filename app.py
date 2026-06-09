import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuration de la page web
st.set_page_config(page_title="Mon Dashboard Strava", layout="wide", page_icon="🏃‍♂️")

st.title("Mon Tableau de Bord Running - Analyse Strava")
st.markdown("Analyse avancée de tes volumes, records officiels, VMA, VO2 Max et Seuils.")

# --- CHARGEMENT DU FICHIER CSV ---
st.sidebar.header("📁 Importation des données")
uploaded_file = st.sidebar.file_uploader("Glisse ton fichier 'activities.csv' ici :", type=["csv"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Nettoyage des dates en français
        mois_trad = {
            "janv.": "january", "févr.": "february", "mars": "march", "avr.": "april",
            "mai": "may", "juin": "june", "juil.": "july", "août": "august",
            "sept.": "september", "oct.": "october", "nov.": "november", "déc.": "december"
        }
        for fr, en in mois_trad.items():
            df["Date de l'activité"] = df["Date de l'activité"].str.replace(fr, en, case=False, regex=False)

        df['Date_Clean'] = pd.to_datetime(df["Date de l'activité"], errors='coerce')
        df = df.dropna(subset=['Date_Clean'])
        
        # Filtrer la Course à pied
        df = df[df["Type d'activité"].isin(['Course à pied', 'Run', 'Trail Run'])]
        
        if df.empty:
            st.warning("Aucune activité de course à pied trouvée.")
            st.stop()
            
        # Unités de base
        df['Distance_km'] = df['Distance.1'] / 1000
        df['Time_min'] = df['Durée de déplacement'] / 60
        df['Vitesse_kmh'] = df['Vitesse moyenne'] * 3.6
        df['Vitesse_max_kmh'] = df['Vitesse max.'] * 3.6
        df['Allure_decimal'] = 60 / df['Vitesse_kmh']
        
        df = df.sort_values('Date_Clean')
        df['Mois'] = df['Date_Clean'].dt.to_period('M').astype(str)
        
        # --- CALCULS AVANCÉS (VMA PHYSIOLOGIQUE, VO2 MAX & SEUIL) ---
        # La VMA est la vitesse max soutenable sur ~6 minutes. 
        # On l'estime en combinant la vitesse max de la séance et la vitesse moyenne pondérée par la distance.
        df['VMA_Est'] = (df['Vitesse_kmh'] * 0.7) + (df['Vitesse_max_kmh'] * 0.3)
        
        # On applique une barrière pour éviter les bugs GPS (ex: un point à 40 km/h)
        df['VMA_Est'] = df['VMA_Est'].clip(8, 25)
        
        # Pour éviter que les footings lents fassent baisser la VMA, on prend la VMA max connue "à ce jour" (Cummax)
        # lissée légèrement pour refléter la forme du moment.
        df['VMA_Lissée'] = df['VMA_Est'].cummax() * 0.95
        # On s'assure que la VMA lissée ne soit pas inférieure à la vitesse moyenne du run actuel
        df['VMA_Lissée'] = np.maximum(df['VMA_Lissée'], df['Vitesse_kmh'])
        
        # Calcul de la VO2 Max selon la formule scientifique : VO2 Max = VMA * 3.5
        df['VO2_Lissée'] = df['VMA_Lissée'] * 3.5
        
        # Le seuil lactique est généralement situé entre 80% (coureur régulier) et 88% (expert) de la VMA.
        # S'il y a du cardio, on ajuste le pourcentage de manière dynamique.
        if 'Fréquence cardiaque moyenne' in df.columns and df['Fréquence cardiaque moyenne'].notna().sum() > 0:
            df['Seuil_Lissé'] = df['VMA_Lissée'] * (165 / df['Fréquence cardiaque moyenne'].cummax().clip(140, 200)) * 0.85
        else:
            df['Seuil_Lissé'] = df['VMA_Lissée'] * 0.85
            
        df['Seuil_Lissé'] = df['Seuil_Lissé'].clip(6, 22)

        # --- EXTRACTEUR DE MEILLEURS EFFORTS (5K, 10K, SEMI, MARATHON) ---
        def calcul_temps_format(vitesse, distance_cible):
            temps_heures = distance_cible / vitesse
            minutes_totales = temps_heures * 60
            heures = int(minutes_totales // 60)
            minutes = int(minutes_totales % 60)
            secondes = int((minutes_totales % 1) * 60)
            if heures > 0:
                return f"{heures}h {minutes:02d}m {secondes:02d}s"
            return f"{minutes}m {secondes:02d}s"

        records = {"Effort": [], "Temps Estimé / Réalisé": [], "Date": [], "Nom de la sortie": []}
        
        dist_cibles = {"5 km": 4.9, "10 km": 9.8, "Semi-Marathon (21.1 km)": 20.9, "Marathon (42.2 km)": 41.8}
        dist_exactes = {"5 km": 5.0, "10 km": 10.0, "Semi-Marathon (21.1 km)": 21.1, "Marathon (42.2 km)": 42.2}
        
        for nom, seuil_dist in dist_cibles.items():
            df_filtre = df[df['Distance_km'] >= seuil_dist]
            if not df_filtre.empty:
                # On prend la ligne où la vitesse moyenne était la plus élevée sur cette distance
                meilleure_session = df_filtre.sort_values(by='Vitesse_kmh', ascending=False).iloc[0]
                records["Effort"].append(nom)
                records["Temps Estimé / Réalisé"].append(calcul_temps_format(meilleure_session['Vitesse_kmh'], dist_exactes[nom]))
                records["Date"].append(meilleure_session['Date_Clean'].strftime('%d/%m/%Y'))
                records["Nom de la sortie"].append(meilleure_session["Nom de l'activité"])
            else:
                records["Effort"].append(nom)
                records["Temps Estimé / Réalisé"].append("Pas encore couru")
                records["Date"].append("-")
                records["Nom de la sortie"].append("-")
                
        df_records = pd.DataFrame(records)

        # --- CRÉATION DES ONGLETS ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Volume & Général", 
            "🏆 Meilleurs Efforts (5k, 10k, Semi...)", 
            "📈 VMA & VO2 Max", 
            "🎯 Évolution du Seuil"
        ])

        # --- ONGLET 1 : VOLUME ---
        with tab1:
            st.subheader("Résumé de tes statistiques globales")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Distance Totale", f"{df['Distance_km'].sum():,.1f} km".replace(",", " "))
            c2.metric("Nombre de Courses", f"{len(df)} sorties")
            c3.metric("Temps Total", f"{df['Time_min'].sum()/60:.1f} h")
            
            allure_moy = df['Allure_decimal'].mean()
            if not np.isnan(allure_moy):
                c4.metric("Allure Moyenne Globale", f"{int(allure_moy)}:{int((allure_moy%1)*60):02d} /km")
            
            st.subheader("📆 Volume mensuel accumulé")
            vol_mensuel = df.groupby('Mois')['Distance_km'].sum().reset_index()
            fig_vol = px.bar(vol_mensuel, x='Mois', y='Distance_km', labels={'Distance_km': 'Distance (km)'}, color_discrete_sequence=['#FC4C02'])
            st.plotly_chart(fig_vol, use_container_width=True)

        # --- ONGLET 2 : MEILLEURS EFFORTS ---
        with tab2:
            st.subheader("🏆 Tes records personnels par distance de référence")
            st.markdown("Calculé automatiquement à partir de tes meilleures allures tenues sur ces distances.")
            st.table(df_records.set_index("Effort"))
            
            st.subheader("🏃‍♂️ Top 5 de tes sorties les plus longues (Endurance)")
            top_dist = df.sort_values(by='Distance_km', ascending=False).head(5)[["Date de l'activité", "Nom de l'activité", 'Distance_km']]
            st.dataframe(top_dist.rename(columns={"Date de l'activité": 'Date', "Nom de l'activité": 'Nom', 'Distance_km': 'Distance (km)'}), use_container_width=True)

        # --- ONGLET 3 : VMA & VO2 MAX ---
        with tab3:
            st.subheader("📈 Évolution de tes capacités maximales (Formule lissée)")
            st.markdown("_Note : Cette courbe isole tes pics de puissance pour refléter ton vrai niveau maximal, sans être polluée par tes footings de récupération._")
            col_v1, col_v2 = st.columns(2)
            
            with col_v1:
                fig_vo2 = px.line(df, x='Date_Clean', y='VO2_Lissée', labels={'VO2_Lissée': 'VO2 Max'}, title="Évolution de la VO2 Max (ml/kg/min)", color_discrete_sequence=['#00CC96'])
                st.plotly_chart(fig_vo2, use_container_width=True)
                st.metric("VO2 Max Estimée Actuelle", f"{df['VO2_Lissée'].iloc[-1]:.1f}")
                
            with col_v2:
                fig_vma = px.line(df, x='Date_Clean', y='VMA_Lissée', labels={'VMA_Lissée': 'VMA (km/h)'}, title="Évolution de la VMA (km/h)", color_discrete_sequence=['#AB63FA'])
                st.plotly_chart(fig_vma, use_container_width=True)
                st.metric("VMA Estimée Actuelle", f"{df['VMA_Lissée'].iloc[-1]:.1f} km/h")

        # --- ONGLET 4 : SEUIL ---
        with tab4:
            st.subheader("🎯 Évolution de ton seuil lactique")
            st.markdown("Le seuil correspond à l'allure maximale que tu peux maintenir sans accumuler de fatigue lactique critique (effort de 45 à 60 min).")
            
            fig_seuil = px.line(df, x='Date_Clean', y='Seuil_Lissé', labels={'Seuil_Lissé': 'Seuil (km/h)'}, title="Vitesse au Seuil (km/h)", color_discrete_sequence=['#FFA15A'])
            st.plotly_chart(fig_seuil, use_container_width=True)
            
            vitesse_seuil = df['Seuil_Lissé'].iloc[-1]
            allure_seuil_dec = 60 / vitesse_seuil
            st.metric("Vitesse actuelle au seuil", f"{vitesse_seuil:.1f} km/h (soit {int(allure_seuil_dec)}:{int((allure_seuil_dec%1)*60):02d} /km)")

    except Exception as e:
        st.error(f"Fichier illisible ou colonnes manquantes. Erreur : {e}")
else:
    st.info("👋 En attente de ton fichier. Glisse-le dans le volet à gauche !")
