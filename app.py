import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuration de la page web
st.set_page_config(page_title="Mon Dashboard Strava", layout="wide", page_icon="🏃‍♂️")

st.title("🏃‍♂️ Mon Tableau de Bord Running Personnalisé")
st.markdown("Analyse croisée entre tes performances réelles Strava et ton profil physiologique configuré manuellement.")

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

# Convertisseur allure décimale -> chaîne (ex: 4.5 -> 4:30 /km)
def format_allure(allure_dec):
    if np.isnan(allure_dec) or np.isinf(allure_dec):
        return "--:--"
    minutes = int(allure_dec)
    secondes = int((allure_dec % 1) * 60)
    return f"{minutes}:{secondes:02d} /km"

# Convertisseur minutes -> format horloge (ex: 125.5 -> 2h 05m 30s)
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
        
        # Variables de temps
        df = df.sort_values('Date_Clean')
        df['Année'] = df['Date_Clean'].dt.year.astype(str)
        df['Mois'] = df['Date_Clean'].dt.to_period('M').astype(str)

        # --- STATS PAR AN ---
        stats_an = df.groupby('Année').agg(
            Distance_Totale=('Distance_km', 'sum'),
            Nombre_Sorties=("ID de l'activité", "count"),
            Temps_Total_Min=('Time_min', 'sum')
        ).reset_index()
        
        stats_an['Allure_Dec_An'] = stats_an['Temps_Total_Min'] / stats_an['Distance_Totale']
        stats_an['Allure moyenne'] = stats_an['Allure_Dec_An'].apply(format_allure)
        stats_an_affichage = stats_an[['Année', 'Distance_Totale', 'Nombre_Sorties', 'Allure moyenne']].copy()
        stats_an_affichage = stats_an_affichage.sort_values('Année', ascending=False)
        stats_an_affichage = stats_an_affichage.rename(columns={'Distance_Totale': 'Distance (km)', 'Nombre_Sorties': 'Nombre de runs'})

        # --- RECHERCHE DES CHRONOS RÉELS ---
        records_reels = {"Distance": [], "Meilleur Chrono Réel": [], "Date": [], "Nom de l'activité Strava": []}
        dist_cibles = {"5 km": 5.0, "10 km": 10.0, "Semi-Marathon": 21.1, "Marathon": 42.195}
        
        for nom, d_cible in dist_cibles.items():
            # On cherche les activités dont la distance globale est proche de la cible (+ ou - 8%)
            tol_inf = d_cible * 0.92
            tol_sup = d_cible * 1.08
            df_matching = df[(df['Distance_km'] >= tol_inf) & (df['Distance_km'] <= tol_sup)]
            
            if not df_matching.empty:
                # Le meilleur chrono réel est l'activité la plus rapide sur cette tranche
                idx_meilleur = df_matching['Time_min'].idxmin()
                run_reel = df_matching.loc[idx_meilleur]
                
                records_reels["Distance"].append(nom)
                records_reels["Meilleur Chrono Réel"].append(mins_to_clock(run_reel['Time_min']))
                records_reels["Date"].append(run_reel['Date_Clean'].strftime('%d/%m/%Y'))
                records_reels["Nom de l'activité Strava"].append(run_reel["Nom de l'activité"])
            else:
                records_reels["Distance"].append(nom)
                records_reels["Meilleur Chrono Réel"].append("Aucune activité de cette distance")
                records_reels["Date"].append("-")
                records_reels["Nom de l'activité Strava"].append("-")
                
        df_records_reels = pd.DataFrame(records_reels)

        # --- CRÉATION DES ONGLETS ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Volumes Annuels & Mensuels", 
            "⏱️ Mes Chronos Réels Strava",
            "🔮 Prédictions de Course (Fourchette)", 
            "🎯 Mes Zones d'Entraînement Target",
            "❤️ Analyse Cardio & Footings"
        ])

        # --- TAB 1 : VOLUMES ---
        with tab1:
            st.subheader("🏃‍♂️ Statistiques globales historiques (Tout temps)")
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
                fig_an = px.bar(stats_an, x='Année', y='Distance_Totale', labels={'Distance_Totale': 'Distance (km)'}, title="Volume annuel (km)", color_discrete_sequence=['#FC4C02'])
                st.plotly_chart(fig_an, use_container_width=True)
                
            st.subheader("📆 Progression mensuelle")
            vol_mensuel = df.groupby('Mois')['Distance_km'].sum().reset_index()
            fig_vol = px.bar(vol_mensuel, x='Mois', y='Distance_km', labels={'Distance_km': 'Distance (km)'}, color_discrete_sequence=['#FC4C02'])
            st.plotly_chart(fig_vol, use_container_width=True)

        # --- TAB 2 : CHRONOS RÉELS ---
        with tab2:
            st.subheader("⏱️ Tes meilleures performances enregistrées sur Strava")
            st.markdown("_Ce tableau extrait la durée totale brute de tes sorties dont la distance totale correspond à ces formats de course (+/- 8%)._")
            st.table(df_records_reels.set_index("Distance"))

        # --- TAB 3 : PRÉDICTIONS EN FOURCHETTE (Modèle de Riegel adapté) ---
        with tab3:
            st.subheader("🔮 Prédictions théoriques basées sur ta VMA de " + str(vma_manuelle) + " km/h")
            st.markdown("Voici une estimation de tes chronos possibles selon ton niveau d'endurance (Indice de Riegel entre -0.06 pour le profil optimiste et -0.09 pour le profil standard/pessimiste) :")
            
            predictions = {"Distance": [], "Fourchette Haute (Prudent)": [], "Fourchette Basse (Optimiste)": []}
            
            # Calculs basés sur la VMA rentrée
            # On pose le temps de référence de base sur un 10k théorique (à 85% ou 88% VMA)
            t_ref_base_min = (10.0 / (vma_manuelle * 0.86)) * 60
            
            for nom, d_cible in dist_cibles.items():
                # Riegel prudent (ex: profil plutôt typé vitesse que marathon)
                t_prudent = t_ref_base_min * ((d_cible / 10.0) ** 1.09)
                # Riegel optimiste (ex: profil très endurant / jour de grâce)
                t_optimiste = t_ref_base_min * ((d_cible / 10.0) ** 1.06)
                
                # Ajustement direct spécifique au 5k pour qu'il colle à ton niveau max VMA (~93-95% VMA)
                if nom == "5 km":
                    t_prudent = (5.0 / (vma_manuelle * 0.92)) * 60
                    t_optimiste = (5.0 / (vma_manuelle * 0.95)) * 60
                
                predictions["Distance"].append(nom)
                predictions["Fourchette Haute (Prudent)"].append(mins_to_clock(t_prudent))
                predictions["Fourchette Basse (Optimiste)"].append(mins_to_clock(t_optimiste))
                
            df_pred = pd.DataFrame(predictions)
            st.table(df_pred.set_index("Distance"))
            st.caption("💡 Si tes chronos réels (onglet précédent) sont plus lents que la fourchette basse, cela montre que tu as une grosse marge de progression en travaillant ton endurance spécifique sur cette distance !")

        # --- TAB 4 : ZONES D'ENTRAÎNEMENT CIBLES ---
        with tab4:
            st.subheader("🎯 Tes Zones d'Allures de Travail (Basées sur VMA)")
            
            # Calcul des allures cibles (en min/km)
            all_ef_max = 60 / (vma_manuelle * 0.60)
            all_ef_min = 60 / (vma_manuelle * 0.70)
            
            all_marathon_max = 60 / (vma_manuelle * 0.75)
            all_marathon_min = 60 / (vma_manuelle * 0.80)
            
            all_seuil_max = 60 / (vma_manuelle * 0.83)
            all_seuil_min = 60 / (vma_manuelle * 0.87)
            
            all_vma_max = 60 / (vma_manuelle * 0.95)
            all_vma_min = 60 / (vma_manuelle * 1.00)
            
            df_zones_allures = pd.DataFrame({
                "Zone d'Allure": ["🏃‍♂️ Endurance Fondamentale (Footing / Récup)", "🔋 Allure Rythme Marathon", "🎯 Seuil Lactique (Tempo / Fractionné Long)", "⚡ Séances VMA (Fractionné Court)"],
                "Pourcentage VMA": ["60% - 70%", "75% - 80%", "83% - 87%", "95% - 100%"],
                "Vitesse Cible (km/h)": [f"{vma_manuelle*0.6:.1f} - {vma_manuelle*0.7:.1f} km/h", f"{vma_manuelle*0.75:.1f} - {vma_manuelle*0.8:.1f} km/h", f"{vma_manuelle*0.83:.1f} - {vma_manuelle*0.87:.1f} km/h", f"{vma_manuelle*0.95:.1f} - {vma_manuelle*1.0:.1f} km/h"],
                "Allure Cible (/km)": [f"{format_allure(all_ef_max)} à {format_allure(all_ef_min)}", f"{format_allure(all_marathon_max)} à {format_allure(all_marathon_min)}", f"{format_allure(all_seuil_max)} à {format_allure(all_seuil_min)}", f"{format_allure(all_vma_max)} à {format_allure(all_vma_min)}"]
            })
            st.dataframe(df_zones_allures, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            st.subheader("❤️ Tes Zones Cardiaques Cibles (Basées sur FC Max : " + str(fc_max_manuelle) + " bpm)")
            st.markdown("_Zones classiques selon l'échelle d'intensité (méthode de la FC Max) :_")
            
            df_zones_cardio = pd.DataFrame({
                "Zone Cardiaque": ["Zone 1 - Récupération active / Footing très lent", "Zone 2 - Endurance Fondamentale (Lipolyse)", "Zone 3 - Endurance Active / Rythme Marathon", "Zone 4 - Seuil Lactique / Résistance", "Zone 5 - Capacité Anaérobie / VMA"],
                "Pourcentage FC Max": ["50% - 60%", "60% - 75%", "75% - 85%", "85% - 95%", "95% - 100%"],
                "Plage Cardiaque Cible": [f"{int(fc_max_manuelle*0.50)} - {int(fc_max_manuelle*0.60)} bpm", f"{int(fc_max_manuelle*0.60)} - {int(fc_max_manuelle*0.75)} bpm", f"{int(fc_max_manuelle*0.75)} - {int(fc_max_manuelle*0.85)} bpm", f"{int(fc_max_manuelle*0.85)} - {int(fc_max_manuelle*0.95)} bpm", f"{int(fc_max_manuelle*0.95)} - {fc_max_manuelle} bpm"]
            })
            st.dataframe(df_zones_cardio, use_container_width=True, hide_index=True)

        # --- TAB 5 : CARDIO & FOOTINGS ---
        with tab5:
            st.subheader("❤️ Indice d'Efficacité Cardiaque (Évolution de tes footings)")
            st.markdown("Ce graphique analyse le coût cardiaque de tes entraînements. Plus la courbe descend au fil des mois, plus ton cœur devient fort et économe (il bat moins vite pour courir à la même vitesse).")
            
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
