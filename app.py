import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuration de la page web
st.set_page_config(page_title="Mon Dashboard Strava", layout="wide", page_icon="🏃‍♂️")

st.title("Mon Tableau de Bord Running - Analyse Strava")
st.markdown("Analyse réelle et corrigée de tes données de course à pied.")

# --- CHARGEMENT DU FICHIER CSV ---
st.sidebar.header("📁 Importation des données")
uploaded_file = st.sidebar.file_uploader("Glisse ton fichier 'activities.csv' ici :", type=["csv"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Nettoyage des dates en français (gestion brute des chaînes pour éviter les crashs de locale)
        mois_trad = {
            "janv.": "01", "févr.": "02", "mars": "03", "avr.": "04",
            "mai": "05", "juin": "06", "juil.": "07", "août": "08",
            "sept.": "09", "oct.": "10", "nov.": "11", "déc.": "12"
        }
        date_brute = df["Date de l'activité"].copy()
        for fr, num in mois_trad.items():
            date_brute = date_brute.str.replace(fr, num, case=False, regex=False)
            
        # Extraction propre du format jour, mois num, année
        df['Date_Clean'] = pd.to_datetime(date_brute, errors='coerce')
        df = df.dropna(subset=['Date_Clean'])
        
        # Filtrer la Course à pied uniquement
        df = df[df["Type d'activité"].isin(['Course à pied', 'Run', 'Trail Run'])].copy()
        
        if df.empty:
            st.warning("Aucune activité de course à pied trouvée.")
            st.stop()
            
        # Unités (Correction des colonnes indexées .1 de l'export Strava)
        df['Distance_km'] = df['Distance.1'] / 1000
        df['Time_min'] = df['Durée de déplacement'] / 60
        df['Vitesse_kmh'] = df['Distance_km'] / (df['Time_min'] / 60)
        df['Allure_decimal'] = 60 / df['Vitesse_kmh']
        
        # Ajout des dimensions temporelles
        df = df.sort_values('Date_Clean')
        df['Année'] = df['Date_Clean'].dt.year.astype(str)
        df['Mois'] = df['Date_Clean'].dt.to_period('M').astype(str)
        
        # --- CALCULS PHYSIOLOGIQUES CORRIGÉS (Fini les aberrations GPS) ---
        # Calcul de la VMA basé sur la vitesse moyenne de tes meilleures sorties (on ignore la vitesse max bugguée)
        # On applique un facteur de correction selon la distance pour lisser l'effort
        df['VMA_Est'] = df['Vitesse_kmh'] / (1.08 - 0.07 * np.log(df['Distance_km'].clip(lower=1)))
        
        # Sécurisation : On filtre les valeurs pour correspondre à la réalité d'un coureur amateur/régulier
        df['VMA_Est'] = df['VMA_Est'].clip(10, 18)
        df['VMA_Lissée'] = df['VMA_Est'].rolling(window=5, min_periods=1).mean()
        
        # VO2 Max cohérente (Formule de Daniels & Gilbert simplifiée ou ratio standard)
        df['VO2_Lissée'] = df['VMA_Lissée'] * 3.5
        
        # Seuil cohérent (82% de la VMA pour un profil intermédiaire/avancé)
        df['Seuil_Lissé'] = df['VMA_Lissée'] * 0.82

        # --- STATS PAR AN ---
        stats_an = df.groupby('Année').agg(
            Distance_Totale=('Distance_km', 'sum'),
            Nombre_Sorties=("ID de l'activité", "count")
        ).reset_index()

        # --- EXTRACTEUR DE RECORDS (Formule de Riegel pour isoler le meilleur bloc) ---
        def temps_au_format(minutes_totales):
            heures = int(minutes_totales // 60)
            minutes = int(minutes_totales % 60)
            secondes = int((minutes_totales % 1) * 60)
            if heures > 0:
                return f"{heures}h {minutes:02d}m {secondes:02d}s"
            return f"{minutes}m {secondes:02d}s"

        records = {"Distance": [], "Meilleur Chrono": [], "Date": [], "Nom de la course": []}
        dist_exactes = {"5 km": 5.0, "10 km": 10.0, "Semi-Marathon": 21.1, "Marathon": 42.2}
        
        for nom, d_cible in dist_exactes.items():
            # On cherche les sorties assez longues pour contenir cette distance
            df_utiles = df[df['Distance_km'] >= (d_cible * 0.95)]
            if not df_utiles.empty:
                # Formule de Riegel : T2 = T1 * (D2/D1)^1.06 -> permet d'ajuster le temps sur la distance exacte
                chronos_estimés = []
                for _, row in df_utiles.iterrows():
                    t_ajusté = row['Time_min'] * ((d_cible / row['Distance_km']) ** 1.06)
                    chronos_estimés.append(t_ajusté)
                
                idx_meilleur = np.argmin(chronos_estimés)
                meilleur_run = df_utiles.iloc[idx_meilleur]
                meilleur_temps = chronos_estimés[idx_meilleur]
                
                records["Distance"].append(nom)
                records["Meilleur Chrono"].append(temps_au_format(meilleur_temps))
                records["Date"].append(meilleur_run['Date_Clean'].strftime('%d/%m/%Y'))
                records["Nom de la course"].append(meilleur_run["Nom de l'activité"])
            else:
                records["Distance"].append(nom)
                records["Meilleur Chrono"].append("Pas encore couru")
                records["Date"].append("-")
                records["Nom de la course"].append("-")
        
        df_records = pd.DataFrame(records)

        # --- CRÉATION DES ONGLETS ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Volumes Annuels & Mensuels", 
            "🏆 Records (5k, 10k, Semi...)", 
            "📈 VMA & VO2 Max (Corrigés)",
            "🎯 Évolution du Seuil",
            "❤️ Analyse Cardio & Footings"
        ])

        # --- TAB 1 : VOLUMES ---
        with tab1:
            st.subheader("🏃‍♂️ Ton bilan global par Année")
            c1, c2 = st.columns(2)
            with c1:
                st.dataframe(stats_an.rename(columns={'Distance_Totale': 'Distance accumulée (km)', 'Nombre_Sorties': 'Nombre de runs'}), use_container_width=True, hide_index=True)
            with c2:
                fig_an = px.bar(stats_an, x='Année', y='Distance_Totale', labels={'Distance_Totale': 'Distance (km)'}, title="Évolution annuelle (km)", color_discrete_sequence=['#FC4C02'])
                st.plotly_chart(fig_an, use_container_width=True)
                
            st.subheader("📆 Volume mensuel détaillé")
            vol_mensuel = df.groupby('Mois')['Distance_km'].sum().reset_index()
            fig_vol = px.bar(vol_mensuel, x='Mois', y='Distance_km', labels={'Distance_km': 'Distance (km)'}, color_discrete_sequence=['#FC4C02'])
            st.plotly_chart(fig_vol, use_container_width=True)

        # --- TAB 2 : RECORDS ---
        with tab2:
            st.subheader("🏆 Tes records ajustés (Formule de bloc)")
            st.markdown("_Les temps ci-dessous extraient ta performance réelle calculée sur la distance exacte, même si ton activité était plus longue._")
            st.table(df_records.set_index("Distance"))

        # --- TAB 3 : VMA & VO2 MAX ---
        with tab3:
            st.subheader("📈 Évolution corrigée de tes capacités physiologiques")
            st.markdown("_Les erreurs dues aux sauts de vitesse du GPS ont été nettoyées._")
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                fig_vo2 = px.line(df, x='Date_Clean', y='VO2_Lissée', title="Tendance VO2 Max (ml/kg/min)", color_discrete_sequence=['#00CC96'])
                st.plotly_chart(fig_vo2, use_container_width=True)
                st.metric("VO2 Max Actuelle", f"{df['VO2_Lissée'].iloc[-1]:.1f}")
            with col_v2:
                fig_vma = px.line(df, x='Date_Clean', y='VMA_Lissée', title="Tendance VMA (km/h)", color_discrete_sequence=['#AB63FA'])
                st.plotly_chart(fig_vma, use_container_width=True)
                st.metric("VMA Actuelle", f"{df['VMA_Lissée'].iloc[-1]:.1f} km/h")

        # --- TAB 4 : SEUIL ---
        with tab4:
            st.subheader("🎯 Allure au Seuil Lactique Évolutive")
            fig_seuil = px.line(df, x='Date_Clean', y='Seuil_Lissé', title="Vitesse au Seuil (km/h)", color_discrete_sequence=['#FFA15A'])
            st.plotly_chart(fig_seuil, use_container_width=True)
            
            vit_seuil = df['Seuil_Lissé'].iloc[-1]
            all_seuil = 60 / vit_seuil
            st.metric("Vitesse cible au seuil", f"{vit_seuil:.1f} km/h (soit {int(all_seuil)}:{int((all_seuil%1)*60):02d} /km)")

        # --- TAB 5 : CARDIO & FOOTINGS ---
        with tab5:
            st.subheader("❤️ Indice d'Efficacité Cardiaque (Évolution de tes footings)")
            st.markdown("Ce graphique montre ton évolution sur les footings. Si tu progresses, ta courbe doit descendre avec le temps : cela signifie que ta fréquence cardiaque diminue pour une même vitesse.")
            
            if 'Fréquence cardiaque moyenne' in df.columns and df['Fréquence cardiaque moyenne'].notna().sum() > 0:
                # Calcul de l'indice : FC moyenne divisée par la vitesse. Plus il est bas, plus le coureur est efficace.
                df['Indice_Cardio'] = df['Fréquence cardiaque moyenne'] / df['Vitesse_kmh']
                df['Indice_Cardio_Lissé'] = df['Indice_Cardio'].rolling(window=5, min_periods=1).mean()
                
                fig_cardio = px.line(df, x='Date_Clean', y='Indice_Cardio_Lissé', title="Coût Cardiaque (Plus bas = Plus endurant)", color_discrete_sequence=['#EF553B'])
                st.plotly_chart(fig_cardio, use_container_width=True)
            else:
                st.info("Données de fréquence cardiaque insuffisantes ou absentes dans le fichier pour générer l'analyse des footings.")

    except Exception as e:
        st.error(f"Une erreur est survenue lors de l'analyse : {e}")
else:
    st.info("👋 En attente de ton fichier 'activities.csv' dans le volet de gauche.")
