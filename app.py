import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuration de la page web
st.set_page_config(page_title="Mon Dashboard Strava", layout="wide", page_icon="🏃‍♂️")

st.title("Mon Tableau de Bord Running")
st.markdown("Analyse de ton historique Strava combinée à tes zones cibles personnalisées.")

# Fonction de décodage des dates
def parser_date_francaise(date_str):
    if not isinstance(date_str, str):
        return pd.NaT
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

# Convertisseurs de formats
def format_allure(allure_dec):
    if np.isnan(allure_dec) or np.isinf(allure_dec):
        return "--:--"
    minutes = int(allure_dec)
    secondes = int((allure_dec % 1) * 60)
    return f"{minutes}:{secondes:02d} /km"

def mins_to_clock(minutes_totales):
    if np.isnan(minutes_totales) or np.isinf(minutes_totales):
        return "-"
    heures = int(minutes_totales // 60)
    minutes = int(minutes_totales % 60)
    secondes = int((minutes_totales % 1) * 60)
    if heures > 0:
        return f"{heures}h {minutes:02d}m {secondes:02d}s"
    return f"{minutes}m {secondes:02d}s"

# --- CONFIGURATION DU PROFIL ATHLÉTIQUE MANUEL ---
st.sidebar.header("⚙️ 1. Ton Profil Athlétique")
vma_manuelle = st.sidebar.number_input("Saisis ta VMA actuelle (km/h) :", min_value=8.0, max_value=25.0, value=16.0, step=0.1)
fc_max_manuelle = st.sidebar.number_input("Saisis ta FC Max réelle (bpm) :", min_value=120, max_value=230, value=185, step=1)

st.sidebar.markdown("---")
st.sidebar.header("📁 2. Importation des données")
uploaded_file = st.sidebar.file_uploader("Glisse ton fichier 'activities.csv' ici :", type=["csv"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        df['Date_Clean'] = df["Date de l'activité"].apply(parser_date_francaise)
        df = df.dropna(subset=['Date_Clean'])
        df = df[df["Type d'activité"].isin(['Course à pied', 'Run', 'Trail Run'])].copy()
        
        if df.empty:
            st.warning("Aucune activité de course à pied trouvée.")
            st.stop()
            
        # Conversion des unités Strava
        df['Distance_km'] = df['Distance.1'] / 1000
        df['Time_min'] = df['Durée de déplacement'] / 60
        df['Vitesse_kmh'] = df['Distance_km'] / (df['Time_min'] / 60)
        
        # Variables temporelles
        df = df.sort_values('Date_Clean')
        df['Année'] = df['Date_Clean'].dt.year.astype(str)
        df['Mois'] = df['Date_Clean'].dt.to_period('M').astype(str)
        
        # Ajout des identifiants et libellés trimestriels (ex: 2026-Q2 et T2 2026)
        df['Trimestre_Id'] = df['Date_Clean'].dt.year.astype(str) + "-Q" + df['Date_Clean'].dt.quarter.astype(str)
        df['Trimestre'] = "T" + df['Date_Clean'].dt.quarter.astype(str) + " " + df['Date_Clean'].dt.year.astype(str)

        # --- STATS PAR AN ---
        stats_an = df.groupby('Année').agg(
            Distance_Totale=('Distance_km', 'sum'),
            Nombre_Sorties=("ID de l'activité", "count"),
            Temps_Total_Min=('Time_min', 'sum')
        ).reset_index()
        
        stats_an['Distance_Arrondie'] = stats_an['Distance_Totale'].round(1)
        stats_an['Volume_Horaire'] = (stats_an['Temps_Total_Min'] / 60).round(1)
        stats_an['Allure_Dec_An'] = stats_an['Temps_Total_Min'] / stats_an['Distance_Totale']
        stats_an['Allure moyenne'] = stats_an['Allure_Dec_An'].apply(format_allure)
        
        stats_an_affichage = stats_an[['Année', 'Distance_Arrondie', 'Nombre_Sorties', 'Volume_Horaire', 'Allure moyenne']].copy()
        stats_an_affichage = stats_an_affichage.sort_values('Année', ascending=False)
        stats_an_affichage = stats_an_affichage.rename(columns={
            'Distance_Arrondie': 'Distance (km)', 
            'Nombre_Sorties': 'Nombre de runs',
            'Volume_Horaire': 'Volume horaire (h)'
        })

        # --- STATS PAR TRIMESTRE ---
        stats_trim = df.groupby(['Trimestre_Id', 'Trimestre']).agg(
            Distance_Totale=('Distance_km', 'sum'),
            Nombre_Sorties=("ID de l'activité", "count"),
            Temps_Total_Min=('Time_min', 'sum')
        ).reset_index()
        
        stats_trim['Distance (km)'] = stats_trim['Distance_Totale'].round(1)
        stats_trim['Volume horaire (h)'] = (stats_trim['Temps_Total_Min'] / 60).round(1)
        stats_trim['Allure_Dec_Trim'] = stats_trim['Temps_Total_Min'] / stats_trim['Distance_Totale']
        stats_trim['Allure moyenne'] = stats_trim['Allure_Dec_Trim'].apply(format_allure)
        
        stats_trim_affichage = stats_trim[['Trimestre', 'Distance (km)', 'Nombre_Sorties', 'Volume horaire (h)', 'Allure moyenne']].copy()
        # Tri décroissant du trimestre le plus récent au plus ancien
        stats_trim_affichage = stats_trim_affichage.iloc[::-1]
        stats_trim_affichage = stats_trim_affichage.rename(columns={'Nombre_Sorties': 'Nombre de runs'})

        # --- RECHERCHE ET EXTRACTION DES CHRONOS RÉELS ET ESTIMATIONS ---
        zones_vma_pred = {
            "5 km": {"d": 5.0, "p_prud": 0.89, "p_opt": 0.94},
            "10 km": {"d": 10.0, "p_prud": 0.82, "p_opt": 0.86},
            "Semi-Marathon": {"d": 21.1, "p_prud": 0.76, "p_opt": 0.80},
            "Marathon": {"d": 42.195, "p_prud": 0.67, "p_opt": 0.72}
        }
        
        summary_records = []
        for nom, config in zones_vma_pred.items():
            d_cible = config["d"]
            
            # Calcul du Chrono Réel Strava
            df_utiles = df[df['Distance_km'] >= (d_cible * 0.95)]
            if not df_utiles.empty:
                temps_au_prorata = (d_cible / df_utiles['Vitesse_kmh']) * 60
                chrono_reel_str = mins_to_clock(temps_au_prorata.min())
            else:
                chrono_reel_str = "Pas de run assez long"
                
            # Calcul des Prédictions en Fourchette
            t_prudent = (d_cible / (vma_manuelle * config["p_prud"])) * 60
            t_optimiste = (d_cible / (vma_manuelle * config["p_opt"])) * 60
            
            summary_records.append({
                "Distance": nom,
                "Mon Meilleur Réel (Strava)": chrono_reel_str,
                "Prédiction - Fourchette Basse (Prudent)": mins_to_clock(t_prudent),
                "Prédiction - Fourchette Haute (Optimiste)": mins_to_clock(t_optimiste)
            })
            
        df_unifié_records = pd.DataFrame(summary_records)

        # --- CRÉATION DES ONGLETS ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Volumes Annuels, Trimestriels & Mensuels", 
            "🏆 Records Réels & Prédictions de Course", 
            "🎯 Mes Zones d'Entraînement (Allures & Cardio)",
            "❤️ Analyse Efficacité Cardio"
        ])

        # --- TAB 1 : VOLUMES ---
        with tab1:
            st.subheader("🏃‍♂️ Vos statistiques globales historiques (Tout temps)")
            c1, c2, c3, c4 = st.columns(4)
            dist_totale = df['Distance_km'].sum()
            runs_totaux = len(df)
            temps_total_heures = df['Time_min'].sum() / 60
            allure_globale_dec = df['Time_min'].sum() / dist_totale
            
            c1.metric("Distance Totale Cumulée", f"{dist_totale:,.1f} km".replace(",", " "))
            c2.metric("Total de Sorties", f"{runs_totaux} runs")
            c3.metric("Temps de Vol Total", f"{temps_total_heures:.1f} heures")
            c4.metric("Allure Moyenne Globale", format_allure(allure_globale_dec))
            
            st.markdown("---")
            st.subheader("📆 Bilan détaillé par Année")
            col_table, col_graph = st.columns(2)
            with col_table:
                st.dataframe(stats_an_affichage, use_container_width=True, hide_index=True)
            with col_graph:
                fig_an = px.bar(stats_an, x='Année', y='Distance_Arrondie', labels={'Distance_Arrondie': 'Distance (km)'}, title="Volume annuel (km)", color_discrete_sequence=['#FC4C02'], text_auto='.1f')
                fig_an.update_traces(textposition='outside')
                st.plotly_chart(fig_an, use_container_width=True)
                
            st.markdown("---")
            st.subheader("🗓️ NOUVEAU : Bilan détaillé par Trimestre")
            st.dataframe(stats_trim_affichage, use_container_width=True, hide_index=True)
                
            st.markdown("---")
            # Filtre à partir de 2023 pour le graphique mensuel
            st.subheader("📆 Progression mensuelle (Depuis 2023)")
            df_recents = df[df['Date_Clean'] >= '2023-01-01'].copy()
            
            if not df_recents.empty:
                vol_mensuel = df_recents.groupby('Mois')['Distance_km'].sum().reset_index()
                vol_mensuel['Distance (km)'] = vol_mensuel['Distance_km'].round(1)
                
                fig_vol = px.bar(vol_mensuel, x='Mois', y='Distance (km)', labels={'Distance (km)': 'Distance (km)'}, color_discrete_sequence=['#FC4C02'], text_auto='.1f')
                fig_vol.update_traces(textposition='outside')
                st.plotly_chart(fig_vol, use_container_width=True)
            else:
                st.info("Aucune activité trouvée depuis le 01/01/2023.")

        # --- TAB 2 : RECORDS & PREDICTIONS FUSIONNÉS ---
        with tab2:
            st.subheader("🏆 Comparatif Unique : Chronos Réels vs Prédictions de Course")
            st.markdown(f"Ce tableau regroupe tes meilleures performances détectées dans ton historique et tes objectifs théoriques calculés d'après ta VMA saisie de **{vma_manuelle} km/h**.")
            st.dataframe(df_unifié_records.set_index("Distance"), use_container_width=True)
            st.info("💡 **Note sur le réel :** L'algorithme calcule maintenant ton temps réel au prorata de tes runs les plus rapides. Si ton chrono réel Strava est supérieur aux prédictions, cela signifie que tu as le potentiel physique (VMA) pour aller chercher ces nouveaux temps en travaillant ton endurance !")

        # --- TAB 3 : ZONES D'ENTRAÎNEMENT ---
        with tab3:
            st.subheader("🎯 Zones d'Allures de Travail (Calculées sur VMA : " + str(vma_manuelle) + " km/h)")
            
            all_ef_max = 60 / (vma_manuelle * 0.60)
            all_ef_min = 60 / (vma_manuelle * 0.70)
            all_marathon_max = 60 / (vma_manuelle * 0.75)
            all_marathon_min = 60 / (vma_manuelle * 0.80)
            all_seuil_max = 60 / (vma_manuelle * 0.83)
            all_seuil_min = 60 / (vma_manuelle * 0.87)
            all_vma_max = 60 / (vma_manuelle * 0.95)
            all_vma_min = 60 / (vma_manuelle * 1.00)
            
            df_zones_allures = pd.DataFrame({
                "Zone d'Allure": ["🏃‍♂️ Endurance Fondamentale (Footing lent / Récup)", "🔋 Allure Rythme Marathon", "🎯 Seuil Lactique (Tempo / Fractionné Long)", "⚡ Séances VMA (Fractionné Court)"],
                "Pourcentage VMA": ["60% - 70%", "75% - 80%", "83% - 87%", "95% - 100%"],
                "Vitesse Cible": [f"{vma_manuelle*0.6:.1f} - {vma_manuelle*0.7:.1f} km/h", f"{vma_manuelle*0.75:.1f} - {vma_manuelle*0.8:.1f} km/h", f"{vma_manuelle*0.83:.1f} - {vma_manuelle*0.87:.1f} km/h", f"{vma_manuelle*0.95:.1f} - {vma_manuelle*1.0:.1f} km/h"],
                "Allure Cible (/km)": [f"{format_allure(all_ef_max)} à {format_allure(all_ef_min)}", f"{format_allure(all_marathon_max)} à {format_allure(all_marathon_min)}", f"{format_allure(all_seuil_max)} à {format_allure(all_seuil_min)}", f"{format_allure(all_vma_max)} à {format_allure(all_vma_min)}"]
            })
            st.dataframe(df_zones_allures, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("❤️ Zones Cardiaques Cibles (Calculées sur FC Max : " + str(fc_max_manuelle) + " bpm)")
            
            df_zones_cardio = pd.DataFrame({
                "Zone Cardiaque": ["Zone 1 - Récupération active / Échauffement", "Zone 2 - Endurance Fondamentale (Lipolyse)", "Zone 3 - Endurance Active / Rythme Marathon", "Zone 4 - Seuil Lactique / Résistance", "Zone 5 - Capacité Anaérobie / Seuil Rouge"],
                "Pourcentage FC Max": ["50% - 60%", "60% - 75%", "75% - 85%", "85% - 95%", "95% - 100%"],
                "Plage Cardiaque Cible": [f"{int(fc_max_manuelle*0.50)} - {int(fc_max_manuelle*0.60)} bpm", f"{int(fc_max_manuelle*0.60)} - {int(fc_max_manuelle*0.75)} bpm", f"{int(fc_max_manuelle*0.75)} - {int(fc_max_manuelle*0.85)} bpm", f"{int(fc_max_manuelle*0.85)} - {int(fc_max_manuelle*0.95)} bpm", f"{int(fc_max_manuelle*0.95)} - {fc_max_manuelle} bpm"]
            })
            st.dataframe(df_zones_cardio, use_container_width=True, hide_index=True)

        # --- TAB 4 : CARDIO ---
        with tab4:
            st.subheader("❤️ Indice d'Efficacité Cardiaque")
            st.markdown("Ce graphique analyse le coût cardiaque de tes entraînements. Plus la courbe descend, plus ton cœur devient fort et économe.")
            
            df_cardio = df[df['Fréquence cardiaque moyenne'].notna() & (df['Fréquence cardiaque moyenne'] > 0)].copy()
            if not df_cardio.empty:
                df_cardio['Indice_Cardio'] = df_cardio['Fréquence cardiaque moyenne'] / df_cardio['Vitesse_kmh']
                df_cardio['Indice_Cardio_Lissé'] = df_cardio['Indice_Cardio'].rolling(window=5, min_periods=1).mean()
                
                fig_cardio = px.line(df_cardio, x='Date_Clean', y='Indice_Cardio_Lissé', title="Indice de charge cardiaque (Plus bas = Plus endurant)", color_discrete_sequence=['#EF553B'])
                st.plotly_chart(fig_cardio, use_container_width=True)
            else:
                st.info("Aucune donnée de fréquence cardiaque moyenne n'a été détectée dans ton fichier.")

    except Exception as e:
        st.error(f"Une erreur est survenue lors de l'analyse : {e}")
else:
    st.info("👋 En attente de ton fichier 'activities.csv' dans le volet de gauche.")
