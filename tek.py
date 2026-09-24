import base64
from pathlib import Path
import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import date, datetime, timedelta
import calendar
import html
import hashlib
import mimetypes



# --- CALENDRIER DES JOURS FÉRIÉS TOGO ---
def easter_sunday(year):
    """Calcul de la date de Pâques (algorithme de Meeus/Jones/Butcher)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def togo_holidays(year):
    """Jours fériés nationaux du Togo connus pour l'année sélectionnée.
    Les dates religieuses variables sont renseignées explicitement pour 2026.
    Pour les autres années, les fêtes chrétiennes mobiles sont calculées.
    """
    fixed = {
        date(year, 1, 1): "Jour de l'An",
        date(year, 4, 27): "Fête de l'Indépendance",
        date(year, 5, 1): "Fête du Travail",
        date(year, 8, 15): "Assomption",
        date(year, 11, 1): "Toussaint",
        date(year, 12, 25): "Noël",
    }
    easter = easter_sunday(year)
    fixed[easter + pd.Timedelta(days=1).to_pytimedelta()] = "Lundi de Pâques"
    fixed[easter + pd.Timedelta(days=39).to_pytimedelta()] = "Ascension"
    fixed[easter + pd.Timedelta(days=50).to_pytimedelta()] = "Lundi de Pentecôte"

    # Dates officielles/usuelles 2026 au Togo : Korité 20/03, Tabaski 27/05,
    # Journée des Martyrs 21/06. Les fêtes lunaires peuvent varier selon
    # l'annonce officielle.
    if year == 2026:
        fixed.update({
            date(2026, 3, 20): "Korité",
            date(2026, 5, 27): "Tabaski",
            date(2026, 6, 21): "Journée des Martyrs",
        })
    return fixed


def planning_day_style(year, month, days):
    """Retourne le style visuel des colonnes du planning : weekend/férié."""
    holidays = togo_holidays(year)
    styles = {}
    for d in days:
        dt = date(year, month, int(d))
        if dt in holidays:
            styles[d] = ("background-color: #FFC7CE; color: #8B1E2D; font-weight: 900; border: 2px solid #E88D98;", f"🎉 {d}")
        elif dt.weekday() >= 5:
            styles[d] = ("background-color: #C8EEFF; color: #123A63; font-weight: 900; border: 1px solid #7FB8D5;", f"🟦 {d}")
        else:
            styles[d] = ("", d)
    return styles


def style_monthly_planning(df, year, month):
    """Applique les couleurs de la maquette aux cellules du planning."""
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    holidays = togo_holidays(year)
    role_colors = {
        'PJ': '#FFD84D',       # jaune
        'PN': '#F6A623',       # orange
        'A': '#8BE28B',        # vert
        'C': '#E5E7EB',        # gris
        'Repos': '#C8EEFF',    # bleu clair
        'SN': '#F1F5F9',       # gris très clair
    }
    for col in df.columns:
        if col in ('NOM', 'PRÉNOMS', 'FONCTION'):
            styles[col] = 'background-color:#EAF4FB; font-weight:700; color:#12396F;'
            continue
        try:
            dt = date(year, month, int(col))
        except Exception:
            continue
        for idx in df.index:
            val = str(df.at[idx, col])
            bg = role_colors.get(val)
            if bg:
                styles.at[idx, col] = f'background-color:{bg}; color:#111827; font-weight:800; text-align:center;'
            else:
                styles.at[idx, col] = 'background-color:#FFFFFF; color:#111827; text-align:center;'
            if dt in holidays:
                styles.at[idx, col] += 'border-left:2px solid #E56A76; border-right:2px solid #E56A76;'
            elif dt.weekday() >= 5 and not bg:
                styles.at[idx, col] = 'background-color:#C8EEFF; color:#123A63; font-weight:800; text-align:center;'
    return styles


def render_colorized_planning_html(df, year, month, visible_days, title="Planning"):
    """Affiche une grille HTML réellement colorée, indépendante des limites de Styler/DataEditor."""
    if df is None or df.empty:
        st.info("Aucune ligne à afficher.")
        return
    holidays = togo_holidays(year)
    role_colors = {
        'PJ': '#FFD84D', 'PN': '#F6A623', 'A': '#8BE28B',
        'C': '#E5E7EB', 'Repos': '#C8EEFF', 'SN': '#F1F5F9'
    }
    day_names = ['Lun','Mar','Mer','Jeu','Ven','Sam','Dim']
    html = ['<div style="overflow:auto;border:2px solid #1D78B5;border-radius:12px;background:#fff;box-shadow:0 5px 18px rgba(0,0,0,.12);">']
    html.append('<table style="border-collapse:collapse;min-width:1200px;width:100%;font-size:11px;">')
    html.append('<thead><tr>')
    for h,w in [('MATRICULE','120px'),('NOM','150px'),('PRÉNOMS','190px'),('FONCTION','260px')]:
        html.append(f'<th style="position:sticky;top:0;background:#032B57;color:white;border:1px solid #7AA8C4;padding:7px;text-align:left;min-width:{w};z-index:2;">{h}</th>')
    for d in visible_days:
        dt = date(year, month, int(d))
        bg = '#FFC7CE' if dt in holidays else ('#C8EEFF' if dt.weekday() >= 5 else '#006AA6')
        fg = '#8B1E2D' if dt in holidays else 'white'
        label = f'🎉 {dt.day:02d}' if dt in holidays else (f'🟦 {dt.day:02d}' if dt.weekday() >= 5 else f'{day_names[dt.weekday()]} {dt.day:02d}')
        html.append(f'<th style="position:sticky;top:0;background:{bg};color:{fg};border:1px solid #7AA8C4;padding:6px;text-align:center;min-width:52px;z-index:2;">{label}</th>')
    html.append('</tr></thead><tbody>')
    for _, row in df.iterrows():
        html.append('<tr>')
        for col in ['MATRICULE','NOM','PRÉNOMS','FONCTION']:
            html.append(f'<td style="background:#EAF4FB;border:1px solid #B7CFDE;padding:6px;font-weight:700;color:#12396F;">{str(row.get(col,''))}</td>')
        for d in visible_days:
            val = str(row.get(d,''))
            dt = date(year, month, int(d))
            bg = role_colors.get(val, '#FFFFFF')
            fg = '#8B1E2D' if dt in holidays and val not in role_colors else '#111827'
            border = '2px solid #E56A76' if dt in holidays else '1px solid #A7C6D9'
            html.append(f'<td style="background:{bg};color:{fg};border:{border};padding:6px;text-align:center;font-weight:900;min-width:52px;">{val}</td>')
        html.append('</tr>')
    html.append('</tbody></table></div>')
    st.markdown(''.join(html), unsafe_allow_html=True)


# --- CONFIGURATION PAGE ---
st.set_page_config(
    page_title='Yas DFO-SRTM – Hub Opérationnel Maritime', 
    page_icon='📡', 
    layout='wide',
    initial_sidebar_state='expanded'
)

# --- LOGO : recherche robuste (script + ancien chemin Windows) ---
SCRIPT_DIR = Path(__file__).resolve().parent
LOGO_CANDIDATES = [
    SCRIPT_DIR / "MARITIME_JAUNE.png",
    Path(r"C:\Users\TGABIAM\Downloads\daily report mar\MARITIME_JAUNE.png"),
    Path(r"C:\Users\TGABIAM\Downloads\MARITIME_JAUNE.png"),
]
LOGO_PATH = next((p for p in LOGO_CANDIDATES if p.exists() and p.is_file()), None)
LOGO_SRC = ""
if LOGO_PATH is not None:
    try:
        LOGO_SRC = "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")
    except Exception:
        LOGO_SRC = ""

def render_logo(width=180):
    """Affiche le logo de façon fiable dans Streamlit."""
    if LOGO_PATH is not None:
        try:
            st.image(str(LOGO_PATH), width=width)
            return True
        except Exception:
            pass
    return False

# --- CHARTE GRAPHIQUE COMPLÈTE YAS EN FOND BLEU MARINE ---
st.markdown("""
    <style>
    /* ===== MENU LATERAL YAS : CONTROLE MANUEL ===== */
    /* Le bouton natif Streamlit est remplacé par notre bouton YAS. */
    button[data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    [data-testid="collapsedControl"] {
        display: none !important;
    }

    section[data-testid="stSidebar"] button[aria-label*="sidebar" i],
    section[data-testid="stSidebar"] button[aria-label*="Sidebar" i] {
        display: none !important;
    }

    /* Bouton flottant pour faire revenir le menu */
    .yas-menu-toggle {
        position: fixed;
        top: 18px;
        left: 10px;
        z-index: 999999;
        background: #FFD21F;
        color: #002B5B;
        border: 2px solid #002B5B;
        border-radius: 10px;
        padding: 8px 12px;
        font-size: 18px;
        font-weight: 800;
        cursor: pointer;
        box-shadow: 0 3px 12px rgba(0,0,0,.25);
    }

    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Montserrat', system-ui, -apple-system, sans-serif;
    }

    /* FOND GÉNÉRAL DE L'APPLICATION EN BLEU MARINE PROFOND */
    .stApp {
        background: linear-gradient(180deg, #0A1128 0%, #0F1E36 100%);
        color: #F8FAFC;
    }

    /* Masquer le header et footer Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Bannière Header - Fond Jaune Yas contrasté */
    .header-banner {
        background: linear-gradient(135deg, #FFCC00 0%, #FFD633 60%, #52B4E9 100%);
        padding: 20px 32px;
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
        margin-bottom: 25px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 4px solid #0A1128;
    }
    
    .header-title-box {
        display: flex;
        align-items: center;
        gap: 20px;
    }

    .header-title {
        color: #0A1128 !important;
        font-size: 26px;
        font-weight: 900;
        letter-spacing: -0.5px;
        margin: 0;
        text-transform: uppercase;
    }

    .header-subtitle {
        color: #162D5A;
        font-size: 13px;
        margin-top: 4px;
        font-weight: 700;
    }

    .role-badge {
        background: #0A1128;
        color: #FFCC00;
        padding: 10px 20px;
        border-radius: 30px;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 0.5px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }


    /* ===== MENU LATÉRAL YAS — DESIGN V3 ===== */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #06152E 0%, #0B2344 52%, #0A1730 100%);
        border-right: 1px solid rgba(255, 204, 0, 0.22);
        box-shadow: 8px 0 28px rgba(0, 0, 0, 0.28);
    }

    section[data-testid="stSidebar"] > div {
        padding: 1rem 0.85rem 1.25rem 0.85rem;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 0.65rem;
    }

    .sidebar-brand {
        background: linear-gradient(135deg, #FFCC00 0%, #FFD84D 72%, #F4B400 100%);
        color: #07162E;
        border-radius: 18px;
        padding: 16px 14px;
        margin: 4px 0 18px 0;
        box-shadow: 0 8px 22px rgba(0,0,0,.25);
        text-align: center;
    }

    .sidebar-brand .brand-icon {
        font-size: 27px;
        line-height: 1;
        margin-bottom: 7px;
    }

    .sidebar-brand .brand-title {
        font-size: 15px;
        font-weight: 900;
        letter-spacing: .7px;
        text-transform: uppercase;
    }

    .sidebar-brand .brand-subtitle {
        margin-top: 4px;
        font-size: 10px;
        font-weight: 800;
        opacity: .78;
        letter-spacing: .35px;
    }

    .sidebar-section-label {
        color: #9FC3DF;
        font-size: 10px;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 1.1px;
        margin: 0 4px 8px 4px;
    }

    /* Radio = boutons de navigation */
    section[data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 7px;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        background: rgba(255,255,255,.055);
        border: 1px solid rgba(255,255,255,.075);
        border-radius: 13px;
        padding: 11px 12px !important;
        min-height: 46px;
        transition: all .18s ease;
        cursor: pointer;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background: rgba(255,204,0,.12);
        border-color: rgba(255,204,0,.45);
        transform: translateX(2px);
    }

    /* ===== MENU ACTIF TURQUOISE + BARRE LUMINEUSE ===== */
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        position: relative;
        overflow: visible;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"] {
        background: linear-gradient(90deg, rgba(0, 229, 212, .20) 0%, rgba(0, 229, 212, .10) 55%, rgba(0, 229, 212, .04) 100%);
        border-color: rgba(0, 229, 212, .55);
        box-shadow:
            0 0 0 1px rgba(0, 229, 212, .10),
            0 7px 22px rgba(0, 229, 212, .16),
            inset 0 0 18px rgba(0, 229, 212, .06);
        transform: translateX(3px);
    }

    /* Petite barre turquoise lumineuse sur le côté gauche */
    section[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"]::before {
        content: "";
        position: absolute;
        left: -2px;
        top: 8px;
        bottom: 8px;
        width: 4px;
        border-radius: 999px;
        background: #00E5D4;
        box-shadow:
            0 0 5px #00E5D4,
            0 0 12px rgba(0, 229, 212, .90),
            0 0 22px rgba(0, 229, 212, .65);
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"] p {
        color: #00E5D4 !important;
        font-weight: 900 !important;
        text-shadow: 0 0 10px rgba(0, 229, 212, .28);
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"]:hover {
        background: linear-gradient(90deg, rgba(0, 229, 212, .25), rgba(0, 229, 212, .08));
        border-color: #00E5D4;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] > label p {
        color: #F3F7FB !important;
        font-size: 12px !important;
        font-weight: 750 !important;
        margin: 0 !important;
    }

    section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child {
        display: none;
    }

    .sidebar-user-card {
        margin-top: 18px;
        padding: 12px;
        border-radius: 13px;
        background: rgba(255,255,255,.045);
        border: 1px solid rgba(255,255,255,.07);
        color: #DCEAF5;
        font-size: 11px;
    }

    .sidebar-user-card strong {
        color: #FFCC00;
    }

    .zone-space-card {
        position: relative;
        margin: 14px 0 8px 0;
        padding: 13px;
        border-radius: 16px;
        background: linear-gradient(145deg, rgba(7,42,72,.98), rgba(3,28,50,.98));
        border: 1px solid rgba(0,229,212,.38);
        box-shadow: 0 10px 28px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.06);
        overflow: hidden;
    }
    .zone-space-card::before {
        content: ""; position: absolute; left: 0; top: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, #00E5D4, #49A9E8, #FFD24A);
    }
    .zone-space-head { display: flex; align-items: center; gap: 10px; margin-bottom: 11px; }
    .zone-space-icon {
        width: 34px; height: 34px; border-radius: 11px; display:flex; align-items:center; justify-content:center;
        background: rgba(0,229,212,.13); border: 1px solid rgba(0,229,212,.30); font-size: 17px;
    }
    .zone-space-title { color:#F3FCFF; font-size:12px; font-weight:900; letter-spacing:.09em; }
    .zone-space-subtitle { color:#9EB7C5; font-size:10px; margin-top:3px; }
    .zone-space-status {
        display:flex; justify-content:space-between; align-items:center; gap:8px;
        padding:7px 9px; border-radius:9px; margin-bottom:10px;
        background:rgba(0,229,212,.07); border:1px solid rgba(0,229,212,.20);
        color:#AFC6D2; font-size:9px; font-weight:800; letter-spacing:.04em;
    }
    .zone-space-status strong { color:#00E5D4; font-size:10px; }
    .zone-dashboard-label {
        color:#EAFBFF; font-size:9px; font-weight:900; letter-spacing:.10em; margin:3px 1px 7px;
    }
    .zone-dashboard-grid { display:grid; grid-template-columns:1fr 1fr; gap:7px; }
    .zone-kpi {
        min-width:0; padding:8px 7px; border-radius:10px; text-align:center;
        background:rgba(255,255,255,.045); border:1px solid rgba(255,255,255,.08);
    }
    .zone-kpi span { display:block; font-size:13px; line-height:1; margin-bottom:3px; }
    .zone-kpi b { display:block; color:#FFFFFF; font-size:16px; line-height:1.05; }
    .zone-kpi small { display:block; color:#8FA9B8; font-size:9px; margin-top:2px; }
    .zone-space-footer {
        margin-top:9px; padding-top:8px; border-top:1px solid rgba(255,255,255,.08);
        color:#819BAA; font-size:8px; text-align:center;
    }
    .zone-space-footer strong { color:#BFD2DB; }


    /* Boutons de la sidebar */
    section[data-testid="stSidebar"] button {
        border-radius: 12px !important;
        font-weight: 800 !important;
    }

    /* Titres de Sections */
    .section-title {
        font-size: 16px;
        font-weight: 800;
        color: #FFCC00;
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 3px solid #FFCC00;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Labels Streamlit en Blanc */
    label {
        color: #E2E8F0 !important;
        font-weight: 600 !important;
    }

    /* Cartes KPI sur fond sombre */
    div[data-testid="stMetric"] {
        background: #132240;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-left: 6px solid #FFCC00;
        padding: 18px 22px;
        border-radius: 16px;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
        transition: all 0.25s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        border-left-color: #52B4E9;
        box-shadow: 0 12px 25px rgba(82, 180, 233, 0.2);
    }

    div[data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-weight: 700 !important;
        font-size: 11px !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    div[data-testid="stMetricValue"] {
        color: #FFCC00 !important;
        font-weight: 900 !important;
        font-size: 28px !important;
    }

    /* Style des Onglets (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        padding-bottom: 10px;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: #132240;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 12px;
        padding: 10px 20px;
        color: #CBD5E1;
        font-weight: 700;
        font-size: 13px;
        transition: all 0.2s ease;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background-color: #1C315B;
        color: #FFCC00;
    }

    .stTabs [aria-selected="true"] {
        background-color: #FFCC00 !important;
        color: #0A1128 !important;
        border-color: #FFCC00 !important;
        font-weight: 800 !important;
        box-shadow: 0 4px 15px rgba(255, 204, 0, 0.3);
    }

    /* Boîte de Connexion Yas */
    .login-wrapper {
        background: #132240;
        border-radius: 24px;
        padding: 40px;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
        border: 2px solid #FFCC00;
        max-width: 440px;
        margin: 40px auto 20px auto;
        text-align: center;
    }

    /* Boutons de Validation Yas */
    .stButton > button {
        border-radius: 12px !important;
        font-weight: 800 !important;
        padding: 12px 24px !important;
        transition: all 0.2s ease-in-out !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #FFCC00 0%, #FFAA00 100%) !important;
        color: #0A1128 !important;
        border: none !important;
        box-shadow: 0 4px 14px rgba(255, 204, 0, 0.3) !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #FFD633 0%, #FFCC00 100%) !important;
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(255, 204, 0, 0.5) !important;
    }


    /* ===== BOUTON DECONNEXION : TRES VISIBLE ===== */
    .st-key-logout_container button {
        background: linear-gradient(135deg, #FF4D4F 0%, #D9363E 100%) !important;
        color: #FFFFFF !important;
        border: 2px solid rgba(255,255,255,.28) !important;
        border-radius: 12px !important;
        min-height: 46px !important;
        font-size: 13px !important;
        font-weight: 900 !important;
        letter-spacing: .6px !important;
        box-shadow: 0 5px 16px rgba(217,54,62,.38) !important;
        transition: all .18s ease !important;
    }
    .st-key-logout_container button:hover {
        background: linear-gradient(135deg, #FF6B6D 0%, #E23B44 100%) !important;
        border-color: #FFFFFF !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 22px rgba(255,77,79,.52) !important;
    }
    .st-key-logout_container button:active {
        transform: translateY(0) !important;
    }

    /* Légende */
    .legend-box {
        background: #132240;
        border: 1px solid #FFCC00;
        padding: 12px 18px;
        border-radius: 12px;
        font-size: 13px;
        color: #E2E8F0;
        margin-bottom: 15px;
    }

    /* Adaptation des zones de texte */
    .stTextArea textarea {
        background-color: #132240 !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 10px !important;
    }

    /* ============================================================
       CHARTE COULEURS DU PLANNING — cohérente avec la maquette
       ============================================================ */
    .planning-card {
        background: #F7FBFF;
        border: 2px solid #1D78B5;
        border-radius: 16px;
        padding: 14px;
        box-shadow: 0 10px 28px rgba(0,0,0,.20);
        margin: 8px 0 18px 0;
    }
    .planning-header {
        background: linear-gradient(90deg, #032B57 0%, #006AA6 70%, #008BD2 100%);
        color: #FFFFFF;
        border-radius: 12px;
        padding: 13px 18px;
        font-size: 22px;
        font-weight: 900;
        letter-spacing: .2px;
        margin-bottom: 12px;
    }
    .planning-legend {
        display:flex; flex-wrap:wrap; gap:8px; align-items:center;
        background:#EAF4FB; border:1px solid #A7C6D9;
        border-radius:10px; padding:8px 10px; margin:8px 0 12px;
        color:#12396F; font-size:12px; font-weight:800;
    }
    .planning-chip {
        display:inline-flex; align-items:center; gap:5px;
        padding:5px 9px; border-radius:6px; border:1px solid rgba(0,0,0,.12);
        font-weight:900; color:#111827;
    }
    .planning-chip-pj { background:#FFD84D; }
    .planning-chip-pn { background:#F6A623; }
    .planning-chip-a { background:#8BE28B; }
    .planning-chip-we { background:#C8EEFF; color:#123A63; }
    .planning-chip-holiday { background:#FFC7CE; color:#8B1E2D; }

    /* Contrôles de filtre */
    div[data-testid="stSelectbox"] > div,
    div[data-testid="stMultiSelect"] > div,
    div[data-testid="stNumberInput"] > div {
        border-radius:10px !important;
    }
    div[data-baseweb="select"] > div {
        background:#FFFFFF !important;
        border-color:#7AA8C4 !important;
        color:#12396F !important;
    }
    div[data-baseweb="select"] input { color:#12396F !important; }

    /* Tableau / éditeur Streamlit : bordures et en-têtes */
    div[data-testid="stDataEditor"] {
        border:2px solid #1D78B5 !important;
        border-radius:12px !important;
        overflow:hidden !important;
        background:#FFFFFF !important;
        box-shadow:0 5px 18px rgba(0,0,0,.12);
    }
    div[data-testid="stDataEditor"] [role="columnheader"] {
        background:#032B57 !important;
        color:#FFFFFF !important;
        font-weight:900 !important;
    }
    div[data-testid="stDataFrame"] {
        border-radius:12px !important;
        overflow:hidden !important;
    }

    /* Cartes d'information */
    div[data-testid="stAlert"] {
        border-radius:10px !important;
        border-left-width:5px !important;
    }

    /* Boutons de téléchargement */
    .stDownloadButton > button {
        border-radius:10px !important;
        border:1px solid #008BD2 !important;
        background:#EAF4FB !important;
        color:#032B57 !important;
        font-weight:800 !important;
    }
    .stDownloadButton > button:hover {
        background:#C8EEFF !important;
        border-color:#006AA6 !important;
    }



    /* --- AMÉLIORATIONS UX : même charte, interface plus lisible --- */
    .quick-help {
        background: rgba(255,255,255,.08);
        border: 1px solid rgba(255,204,0,.30);
        border-radius: 12px;
        padding: 10px 14px;
        margin: 8px 0 18px 0;
        color: #E2E8F0;
        font-size: 12px;
    }
    .page-intro {
        background: rgba(255,255,255,.06);
        border-left: 4px solid #FFCC00;
        border-radius: 10px;
        padding: 12px 16px;
        margin: 0 0 18px 0;
    }
    .page-intro-title {
        color: #FFCC00;
        font-size: 15px;
        font-weight: 900;
        margin-bottom: 3px;
    }
    .page-intro-text {
        color: #CBD5E1;
        font-size: 12px;
        line-height: 1.5;
    }
    .welcome-strip {
        display:flex; align-items:center; gap:12px;
        background: linear-gradient(135deg, rgba(0,229,212,.13), rgba(255,204,0,.08));
        border:1px solid rgba(0,229,212,.32);
        border-radius:14px; padding:11px 14px; margin:0 0 18px 0;
        box-shadow:0 6px 20px rgba(0,0,0,.10);
    }
    .welcome-strip-icon {
        width:36px; height:36px; border-radius:10px; display:flex; align-items:center; justify-content:center;
        background:rgba(0,229,212,.16); color:#00E5D4; font-size:22px; font-weight:900; flex:0 0 auto;
    }
    .welcome-strip-main { flex:1; min-width:0; }
    .welcome-strip-title { color:#EAFBFF; font-size:12px; font-weight:900; letter-spacing:.5px; }
    .welcome-strip-text { color:#B8C7D9; font-size:11px; margin-top:3px; }
    .welcome-strip-badge {
        color:#00E5D4; border:1px solid rgba(0,229,212,.45); border-radius:999px;
        padding:5px 9px; font-size:9px; font-weight:900; letter-spacing:.8px; flex:0 0 auto;
    }
    .ops-hero {
        display:flex; align-items:center; justify-content:space-between; gap:12px;
        background:linear-gradient(135deg, rgba(255,255,255,.075), rgba(0,229,212,.055));
        border:1px solid rgba(255,255,255,.10); border-radius:14px; padding:14px 16px; margin:0 0 16px 0;
    }
    .ops-hero b { color:#F8FAFC; font-size:14px; }
    .ops-hero span { color:#94A3B8; font-size:11px; }
    .ops-hero-pill { color:#FFCC00; border:1px solid rgba(255,204,0,.30); border-radius:999px; padding:6px 10px; font-size:9px; font-weight:900; white-space:nowrap; }
    div[data-testid="stTabs"] button {
        font-weight: 800 !important;
        font-size: 13px !important;
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,.06);
        border: 1px solid rgba(255,255,255,.10);
        border-radius: 12px;
        padding: 8px 12px;
    }
    .stButton > button, .stDownloadButton > button {
        border-radius: 10px !important;
        font-weight: 800 !important;
        min-height: 42px !important;
    }

    /* --- Synthèse journalière inspirée du modèle fourni --- */
    .daily-report {
        background: #FFFFFF;
        color: #111827;
        padding: 0;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 8px 24px rgba(0,0,0,.18);
        margin-bottom: 18px;
    }
    .daily-report-header {
        background: #12396F;
        color: #FFFFFF;
        padding: 14px 18px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
    }
    .daily-report-title {
        font-size: 20px;
        font-weight: 900;
        letter-spacing: .2px;
    }
    .daily-report-date {
        background: #FFFFFF;
        color: #12396F;
        padding: 6px 20px;
        border-radius: 9px;
        min-width: 120px;
        text-align: center;
    }
    .daily-report-date span {
        display: block;
        font-size: 10px;
        font-weight: 800;
    }
    .daily-section-title {
        background: #12396F;
        color: #FFFFFF;
        font-size: 16px;
        font-weight: 800;
        padding: 10px 18px;
        margin-top: 18px;
        border-radius: 8px 8px 0 0;
    }
    .daily-report-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        background: #FFFFFF;
        color: #111827;
    }
    .daily-report-table th {
        background: #FFF500;
        color: #111827;
        border: 1px solid #777;
        padding: 7px 5px;
        text-align: center;
        font-weight: 800;
    }
    .daily-report-table td {
        border: 1px solid #999;
        padding: 6px 5px;
        text-align: center;
    }
    .total-strip {
        display: flex;
        align-items: center;
        background: #DCE9F7;
        border: 1px solid #9AA8B5;
        min-height: 42px;
    }
    .sigma {
        background: #12396F;
        color: #FFFFFF;
        font-size: 23px;
        font-weight: 800;
        padding: 6px 18px;
    }
    .total-label {
        flex: 1;
        text-align: center;
        font-weight: 800;
        color: #17355F;
    }
    .total-strip strong {
        width: 55%;
        text-align: center;
        color: #17355F;
        font-size: 17px;
    }
    .daily-report-summary {
        display: flex;
        gap: 12px;
        margin: 8px 0 4px 0;
    }
    .summary-card {
        background: #E8F0F8;
        border: 1px solid #B7C7D9;
        border-radius: 8px;
        padding: 7px 22px;
        text-align: center;
        min-width: 130px;
    }
    .summary-label {
        font-size: 10px;
        font-weight: 800;
        color: #5C6B78;
    }
    .summary-value {
        font-size: 22px;
        font-weight: 900;
        color: #12396F;
    }
    .difficulty-box {
        min-height: 80px;
        border: 1px solid #999;
        background: #FFFFFF;
        color: #111827;
        padding: 12px;
        font-size: 12px;
        margin-bottom: 4px;
    }
                .zone-dashboard-bottom {
                margin-top: 30px;
                padding-top: 8px;
                border-top: 1px solid rgba(0,229,212,.22);
            }


    /* ============================================================
       YAS — NAVIGATION MOBILE PAR BOUTON HAMBURGER
       Le menu n'apparait que lorsqu'on le demande.
       ============================================================ */
    .yas-mobile-header,
    .yas-mobile-menu {
        display: none;
    }

    /* Conteneur dédié au bouton hamburger : caché par défaut sur PC.
       On utilise un conteneur Streamlit avec une clé dédiée afin de ne pas
       dépendre de l'aria-label ou de la structure interne du bouton. */
    .st-key-yas-mobile-hamburger {
        display: none !important;
    }

    /* Desktop : sidebar Streamlit normale, navigation PC inchangée. */
    @media (min-width: 701px) {
        .yas-mobile-header, .yas-mobile-menu,
        .st-key-yas-mobile-hamburger { display: none !important; }
    }

    @media (max-width: 700px) {
        section[data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        .header-banner { display: none !important; }
        .block-container {
            padding: 0.35rem 0.45rem 1.5rem 0.45rem !important;
            max-width: 100% !important;
        }
        .yas-mobile-header {
            display: flex !important;
            align-items: center;
            justify-content: space-between;
            height: 58px;
            margin: 0 0 8px 0;
            padding: 5px 7px 5px 8px;
            border-radius: 9px;
            background: linear-gradient(135deg, #FFCC00 0%, #FFD633 65%, #52B4E9 100%);
            box-shadow: 0 5px 14px rgba(0,0,0,.25);
            box-sizing: border-box;
            overflow: hidden;
        }
        .yas-mobile-logo {
            height: 47px;
            max-width: 82%;
            object-fit: contain;
            object-position: left center;
            border-radius: 5px;
        }
        .yas-mobile-logo-fallback {
            color: #0A1128;
            font-size: 11px;
            font-weight: 900;
            line-height: 1.1;
            text-transform: uppercase;
        }
        .st-key-yas-mobile-hamburger {
            display: block !important;
            position: relative !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            z-index: 1000000 !important;
        }
        .st-key-yas-mobile-hamburger div[data-testid="stButton"] {
            display: block !important;
        }
        .st-key-yas-mobile-hamburger button {
            position: fixed !important;
            top: 11px !important;
            right: 11px !important;
            width: 34px !important;
            min-width: 34px !important;
            height: 34px !important;
            min-height: 34px !important;
            padding: 0 !important;
            margin: 0 !important;
            border-radius: 9px !important;
            background: #0A1128 !important;
            color: #FFCC00 !important;
            border: 1px solid rgba(255,255,255,.2) !important;
            box-shadow: 0 3px 10px rgba(0,0,0,.3) !important;
            z-index: 1000000 !important;
            font-size: 20px !important;
        }
        .st-key-yas-mobile-hamburger button p {
            color: #FFCC00 !important;
            font-size: 20px !important;
            margin: 0 !important;
        }
        .yas-mobile-menu {
            display: block !important;
            background: #0B2344;
            border: 1px solid rgba(255,204,0,.45);
            border-radius: 13px;
            padding: 9px;
            margin: 0 0 10px 0;
            box-shadow: 0 8px 24px rgba(0,0,0,.35);
        }
        .yas-mobile-menu-title {
            color: #FFCC00;
            font-size: 10px;
            font-weight: 900;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin: 0 2px 7px 2px;
        }
        .yas-mobile-menu div[role="radiogroup"] { gap: 6px; }
        .yas-mobile-menu div[role="radiogroup"] > label {
            background: rgba(255,255,255,.055);
            border: 1px solid rgba(255,255,255,.10);
            border-radius: 10px;
            padding: 8px 9px !important;
            min-height: 40px;
        }
        .yas-mobile-menu div[role="radiogroup"] > label[data-checked="true"] {
            background: linear-gradient(90deg, rgba(0,229,212,.22), rgba(0,229,212,.08));
            border-color: #00E5D4;
        }
        div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
        .stDataFrame, [data-testid="stDataEditor"] { max-width: 100% !important; }
    }

</style>
""", unsafe_allow_html=True)

# --- BASE DE DONNÉES & CONSTANTES ---
MEDIA_DIR = Path(__file__).resolve().parent / 'media_rex'
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

DB = 'daily_mobile_maritime.db'
ZONES = ['ANEHO', 'TSEVIE', 'KPALIME']
STATUS = ['UP', 'DOWN']
STATUS_DISPLAY = ['🟢 UP', '🔴 DOWN']
YESNO = ['OUI', 'NON']

ROLES_EXCEL = [
    'PJ : Permanence de jour (07h-18h)', 
    'PN : Permanence de nuit (18h-07h)', 
    'A : Astreinte', 
    'C : Congé',
    'Repos',
    'Service Normal'
]

ROLES_SHORT = ['PJ', 'PN', 'A', 'C', 'Repos', 'SN']
WEEKEND_TYPES = ['TECHNICIEN', 'CHAUFFEUR']
WEEKEND_SHIFT_OPTIONS = ['', 'PJ', 'PN', 'A']

ROLES_MAPPING = {
    'PJ': 'PJ : Permanence de jour (07h-18h)',
    'PN': 'PN : Permanence de nuit (18h-07h)',
    'A': 'A : Astreinte',
    'C': 'C : Congé',
    'Repos': 'Repos',
    'SN': 'Service Normal'
}

ROLES_REVERSE_MAPPING = {v: k for k, v in ROLES_MAPPING.items()}

DEFAULT_AGENTS = {
    'KPALIME': [
        {'ENTITE': 'TGT', 'Matricule': '03-301226U', 'Nom': 'OUDANOU', 'Prénoms': 'DIFIAGUE', 'Fonction': 'Superviseur Opération & Maintenance', 'Niveau': 'Superviseur et Assimilés', 'Contrat': 'CDI', 'Contact': '70456126'},
        {'ENTITE': 'TGT', 'Matricule': '03-301262Y', 'Nom': 'OURO-TAGBA', 'Prénoms': 'ESSOGNINA', 'Fonction': "Chef(fe) d'Equipe Opérations et Maintenance", 'Niveau': "Chef d'Equipe/Coordinateur", 'Contrat': 'CDI', 'Contact': '93922077'},
        {'ENTITE': 'TGT', 'Matricule': '03-301635D', 'Nom': 'AGBANG', 'Prénoms': 'BIKILI KOFFI', 'Fonction': 'Technicien(ne) Intervention Clients', 'Niveau': "Agent d'Exécution", 'Contrat': 'CDI', 'Contact': '90382392'},
        {'ENTITE': 'TOGO INTERIM', 'Matricule': '2024/TI-2024', 'Nom': 'KOUMBOGLE', 'Prénoms': 'Koffi Namdjounte', 'Fonction': 'TECHNICIEN FIXE', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '92803125'},
        {'ENTITE': 'TOGO INTERIM', 'Matricule': '2024/TI-2026', 'Nom': 'AKPALOO', 'Prénoms': 'Yawo Srdzramdo', 'Fonction': 'TECHNICIEN FIXE', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '90416626'},
        {'ENTITE': 'TGT', 'Matricule': '03-300999H', 'Nom': 'ABASSA', 'Prénoms': 'KOMLATSE', 'Fonction': 'Technicien(ne) Intervention Clients', 'Niveau': "Agent d'Exécution", 'Contrat': 'CDI', 'Contact': '90280895'},
        {'ENTITE': 'TGC', 'Matricule': '02-0000382', 'Nom': 'OUNADI', 'Prénoms': "N'Waki Kokou", 'Fonction': 'Technicien(ne) Maintenance Field RAN', 'Niveau': 'Agent de Maîtrise', 'Contrat': 'CDI', 'Contact': '90313847'},
        {'ENTITE': 'TGC', 'Matricule': '02-0000384', 'Nom': 'DOSSOU-YOVO', 'Prénoms': 'Joys Floresco', 'Fonction': 'Technicien(ne) Maintenance FH & IP/MPLS', 'Niveau': 'Agent de Maîtrise', 'Contrat': 'CDI', 'Contact': '70704170'},
        {'ENTITE': 'AXE CAPITAL', 'Matricule': '-', 'Nom': 'SAMIRE', 'Prénoms': 'Napo Kofi', 'Fonction': 'MONTEUR', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '90775489'}
    ],
    'ANEHO': [
        {'ENTITE': 'TGT', 'Matricule': '03-301255R', 'Nom': 'TODOM', 'Prénoms': 'ADJA BABA ESSOHOUNA', 'Fonction': 'Superviseur Opération & Maintenance', 'Niveau': 'Superviseur et Assimilés', 'Contrat': 'CDI', 'Contact': '70452290'},
        {'ENTITE': 'TGT', 'Matricule': '03-301609K', 'Nom': 'ASSIH', 'Prénoms': 'AFEIGNIDOU', 'Fonction': "Chef(fe) d'Equipe Opérations et Maintenance", 'Niveau': "Chef d'Equipe/Coordinateur", 'Contrat': 'CDI', 'Contact': '70441371'},
        {'ENTITE': 'TGT', 'Matricule': '03-300942G', 'Nom': 'JOHNSON', 'Prénoms': 'ANANI ASSIBAVI', 'Fonction': 'Technicien(ne) Opérations et Maintenance', 'Niveau': "Agent d'Exécution", 'Contrat': 'CDI', 'Contact': '93435222'},
        {'ENTITE': 'TOGO-INTERIM', 'Matricule': '2024/Ti-2020', 'Nom': 'ADOTEVI-AKUE', 'Prénoms': 'Adotè Zomabi', 'Fonction': 'TECHNICIEN FIXE', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '90010508'},
        {'ENTITE': 'TOGO INTERIM', 'Matricule': '2024/Ti-2023', 'Nom': 'SEKPO', 'Prénoms': 'KODJO Jérôme', 'Fonction': 'TECHNICIEN FIXE', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '91223770'},
        {'ENTITE': 'TOGO-INTERIM', 'Matricule': '2024/Ti-2039', 'Nom': 'AYITE', 'Prénoms': 'Koffi', 'Fonction': 'TECHNICIEN FIXE', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '90484776'},
        {'ENTITE': 'TGC', 'Matricule': '02-0000380', 'Nom': 'GABIAM', 'Prénoms': 'Têko Herman Romaric', 'Fonction': 'Technicien(ne) Maintenance FH & IP/MPLS', 'Niveau': 'Agent de Maîtrise', 'Contrat': 'CDI', 'Contact': '93340864'},
        {'ENTITE': 'TGC', 'Matricule': '02-0000381', 'Nom': 'MAKOUYA', 'Prénoms': 'Gnofam', 'Fonction': 'Technicien(ne) Maintenance Field RAN', 'Niveau': 'Agent de Maîtrise', 'Contrat': 'CDI', 'Contact': '93395013'}
    ],
    'TSEVIE': [
        {'ENTITE': 'TOGO INTERIM', 'Matricule': '2024-TI/1464', 'Nom': 'DOUTI', 'Prénoms': "M'domba", 'Fonction': 'TECHNICIEN FIXE', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '70401401'},
        {'ENTITE': 'TOGO INTERIM', 'Matricule': '2024/TI-', 'Nom': 'ZOHOU', 'Prénoms': 'Komivi Elom Maurice', 'Fonction': 'Technicien Field RAN-TRANS', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '91423747'},
        {'ENTITE': 'TOGO INTERIM', 'Matricule': '2024/TI-2019', 'Nom': 'TCHALLA', 'Prénoms': 'Akla Esso Kodjo', 'Fonction': 'Technicien Field RAN-TRANS', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '91971551'},
        {'ENTITE': 'TOGO INTERIM', 'Matricule': '-', 'Nom': 'PAYARO', 'Prénoms': 'Malimda', 'Fonction': 'Technicien Field RAN-TRANS-FTTH', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '90531045'},
        {'ENTITE': 'TOGO INTERIM', 'Matricule': '-', 'Nom': 'HONOU', 'Prénoms': 'Dzigbodi Kodzo', 'Fonction': 'Technicien Field RAN-TRANS', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '90236804'},
        {'ENTITE': 'AXE CAPITAL', 'Matricule': '-', 'Nom': 'ADJEYE', 'Prénoms': 'Mandassini', 'Fonction': 'MONTEUR', 'Niveau': 'Manager/Spécialiste', 'Contrat': 'CDD', 'Contact': '92102174'}
    ]
}

USERS = {
    'aneho': ('aneho2026', 'ZONE', 'ANEHO'),
    'tsevie': ('tsevie2026', 'ZONE', 'TSEVIE'),
    'kpalime': ('kpalime2026', 'ZONE', 'KPALIME'),
    'chef': ('chef2026', 'CHEF', 'GENERAL')
}

def db():
    c = sqlite3.connect(DB, check_same_thread=False, timeout=30)
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass
    return c

def init():
    c = db(); q = c.cursor()
    q.execute('''CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, report_date TEXT, zone TEXT, submitted_by TEXT, submitted_at TEXT, difficulties TEXT, UNIQUE(report_date,zone))''')
    q.execute('''CREATE TABLE IF NOT EXISTS cells_down(id INTEGER PRIMARY KEY, report_date TEXT, zone TEXT, site TEXT, g2 INTEGER, g3 INTEGER, g4 INTEGER, g5 INTEGER, observation TEXT, statut TEXT)''')
    q.execute('''CREATE TABLE IF NOT EXISTS dr2(id INTEGER PRIMARY KEY, report_date TEXT, zone TEXT, site TEXT, sites_impactes TEXT, dr2 TEXT, escalade TEXT, evitable TEXT, point_bloquant TEXT, statut TEXT)''')
    # Migration des anciennes bases : ajout de la colonne SITES IMPACTÉS si elle n'existe pas.
    try:
        q.execute("ALTER TABLE dr2 ADD COLUMN sites_impactes TEXT")
    except sqlite3.OperationalError:
        pass
    q.execute('''CREATE TABLE IF NOT EXISTS instances(id INTEGER PRIMARY KEY, report_date TEXT, zone TEXT, base TEXT, installations INTEGER, derangements INTEGER, points_bloquants TEXT)''')
    q.execute('''CREATE TABLE IF NOT EXISTS degraded(id INTEGER PRIMARY KEY, report_date TEXT, zone TEXT, site_name TEXT, g2 REAL, g3 REAL, g4 REAL, disponibilite REAL, base TEXT)''')
    q.execute('''CREATE TABLE IF NOT EXISTS formations(id INTEGER PRIMARY KEY, report_date TEXT, zone TEXT, base TEXT, intitule TEXT, notions TEXT)''')
    q.execute('''CREATE TABLE IF NOT EXISTS rex_media(
        id INTEGER PRIMARY KEY, report_date TEXT NOT NULL, zone TEXT NOT NULL,
        filename TEXT NOT NULL, stored_name TEXT NOT NULL, media_type TEXT NOT NULL,
        mime_type TEXT, size_bytes INTEGER DEFAULT 0, uploaded_by TEXT, uploaded_at TEXT,
        UNIQUE(report_date, zone, filename, stored_name))''')
    q.execute('''CREATE TABLE IF NOT EXISTS planning(id INTEGER PRIMARY KEY, report_date TEXT, zone TEXT, entite TEXT, matricule TEXT, nom TEXT, prenoms TEXT, fonction TEXT, niveau TEXT, contrat TEXT, contact TEXT, role_garde TEXT)''')
    q.execute("""CREATE TABLE IF NOT EXISTS weekend_permanence(
        id INTEGER PRIMARY KEY, weekend_start TEXT NOT NULL, zone TEXT NOT NULL, base TEXT NOT NULL,
        type_agent TEXT NOT NULL, matricule TEXT, nom TEXT NOT NULL, prenoms TEXT,
        jour TEXT, nuit TEXT, astreinte TEXT,
        UNIQUE(weekend_start, zone, base, type_agent, matricule, nom, prenoms))""")
    q.execute("""CREATE TABLE IF NOT EXISTS monthly_schedule(
        id INTEGER PRIMARY KEY, month TEXT NOT NULL, zone TEXT NOT NULL,
        work_date TEXT NOT NULL, matricule TEXT, nom TEXT NOT NULL,
        prenoms TEXT, entite TEXT, role_garde TEXT NOT NULL, generated_at TEXT,
        UNIQUE(month, zone, work_date, matricule))""")
    q.execute("""CREATE TABLE IF NOT EXISTS monthly_schedule_config(
        id INTEGER PRIMARY KEY, month TEXT NOT NULL, zone TEXT NOT NULL,
        quota_mode TEXT NOT NULL DEFAULT 'Par agent', pj_target INTEGER DEFAULT 8,
        pn_target INTEGER DEFAULT 8, a_target INTEGER DEFAULT 8, updated_at TEXT,
        UNIQUE(month, zone))""")
    q.execute("""CREATE TABLE IF NOT EXISTS monthly_agent_schedule_config(
        id INTEGER PRIMARY KEY, month TEXT NOT NULL, zone TEXT NOT NULL,
        matricule TEXT NOT NULL, nom TEXT NOT NULL, prenoms TEXT,
        pj_target INTEGER DEFAULT 8, pn_target INTEGER DEFAULT 8,
        a_target INTEGER DEFAULT 8, updated_at TEXT,
        UNIQUE(month, zone, matricule))""")
    c.commit(); c.close()

init()

def login():
    st.markdown(f'''
        <div class="login-wrapper">
            <div style="margin-bottom:15px;">{("<img src=\"" + LOGO_SRC + "\" style=\"width:140px; max-height:90px; object-fit:contain;\">") if LOGO_SRC else ""}</div>
            <h2 style="color: #FFCC00; font-weight: 900; font-size: 22px; margin: 0 0 6px 0;">HUB OPÉRATIONNEL</h2>
            <p style="color: #CBD5E1; font-size: 13px; font-weight: 600; margin-bottom: 25px;">Authentification DFO - SRTM</p>
        </div>
    ''', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form('login_form'):
            u = st.text_input('Identifiant', placeholder='Ex: aneho ou chef')
            p = st.text_input('Mot de passe', type='password', placeholder='••••••••')
            submit = st.form_submit_button('Connexion', type='primary', use_container_width=True)
            
            if submit:
                x = USERS.get(u.lower().strip())
                if x and x[0] == p:
                    st.session_state.update(auth=True, user=u.lower().strip(), role=x[1], zone=x[2])
                    st.rerun()
                else: 
                    st.error('❌ Identifiant ou mot de passe incorrect. Vérifiez votre saisie.')

if not st.session_state.get('auth', False): 
    login()
    st.stop()

USER, ROLE, ZONE = st.session_state.user, st.session_state.role, st.session_state.zone

def qdf(sql, params=()):
    c = db(); d = pd.read_sql_query(sql, c, params=params); c.close()
    return d

def get_monthly_schedule_config(year, month, zone):
    """Récupère les paramètres personnalisables de génération du mois."""
    mk = f"{year:04d}-{month:02d}"
    d = qdf("SELECT quota_mode,pj_target,pn_target,a_target FROM monthly_schedule_config WHERE month=? AND zone=?", (mk, zone))
    if d.empty:
        return {"quota_mode": "Par agent", "PJ": 8, "PN": 8, "A": 8}
    r = d.iloc[0]
    return {
        "quota_mode": str(r.get("quota_mode") or "Par agent"),
        "PJ": int(r.get("pj_target") or 0),
        "PN": int(r.get("pn_target") or 0),
        "A": int(r.get("a_target") or 0),
    }


def save_monthly_schedule_config(year, month, zone, quota_mode, pj_target, pn_target, a_target):
    mk = f"{year:04d}-{month:02d}"
    c = db(); q = c.cursor()
    q.execute("""INSERT OR REPLACE INTO monthly_schedule_config
        (month,zone,quota_mode,pj_target,pn_target,a_target,updated_at)
        VALUES(?,?,?,?,?,?,?)""",
        (mk, zone, quota_mode, int(pj_target), int(pn_target), int(a_target),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.commit(); c.close()


def get_agent_monthly_schedule_config(year, month, zone, matricule):
    """Retourne la programmation individuelle d'un agent pour le mois."""
    mk = f"{int(year):04d}-{int(month):02d}"
    d = qdf("""SELECT pj_target,pn_target,a_target FROM monthly_agent_schedule_config
               WHERE month=? AND zone=? AND matricule=?""", (mk, zone, str(matricule)))
    if d.empty:
        base = get_monthly_schedule_config(year, month, zone)
        return {"PJ": int(base.get("PJ", 8)), "PN": int(base.get("PN", 8)), "A": int(base.get("A", 8))}
    r = d.iloc[0]
    return {"PJ": int(r.get("pj_target") or 0), "PN": int(r.get("pn_target") or 0), "A": int(r.get("a_target") or 0)}


def save_agent_monthly_schedule_config(year, month, zone, agent, pj_target, pn_target, a_target):
    """Enregistre les objectifs PJ/PN/A d'un agent pour un mois."""
    mk = f"{int(year):04d}-{int(month):02d}"
    c = db(); q = c.cursor()
    q.execute("""INSERT OR REPLACE INTO monthly_agent_schedule_config
        (month,zone,matricule,nom,prenoms,pj_target,pn_target,a_target,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        (mk, zone, str(agent.get("Matricule", "-")), str(agent.get("Nom", "")),
         str(agent.get("Prénoms", "")), int(pj_target), int(pn_target), int(a_target),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    c.commit(); c.close()


def get_all_agent_monthly_configs(year, month, zone):
    """Tableau des programmations individuelles enregistrées."""
    rows = []
    for a in DEFAULT_AGENTS.get(zone, []):
        cfg = get_agent_monthly_schedule_config(year, month, zone, a.get("Matricule", "-"))
        rows.append({
            "MATRICULE": a.get("Matricule", "-"),
            "AGENT": f'{a.get("Nom", "")} {a.get("Prénoms", "")}'.strip(),
            "FONCTION": a.get("Fonction", ""),
            "PJ": cfg["PJ"], "PN": cfg["PN"], "A": cfg["A"],
            "TOTAL": cfg["PJ"] + cfg["PN"] + cfg["A"]
        })
    return pd.DataFrame(rows)


def generate_monthly_schedule(year, month, zone, force=True, config=None):
    """Génère le planning selon les programmations individuelles enregistrées."""
    agents = DEFAULT_AGENTS.get(zone, [])
    if not agents:
        return
    nd = calendar.monthrange(int(year), int(month))[1]
    mk = f"{int(year):04d}-{int(month):02d}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    config = config or get_monthly_schedule_config(year, month, zone)
    quota_mode = config.get("quota_mode", "Par agent")

    targets = {}
    for i, a in enumerate(agents):
        individual = get_agent_monthly_schedule_config(year, month, zone, a.get("Matricule", "-"))
        targets[i] = {r: max(0, int(individual.get(r, config.get(r, 8)))) for r in ("PJ", "PN", "A")}

    if quota_mode == "Total équipe":
        team = {r: max(0, int(config.get(r, 8))) for r in ("PJ", "PN", "A")}
        for r, total in team.items():
            for i in range(len(agents)):
                targets[i][r] = 0
            for n in range(total):
                targets[n % len(agents)][r] += 1

    c = db(); q = c.cursor()
    if force:
        q.execute("DELETE FROM monthly_schedule WHERE month=? AND zone=?", (mk, zone))

    counts = {i: {"PJ": 0, "PN": 0, "A": 0} for i in range(len(agents))}
    assigned_dates = {i: set() for i in range(len(agents))}

    for day in range(1, nd + 1):
        dt = date(int(year), int(month), day)
        assigned_today = set()
        for role in ("PJ", "PN", "A"):
            candidates = [i for i in range(len(agents)) if i not in assigned_today and counts[i][role] < targets[i][role]]
            if not candidates or (role == "A" and dt.weekday() >= 5):
                continue
            i = min(candidates, key=lambda x: (-(targets[x][role] - counts[x][role]), sum(counts[x].values()), len(assigned_dates[x]), x))
            a = agents[i]
            q.execute("""INSERT OR REPLACE INTO monthly_schedule
                (month,zone,work_date,matricule,nom,prenoms,entite,role_garde,generated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (mk, zone, dt.strftime("%d/%m/%Y"), a["Matricule"], a["Nom"], a["Prénoms"], a["ENTITE"], ROLES_MAPPING[role], now))
            counts[i][role] += 1
            assigned_dates[i].add(day)
            assigned_today.add(i)

        for i, a in enumerate(agents):
            if i not in assigned_today:
                default = "Service Normal" if dt.weekday() < 5 else "Repos"
                q.execute("""INSERT OR REPLACE INTO monthly_schedule
                    (month,zone,work_date,matricule,nom,prenoms,entite,role_garde,generated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (mk, zone, dt.strftime("%d/%m/%Y"), a["Matricule"], a["Nom"], a["Prénoms"], a["ENTITE"], default, now))
    c.commit(); c.close()


def _weighted_assignment(candidates, role, counts, targets, last_role, assigned_today):
    """Choisit l'agent le plus en déficit par rapport à son quota cible."""
    if not candidates:
        return None
    target = targets.get(role, 0)
    def score(i):
        # Plus le déficit est grand, plus l'agent est prioritaire.
        deficit = target - counts[i].get(role, 0)
        repeat_penalty = 1000 if last_role.get(i) == role else 0
        today_penalty = 10000 if i in assigned_today else 0
        # Légère priorité à celui qui a le moins de gardes au total.
        total = sum(counts[i].values())
        return (today_penalty + repeat_penalty, -deficit, total, i)
    return min(candidates, key=score)


def get_monthly_pivot_df(year, month, zone):
    nd = calendar.monthrange(year, month)[1]
    days = [f"{d:02d}" for d in range(1,nd+1)]
    agents = DEFAULT_AGENTS.get(zone, [])
    base = pd.DataFrame(agents)[["Nom","Prénoms","Fonction"]].rename(
        columns={"Nom":"NOM","Prénoms":"PRÉNOMS","Fonction":"FONCTION"}
    ) if agents else pd.DataFrame(columns=["NOM","PRÉNOMS","FONCTION"])
    for d in days: base[d] = "SN"
    dbdf = qdf("SELECT work_date,nom,prenoms,role_garde FROM monthly_schedule WHERE month=? AND zone=?",
               (f"{year:04d}-{month:02d}",zone))
    for idx,row in base.iterrows():
        m = dbdf[(dbdf.nom==row.NOM)&(dbdf.prenoms==row["PRÉNOMS"])]
        for _,x in m.iterrows():
            try:
                dn=int(str(x.work_date).split("/")[0])
                if 1<=dn<=nd: base.at[idx,f"{dn:02d}"]=ROLES_REVERSE_MAPPING.get(x.role_garde,"SN")
            except Exception: pass
    return base

def save_monthly_pivot_df(df_pivot, year, month, zone):
    nd=calendar.monthrange(year,month)[1]; mk=f"{year:04d}-{month:02d}"
    amap={(a["Nom"],a["Prénoms"]):a for a in DEFAULT_AGENTS.get(zone,[])}
    c=db(); q=c.cursor(); q.execute("DELETE FROM monthly_schedule WHERE month=? AND zone=?",(mk,zone))
    now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for d in range(1,nd+1):
        ds=f"{d:02d}/{month:02d}/{year:04d}"; col=f"{d:02d}"
        for _,row in df_pivot.iterrows():
            a=amap.get((row.NOM,row["PRÉNOMS"]),{})
            q.execute("""INSERT OR REPLACE INTO monthly_schedule
                (month,zone,work_date,matricule,nom,prenoms,entite,role_garde,generated_at)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (mk,zone,ds,a.get("Matricule","-"),row.NOM,row["PRÉNOMS"],a.get("ENTITE",""),
                 ROLES_MAPPING.get(row.get(col,"SN"),"Service Normal"),now))
    c.commit(); c.close()

def weekend_dates(year, month):
    """Retourne les samedis d'un mois et leurs dimanches associés."""
    nd = calendar.monthrange(year, month)[1]
    return [date(year, month, d) for d in range(1, nd + 1) if date(year, month, d).weekday() == 5]

def get_bases_for_zone(report_date, zone):
    """Liste les bases connues pour la zone, avec la zone comme base par défaut."""
    bases = [zone]
    try:
        d1 = qdf("SELECT DISTINCT base FROM instances WHERE report_date=? AND zone=? AND TRIM(base)<>''", (report_date, zone))
        d2 = qdf("SELECT DISTINCT base FROM degraded WHERE report_date=? AND zone=? AND TRIM(base)<>''", (report_date, zone))
        for d in (d1, d2):
            if not d.empty:
                for b in d.iloc[:,0].astype(str).tolist():
                    if b.strip() and b.strip() not in bases:
                        bases.append(b.strip())
    except Exception:
        pass
    return bases

def get_weekend_permanence_df(year, month, weekend_start, zone):
    """Construit la vue des permanences du week-end pour une base/zone."""
    ws = weekend_start.strftime('%d/%m/%Y') if isinstance(weekend_start, date) else str(weekend_start)
    existing = qdf("SELECT base BASE, type_agent TYPE, matricule MATRICULE, nom NOM, prenoms PRÉNOMS, jour JOUR, nuit NUIT, astreinte ASTREINTE FROM weekend_permanence WHERE weekend_start=? AND zone=? ORDER BY type_agent, nom, prenoms", (ws, zone))
    if not existing.empty:
        return existing

    agents = DEFAULT_AGENTS.get(zone, [])
    rows = []
    for a in agents:
        rows.append({
            'BASE': zone, 'TYPE': 'TECHNICIEN', 'MATRICULE': a.get('Matricule','-'),
            'NOM': a.get('Nom',''), 'PRÉNOMS': a.get('Prénoms',''),
            'JOUR': '', 'NUIT': '', 'ASTREINTE': ''
        })
    return pd.DataFrame(rows, columns=['BASE','TYPE','MATRICULE','NOM','PRÉNOMS','JOUR','NUIT','ASTREINTE'])

def save_weekend_permanence_df(df, year, month, weekend_start, zone):
    """Enregistre les permanences du week-end sans toucher au planning mensuel."""
    ws = weekend_start.strftime('%d/%m/%Y') if isinstance(weekend_start, date) else str(weekend_start)
    c = db(); q = c.cursor()
    q.execute("DELETE FROM weekend_permanence WHERE weekend_start=? AND zone=?", (ws, zone))
    for x in df.fillna('').to_dict('records'):
        q.execute("""INSERT INTO weekend_permanence
            (weekend_start,zone,base,type_agent,matricule,nom,prenoms,jour,nuit,astreinte)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (ws, zone, x.get('BASE', zone), x.get('TYPE','TECHNICIEN'), x.get('MATRICULE','-'),
             x.get('NOM',''), x.get('PRÉNOMS',''), x.get('JOUR',''), x.get('NUIT',''), x.get('ASTREINTE','')))
    c.commit(); c.close()

def export_weekend_permanence_excel(year, month, zone, weekend_start, df):
    o = BytesIO()
    end = weekend_start + pd.Timedelta(days=1).to_pytimedelta()
    title = f"Permanence {weekend_start.strftime('%d-%m-%Y')}"
    with pd.ExcelWriter(o, engine='xlsxwriter') as w:
        out = df.copy()
        out.insert(0, 'WEEK-END', f"{weekend_start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}")
        out.to_excel(w, sheet_name='Permanences Week-end', index=False)
        ws = w.sheets['Permanences Week-end']
        ws.freeze_panes(1, 0)
        ws.autofilter(0, 0, max(len(out),1), max(len(out.columns)-1,0))
        ws.set_column(0, max(len(out.columns)-1,0), 20)
    return o.getvalue()

def monthly_summary(year,month,zone):
    piv=get_monthly_pivot_df(year,month,zone)
    if piv.empty:return piv
    days=[f"{d:02d}" for d in range(1,calendar.monthrange(year,month)[1]+1)]
    out=piv[["NOM","PRÉNOMS","FONCTION"]].copy()
    for code in ROLES_SHORT: out[code]=piv[days].apply(lambda r:int((r==code).sum()),axis=1)
    out["TOTAL JOURS"]=len(days)
    return out

def export_monthly_excel(year,month,zone):
    """Exporte le planning mensuel avec la charte couleur de la maquette."""
    piv=get_monthly_pivot_df(year,month,zone); recap=monthly_summary(year,month,zone)
    detail=qdf("""SELECT zone ZONE,work_date DATE,matricule MATRICULE,nom NOM,prenoms PRÉNOMS,
                         entite ENTITÉ,role_garde "RÔLE / GARDE"
                  FROM monthly_schedule WHERE month=? AND zone=? ORDER BY work_date,nom""",
               (f"{year:04d}-{month:02d}",zone))
    o=BytesIO()
    with pd.ExcelWriter(o,engine="xlsxwriter") as w:
        piv.to_excel(w,sheet_name=f"Planning {zone}",index=False)
        recap.to_excel(w,sheet_name=f"Recap {zone}",index=False)
        detail.to_excel(w,sheet_name="Détail",index=False)

        wb=w.book
        navy=wb.add_format({'bold':True,'font_color':'#FFFFFF','bg_color':'#12396F','border':1,'align':'center','valign':'vcenter'})
        text=wb.add_format({'font_color':'#111827','border':1,'align':'left','valign':'vcenter'})
        fills={
            'PJ':wb.add_format({'bg_color':'#FFD84D','font_color':'#111827','bold':True,'border':1,'align':'center'}),
            'PN':wb.add_format({'bg_color':'#F6A623','font_color':'#111827','bold':True,'border':1,'align':'center'}),
            'A':wb.add_format({'bg_color':'#8BE28B','font_color':'#111827','bold':True,'border':1,'align':'center'}),
            'C':wb.add_format({'bg_color':'#E5E7EB','font_color':'#111827','bold':True,'border':1,'align':'center'}),
            'Repos':wb.add_format({'bg_color':'#C8EEFF','font_color':'#123A63','bold':True,'border':1,'align':'center'}),
            'SN':wb.add_format({'bg_color':'#F1F5F9','font_color':'#111827','border':1,'align':'center'}),
        }
        weekend_fmt=wb.add_format({'bg_color':'#C8EEFF','font_color':'#123A63','bold':True,'border':1,'align':'center'})
        holiday_fmt=wb.add_format({'bg_color':'#FFC7CE','font_color':'#8B1E2D','bold':True,'border':1,'align':'center'})

        ws=w.sheets[f"Planning {zone}"]
        ws.freeze_panes(1,3)
        ws.autofilter(0,0,max(len(piv),1),max(len(piv.columns)-1,0))
        ws.set_column(0,0,20)
        ws.set_column(1,1,26)
        ws.set_column(2,2,42)
        ws.set_column(3,len(piv.columns)-1,7)
        for c in range(len(piv.columns)):
            ws.write(0,c,piv.columns[c],navy)
        holidays=togo_holidays(year)
        for r_i in range(len(piv)):
            ws.write(r_i+1,0,piv.iloc[r_i,0],text)
            ws.write(r_i+1,1,piv.iloc[r_i,1],text)
            ws.write(r_i+1,2,piv.iloc[r_i,2],text)
            for c_i,col in enumerate(piv.columns[3:], start=3):
                dt=date(year,month,int(col))
                val=str(piv.iloc[r_i][col])
                fmt=holiday_fmt if dt in holidays else fills.get(val, weekend_fmt if dt.weekday()>=5 else fills['SN'])
                ws.write(r_i+1,c_i,val,fmt)

        for sheet in [f"Recap {zone}","Détail"]:
            sw=w.sheets[sheet]
            sw.freeze_panes(1,0)
            sw.autofilter(0,0,max(len((recap if sheet.startswith('Recap') else detail)),1),max(len((recap if sheet.startswith('Recap') else detail).columns)-1,0))
            sw.set_column(0,max(len((recap if sheet.startswith('Recap') else detail).columns)-1,0),18)
            obj=recap if sheet.startswith('Recap') else detail
            for c in range(len(obj.columns)):
                sw.write(0,c,obj.columns[c],navy)
    return o.getvalue()

def get_monthly_pivot_df(year, month, zone):
    num_days = calendar.monthrange(year, month)[1]
    days_cols = [f"{d:02d}" for d in range(1, num_days + 1)]
    df_db = qdf("SELECT report_date, nom, prenoms, role_garde FROM planning WHERE zone=?", (zone,))
    agents = DEFAULT_AGENTS.get(zone, [])
    base_df = pd.DataFrame(agents)[['Nom', 'Prénoms', 'Fonction']].rename(columns={'Nom': 'NOM', 'Prénoms': 'PRÉNOMS', 'Fonction': 'FONCTION'}) if agents else pd.DataFrame(columns=['NOM', 'PRÉNOMS', 'FONCTION'])

    for d in days_cols: base_df[d] = 'SN'
    if not df_db.empty:
        for idx, row in base_df.iterrows():
            nom, prenom = row['NOM'], row['PRÉNOMS']
            for day_num in range(1, num_days + 1):
                date_str = f"{day_num:02d}/{month:02d}/{year:04d}"
                match = df_db[(df_db['report_date'] == date_str) & (df_db['nom'] == nom) & (df_db['prenoms'] == prenom)]
                if not match.empty:
                    base_df.at[idx, f"{day_num:02d}"] = ROLES_REVERSE_MAPPING.get(match.iloc[0]['role_garde'], 'SN')
    return base_df

def save_monthly_pivot_df(df_pivot, year, month, zone):
    num_days = calendar.monthrange(year, month)[1]
    agents = DEFAULT_AGENTS.get(zone, [])
    agent_dict = {(a['Nom'], a['Prénoms']): a for a in agents}
    c = db(); q = c.cursor()
    for day_num in range(1, num_days + 1):
        date_str = f"{day_num:02d}/{month:02d}/{year:04d}"
        q.execute("DELETE FROM planning WHERE zone=? AND report_date=?", (zone, date_str))
        col_day = f"{day_num:02d}"
        for _, row in df_pivot.iterrows():
            nom, prenom = row['NOM'], row['PRÉNOMS']
            ag_info = agent_dict.get((nom, prenom), {})
            role_full = ROLES_MAPPING.get(row.get(col_day, 'SN'), 'Service Normal')
            q.execute('''INSERT INTO planning(report_date, zone, entite, matricule, nom, prenoms, fonction, niveau, contrat, contact, role_garde) 
                         VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                      (date_str, zone, ag_info.get('ENTITE', ''), ag_info.get('Matricule', '-'), nom, prenom, 
                       ag_info.get('Fonction', row['FONCTION']), ag_info.get('Niveau', ''), ag_info.get('Contrat', ''), ag_info.get('Contact', ''), role_full))
    c.commit(); c.close()

def _media_type_from_mime(mime_type, filename):
    mime = (mime_type or mimetypes.guess_type(filename)[0] or '').lower()
    if mime.startswith('image/'):
        return 'image'
    if mime.startswith('video/'):
        return 'video'
    return ''

def save_rex_media(report_date, zone, uploaded_files):
    """Enregistre les photos/vidéos du partage d'expérience et leurs métadonnées."""
    if not uploaded_files:
        return 0
    media_zone_dir = MEDIA_DIR / str(zone) / str(report_date)
    media_zone_dir.mkdir(parents=True, exist_ok=True)
    c = db(); q = c.cursor(); saved = 0
    try:
        for uploaded in uploaded_files:
            media_type = _media_type_from_mime(uploaded.type, uploaded.name)
            if not media_type:
                continue
            data = uploaded.getvalue()
            digest = hashlib.sha256(data).hexdigest()[:16]
            suffix = Path(uploaded.name).suffix.lower()
            safe_stored = f"{digest}{suffix}"
            target = media_zone_dir / safe_stored
            if not target.exists():
                target.write_bytes(data)
            q.execute('''INSERT OR IGNORE INTO rex_media
                (report_date,zone,filename,stored_name,media_type,mime_type,size_bytes,uploaded_by,uploaded_at)
                VALUES(?,?,?,?,?,?,?,?,?)''',
                (str(report_date), str(zone), uploaded.name, safe_stored, media_type,
                 uploaded.type or mimetypes.guess_type(uploaded.name)[0] or '', len(data), USER,
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            if q.rowcount:
                saved += 1
        c.commit()
    finally:
        c.close()
    return saved

def load_rex_media(report_date, zone):
    c = db()
    try:
        return c.execute('''SELECT id,filename,stored_name,media_type,mime_type,size_bytes,uploaded_by,uploaded_at
                            FROM rex_media WHERE report_date=? AND zone=? ORDER BY id DESC''',
                         (str(report_date), str(zone))).fetchall()
    finally:
        c.close()

def format_media_size(size_bytes):
    size = float(size_bytes or 0)
    for unit in ('o', 'Ko', 'Mo', 'Go'):
        if size < 1024 or unit == 'Go':
            return f"{size:.1f} {unit}" if unit != 'o' else f"{int(size)} {unit}"
        size /= 1024

def save(r, z, diff, cells, dr, ins, deg, forms, plan):
    # Supprime les lignes entièrement vides avant l'enregistrement.
    def _clean_rows(df):
        if df is None or df.empty:
            return pd.DataFrame()
        out = df.copy().dropna(how='all')
        return out.fillna('')

    cells = _clean_rows(cells)
    dr = _clean_rows(dr)
    ins = _clean_rows(ins)
    deg = _clean_rows(deg)
    forms = _clean_rows(forms)

    c = db(); q = c.cursor()
    for t in ['reports', 'cells_down', 'dr2', 'instances', 'degraded', 'formations', 'planning']: 
        q.execute(f'DELETE FROM {t} WHERE report_date=? AND zone=?', (r, z))
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    q.execute('INSERT INTO reports(report_date,zone,submitted_by,submitted_at,difficulties) VALUES(?,?,?,?,?)', (r, z, USER, now, diff))
    for x in cells.fillna('').to_dict('records'): 
        q.execute('INSERT INTO cells_down(report_date,zone,site,g2,g3,g4,g5,observation,statut) VALUES(?,?,?,?,?,?,?,?,?)', (r, z, x.get('SITE',''), int(x.get('2G') or 0), int(x.get('3G') or 0), int(x.get('4G') or 0), int(x.get('5G') or 0), x.get('OBSERVATION',''), x.get('STATUT','')))
    for x in dr.fillna('').to_dict('records'): 
        q.execute('INSERT INTO dr2(report_date,zone,site,sites_impactes,dr2,escalade,evitable,point_bloquant,statut) VALUES(?,?,?,?,?,?,?,?,?)', (r, z, x.get('SITE',''), x.get('SITES IMPACTÉS',''), x.get('DR2',''), x.get('ESCALADE',''), x.get('ÉVITABLE ?',''), x.get('POINT BLOQUANT',''), x.get('STATUT','')))
    for x in ins.fillna('').to_dict('records'): 
        q.execute('INSERT INTO instances(report_date,zone,base,installations,derangements,points_bloquants) VALUES(?,?,?,?,?,?)', (r, z, x.get('BASES',''), int(x.get('INSTALLATIONS') or 0), int(x.get('DÉRANGEMENTS') or 0), x.get('POINTS BLOQUANTS','')))
    for x in deg.fillna('').to_dict('records'): 
        q.execute('INSERT INTO degraded(report_date,zone,site_name,g2,g3,g4,disponibilite,base) VALUES(?,?,?,?,?,?,?,?)', (r, z, x.get('SITE NAME',''), float(x.get('2G') or 0), float(x.get('3G') or 0), float(x.get('4G') or 0), float(x.get('DISPONIBILITÉ') or 0), x.get('BASE','')))
    for x in forms.fillna('').to_dict('records'): 
        q.execute('INSERT INTO formations(report_date,zone,base,intitule,notions) VALUES(?,?,?,?,?)', (r, z, x.get('BASE',''), x.get('INTITULÉ',''), x.get('NOTIONS VUES','')))
    for x in plan.fillna('').to_dict('records'):
        q.execute('INSERT INTO planning(report_date,zone,entite,matricule,nom,prenoms,fonction,niveau,contrat,contact,role_garde) VALUES(?,?,?,?,?,?,?,?,?,?,?)', 
                  (r, z, x.get('ENTITÉ',''), x.get('MATRICULE',''), x.get('NOM',''), x.get('PRÉNOMS',''), x.get('FONCTION',''), x.get('NIVEAU HIÉRARCHIQUE',''), x.get('NATURE CONTRAT',''), x.get('CONTACT',''), x.get('RÔLE / GARDE','')))
    c.commit(); c.close()

def load(r, z):
    diff = qdf('SELECT difficulties FROM reports WHERE report_date=? AND zone=?', (r, z))
    cells = qdf("SELECT site SITE,g2 '2G',g3 '3G',g4 '4G',g5 '5G',observation OBSERVATION,statut STATUT FROM cells_down WHERE report_date=? AND zone=?", (r, z))
    dr = qdf("SELECT site SITE,sites_impactes 'SITES IMPACTÉS',dr2 DR2,escalade ESCALADE,evitable 'ÉVITABLE ?',point_bloquant 'POINT BLOQUANT',statut STATUT FROM dr2 WHERE report_date=? AND zone=?", (r, z))
    ins = qdf("SELECT base BASES,installations INSTALLATIONS,derangements DÉRANGEMENTS,points_bloquants 'POINTS BLOQUANTS' FROM instances WHERE report_date=? AND zone=?", (r, z))
    deg = qdf("SELECT site_name 'SITE NAME',g2 '2G',g3 '3G',g4 '4G',disponibilite 'DISPONIBILITÉ',base BASE FROM degraded WHERE report_date=? AND zone=?", (r, z))
    forms = qdf("SELECT base BASE,intitule 'INTITULÉ',notions 'NOTIONS VUES' FROM formations WHERE report_date=? AND zone=?", (r, z))
    plan = qdf("SELECT entite ENTITÉ,matricule MATRICULE,nom NOM,prenoms PRÉNOMS,fonction FONCTION,niveau 'NIVEAU HIÉRARCHIQUE',contrat 'NATURE CONTRAT',contact CONTACT,role_garde 'RÔLE / GARDE' FROM planning WHERE report_date=? AND zone=?", (r, z))
    
    if plan.empty and z in DEFAULT_AGENTS:
        df_default = pd.DataFrame(DEFAULT_AGENTS[z])
        plan = df_default.rename(columns={'ENTITE': 'ENTITÉ', 'Matricule': 'MATRICULE', 'Nom': 'NOM', 'Prénoms': 'PRÉNOMS', 'Fonction': 'FONCTION', 'Niveau': 'NIVEAU HIÉRARCHIQUE', 'Contrat': 'NATURE CONTRAT', 'Contact': 'CONTACT'})
        plan['RÔLE / GARDE'] = 'Service Normal'
    return (diff.iloc[0,0] if not diff.empty else ''), cells, dr, ins, deg, forms, plan


# ===== NAVIGATION MOBILE YAS =====
# Sur téléphone : un petit bouton ☰ reste visible dans le bandeau.
# Le menu s'ouvre uniquement à la demande et se referme après sélection.
if "yas_mobile_menu_open" not in st.session_state:
    st.session_state.yas_mobile_menu_open = False

# True uniquement lorsqu'une rubrique a été choisie depuis le menu mobile.
# Cela évite que le dernier choix mobile bloque la navigation de la sidebar sur PC.
if "yas_mobile_nav_override" not in st.session_state:
    st.session_state.yas_mobile_nav_override = False

if "yas_mobile_choice" not in st.session_state:
    st.session_state.yas_mobile_choice = (
        "🚨 Rapport du jour" if ROLE == "ZONE" else "✨ Actualités opérationnelles"
    )

def _desktop_zone_navigation_changed():
    st.session_state.yas_mobile_nav_override = False

def _desktop_supervisor_navigation_changed():
    st.session_state.yas_mobile_nav_override = False

st.markdown(f'''
<div class="yas-mobile-header">
  {("<img class=\"yas-mobile-logo\" src=\"" + LOGO_SRC + "\" alt=\"YAS DFO-SRTM\">") if LOGO_SRC else "<div class=\"yas-mobile-logo-fallback\">📡 YAS DFO-SRTM<br>HUB OPÉRATIONNEL MARITIME</div>"}
</div>
''', unsafe_allow_html=True)

with st.container(key="yas-mobile-hamburger"):
    if st.button("☰", key="yas_mobile_menu_button", help="Ouvrir / fermer le menu"):
        st.session_state.yas_mobile_menu_open = not st.session_state.yas_mobile_menu_open
        st.rerun()

if st.session_state.yas_mobile_menu_open:
    if ROLE == "ZONE":
        mobile_options = ["🚨 Rapport du jour", "🗓️ Planning", "🧠 Formations polyvalentes ", "🚀 Vérifier & Soumettre"]
        mobile_title = "Navigation • Zone"
    else:
        mobile_options = ["✨ Actualités opérationnelles", "📄 Problématiques", "📅 Week-ends", "🗓️ Planning secteurs"]
        mobile_title = "Navigation • Superviseur"

    st.markdown(f'<div class="yas-mobile-menu"><div class="yas-mobile-menu-title">{mobile_title}</div>', unsafe_allow_html=True)
    mobile_choice = st.radio(
        "Menu mobile",
        mobile_options,
        index=mobile_options.index(st.session_state.yas_mobile_choice) if st.session_state.yas_mobile_choice in mobile_options else 0,
        key="yas_mobile_choice_widget",
        label_visibility="collapsed"
    )
    if mobile_choice != st.session_state.yas_mobile_choice:
        st.session_state.yas_mobile_choice = mobile_choice
        st.session_state.yas_mobile_nav_override = True
        st.session_state.yas_mobile_menu_open = False
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- HEADER YAS ---
st.markdown(f'''
    <div class="header-banner">
        <div class="header-title-box">
            {("<img src=\"" + LOGO_SRC + "\" style=\"height:60px; max-width:180px; object-fit:contain; border-radius:8px;\">") if LOGO_SRC else "<div style=\"font-weight:900;color:#0A1128;\">YAS MARITIME</div>"}
            <div>
                <h1 class="header-title">HUB OPÉRATIONNEL MARITIME</h1>
                <div class="header-subtitle">Direction des Opérations Fixes & Mobiles (DFO - SRTM)</div>
            </div>
        </div>
        <div>
            <span class="role-badge">
                {"👑 SUPERVISEUR GENERAL" if ROLE == 'CHEF' else f"📍 SECTEUR : {ZONE}"}
            </span>
        </div>
    </div>
''', unsafe_allow_html=True)

# Barre supérieure
c_top1, c_top2 = st.columns([4, 1.2])
with c_top1:
    dt_selected = st.date_input('📅 Date du rapport', date.today())
    r = dt_selected.strftime('%d/%m/%Y')
with c_top2:
    with st.container(key="logout_container"):
        st.write("")
        if st.button('🚪  DÉCONNEXION', use_container_width=True):
            st.session_state.clear()
            st.rerun()

st.write("")

st.markdown(f"""
<div class="page-intro">
  <div class="page-intro-title">👋 Bienvenue dans votre espace {ZONE if ROLE == 'ZONE' else 'Superviseur Général'}</div>
  <div class="page-intro-text">
    <b>1.</b> Choisissez la date &nbsp;•&nbsp;
    <b>2.</b> Saisissez les informations nécessaires &nbsp;•&nbsp;
    <b>3.</b> Vérifiez les indicateurs &nbsp;•&nbsp;
    <b>4.</b> Soumettez le rapport.
  </div>
</div>
""", unsafe_allow_html=True)

# Bandeau d'accueil compact : remplace le guide d'utilisation par un espace plus visuel.
st.markdown(f"""
<div class="welcome-strip">
  <div class="welcome-strip-icon">✦</div>
  <div class="welcome-strip-main">
    <div class="welcome-strip-title">ESPACE OPÉRATIONNEL • {ZONE if ROLE == 'ZONE' else 'SUPERVISION GÉNÉRALE'}</div>
    <div class="welcome-strip-text">
      📅 {r} &nbsp; • &nbsp; ⚡ Données opérationnelles prêtes &nbsp; • &nbsp; 🔐 Session active
    </div>
  </div>
  <div class="welcome-strip-badge">EN LIGNE</div>
</div>
""", unsafe_allow_html=True)


# V3 : reprise rapide du rapport de la veille
if ROLE == 'ZONE':
    previous_date = dt_selected - timedelta(days=1)
    previous_label = previous_date.strftime('%d/%m/%Y')
    if st.button(f'🔄 Reprendre les données du {previous_label}', use_container_width=True, key='copy_previous_report'):
        prev_diff, prev_cells, prev_dr, prev_ins, prev_deg, prev_forms, _ = load(previous_label, ZONE)
        st.session_state['copy_previous_data'] = {
            'date': r,
            'diff': prev_diff,
            'cells': prev_cells,
            'dr': prev_dr,
            'ins': prev_ins,
            'deg': prev_deg,
            'forms': prev_forms,
        }
        st.rerun()

# --- SYNTHÈSE JOURNALIÈRE : rendu proche du modèle fourni ---
def _clean_df_for_report(df, columns):
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    out = df.copy()
    for c in columns:
        if c not in out.columns:
            out[c] = ""
    return out[columns].fillna("")

def _report_table(df, columns, widths=None):
    """Convertit un DataFrame en tableau HTML compact pour la synthèse."""
    d = _clean_df_for_report(df, columns)
    if d.empty:
        return '<div class="report-empty">Aucune donnée renseignée.</div>'
    html = d.to_html(index=False, escape=True, classes="daily-report-table", border=0)
    return html

def build_daily_synthesis_excel(report_date, zone=None, global_data=None):
    """Construit un classeur Excel modifiable avec une feuille de synthèse fidèle au modèle fourni."""
    if global_data is None:
        diff, cells, dr, ins, deg, forms, plan = load(report_date, zone)
        scope = zone or "MARITIME"
    else:
        rep_g, cells, dr, ins, deg, forms, plan = global_data
        diff = ""
        scope = "MARITIME"

    # Copie des données pour éviter de modifier les DataFrames utilisés ailleurs.
    cells = cells.copy() if cells is not None else pd.DataFrame()
    dr = dr.copy() if dr is not None else pd.DataFrame()
    ins = ins.copy() if ins is not None else pd.DataFrame()
    deg = deg.copy() if deg is not None else pd.DataFrame()
    forms = forms.copy() if forms is not None else pd.DataFrame()

    # En consolidé, conserver la zone dans le nom du site pour faciliter la lecture.
    if global_data is not None:
        if 'ZONE' in cells.columns:
            cells['SITE'] = cells.apply(lambda x: f"{x.get('ZONE','')} - {x.get('SITE','')}".strip(' -'), axis=1)
            cells.drop(columns=['ZONE'], inplace=True, errors='ignore')
        if 'ZONE' in dr.columns:
            dr['SITE'] = dr.apply(lambda x: f"{x.get('ZONE','')} - {x.get('SITE','')}".strip(' -'), axis=1)
            dr.drop(columns=['ZONE'], inplace=True, errors='ignore')

    cells_cols = ['SITE','2G','3G','4G','5G','OBSERVATION','STATUT']
    dr_cols = ['SITE','SITES IMPACTÉS','DR2','ESCALADE','ÉVITABLE ?','POINT BLOQUANT','STATUT']
    ins_cols = ['BASES','INSTALLATIONS','DÉRANGEMENTS','POINTS BLOQUANTS']
    deg_cols = ['SITE NAME','2G','3G','4G','DISPONIBILITÉ','BASE']
    form_cols = ['BASE','INTITULÉ','NOTIONS VUES']

    def clean(df, cols):
        if df.empty:
            return pd.DataFrame(columns=cols)
        d = df.copy()
        for c in cols:
            if c not in d.columns:
                d[c] = ''
        return d[cols].fillna('')

    cells = clean(cells, cells_cols)
    dr = clean(dr, dr_cols)
    ins = clean(ins, ins_cols)
    deg = clean(deg, deg_cols)
    forms = clean(forms, form_cols)

    total_cells = int(cells[['2G','3G','4G','5G']].apply(pd.to_numeric, errors='coerce').fillna(0).sum().sum()) if not cells.empty else 0
    total_dr2 = int((dr['DR2'].astype(str).str.upper() == 'OUI').sum()) if not dr.empty else 0

    # Ajout de la date dans les tableaux comme sur le modèle fourni.
    cells_export = cells.copy()
    cells_export.insert(0, 'DATE', report_date)
    dr_export = dr.copy()
    dr_export.insert(0, 'DATE', report_date)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        wb = writer.book
        ws = wb.add_worksheet('Synthèse Journalière')
        writer.sheets['Synthèse Journalière'] = ws

        # Formats proches du modèle : bleu marine / jaune / bleu clair.
        navy = '#12396F'
        yellow = '#FFF500'
        light_blue = '#DCE9F7'
        pale_green = '#E2F0D9'
        white = '#FFFFFF'
        border = '#777777'

        fmt_title = wb.add_format({'bold': True, 'font_color': white, 'bg_color': navy, 'font_size': 16, 'align': 'left', 'valign': 'vcenter'})
        fmt_date = wb.add_format({'bold': True, 'font_color': navy, 'bg_color': white, 'font_size': 12, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'border_color': border})
        fmt_section = wb.add_format({'bold': True, 'font_color': white, 'bg_color': navy, 'font_size': 12, 'align': 'left', 'valign': 'vcenter'})
        fmt_head = wb.add_format({'bold': True, 'bg_color': yellow, 'font_color': '#111111', 'border': 1, 'border_color': border, 'align': 'center', 'valign': 'vcenter'})
        fmt_cell = wb.add_format({'border': 1, 'border_color': border, 'align': 'center', 'valign': 'vcenter'})
        fmt_text = wb.add_format({'border': 1, 'border_color': border, 'align': 'left', 'valign': 'vcenter'})
        fmt_total = wb.add_format({'bold': True, 'bg_color': light_blue, 'border': 1, 'border_color': border, 'align': 'center', 'valign': 'vcenter'})
        fmt_total_value = wb.add_format({'bold': True, 'font_size': 14, 'font_color': navy, 'bg_color': light_blue, 'border': 1, 'border_color': border, 'align': 'center', 'valign': 'vcenter'})
        fmt_kpi_label = wb.add_format({'bold': True, 'font_color': '#3D7E4B', 'bg_color': pale_green, 'border': 1, 'border_color': '#B7C7B0', 'align': 'center', 'valign': 'vcenter'})
        fmt_kpi_value = wb.add_format({'bold': True, 'font_size': 14, 'font_color': navy, 'bg_color': light_blue, 'border': 1, 'border_color': '#B7C7D9', 'align': 'center', 'valign': 'vcenter'})
        fmt_diff = wb.add_format({'border': 1, 'border_color': border, 'text_wrap': True, 'valign': 'top', 'align': 'left'})

        ws.hide_gridlines(2)
        ws.set_zoom(85)
        ws.set_column('A:A', 16)
        ws.set_column('B:B', 20)
        ws.set_column('C:G', 14)
        ws.set_column('H:H', 18)
        ws.set_column('I:I', 18)

        # En-tête.
        ws.merge_range('A1:H2', 'SYNTHÈSE JOURNALIÈRE MOBILE – MARITIME', fmt_title)
        ws.merge_range('I1:J2', f'DATE\n{report_date}', fmt_date)
        ws.set_row(0, 24); ws.set_row(1, 24)

        row = 3
        def write_section(title):
            nonlocal row
            ws.merge_range(row, 0, row, 9, title, fmt_section)
            ws.set_row(row, 22)
            row += 1

        def write_df(df, widths=None):
            nonlocal row
            for j, col in enumerate(df.columns):
                ws.write(row, j, col, fmt_head)
            row += 1
            if df.empty:
                ws.merge_range(row, 0, row, max(0, len(df.columns)-1), 'Aucune donnée renseignée.', fmt_cell)
                row += 2
                return
            for vals in df.itertuples(index=False, name=None):
                for j, val in enumerate(vals):
                    fmt = fmt_text if j in [0, len(df.columns)-1] else fmt_cell
                    ws.write(row, j, '' if pd.isna(val) else val, fmt)
                row += 1
            row += 1

        write_section('1. CELLS DOWN')
        write_df(cells_export)
        ws.write(row, 0, 'Σ', fmt_section)
        ws.merge_range(row, 1, row, 6, 'TOTAL CELLS DOWN', fmt_total)
        ws.merge_range(row, 7, row, 9, total_cells, fmt_total_value)
        row += 2

        write_section('2. DR2 J-1')
        write_df(dr_export)
        ws.merge_range(row, 0, row, 4, 'TOTAL CELLS DOWN', fmt_kpi_label)
        ws.write(row, 5, total_cells, fmt_kpi_value)
        ws.merge_range(row, 6, row, 8, 'DR2', fmt_kpi_label)
        ws.write(row, 9, total_dr2, fmt_kpi_value)
        row += 2

        write_section('3. Difficultés en cours pour faciliter le travail')
        ws.merge_range(row, 0, row+3, 9, diff if diff else 'Aucune difficulté signalée.', fmt_diff)
        row += 5

        write_section('4. Instances')
        write_df(ins)

        write_section('5. Tops Sites Dégradé J-1')
        write_df(deg)

        write_section("6. Formations de Partage d'expérience")
        write_df(forms)

        ws.freeze_panes(3, 0)
        ws.set_landscape()
        ws.fit_to_pages(1, 0)
        ws.set_margins(left=0.25, right=0.25, top=0.35, bottom=0.35)
        ws.print_area(0, 0, row, 9)

        # Feuilles détaillées modifiables.
        details = {
            'Cells Down': cells_export,
            'DR2 J-1': dr_export,
            'Instances': ins,
            'Sites Dégradés': deg,
            'Formations': forms,
        }
        for sheet, df in details.items():
            df.to_excel(writer, sheet_name=sheet, index=False)
            sw = writer.sheets[sheet]
            sw.freeze_panes(1, 0)
            sw.autofilter(0, 0, max(len(df), 1), max(len(df.columns)-1, 0))
            sw.set_row(0, 22, wb.add_format({'bold': True, 'bg_color': yellow, 'border': 1, 'align': 'center'}))
            sw.set_column(0, max(len(df.columns)-1, 0), 18)

    return output.getvalue()


def render_daily_synthesis(report_date, zone=None, global_data=None):
    """Met uniquement à disposition le téléchargement Excel modifiable de la synthèse."""
    excel_data = build_daily_synthesis_excel(report_date, zone=zone, global_data=global_data)
    st.download_button(
        '📥 Télécharger la Synthèse Journalière – Excel modifiable',
        data=excel_data,
        file_name=f'Synthese_Mobile_Maritime_{report_date.replace("/", "-")}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        type='primary',
        use_container_width=True
    )



# --- V3 : OUTILS DE PILOTAGE SIMPLES ---
def _report_status_for_zone(report_date, zone):
    d = qdf("SELECT submitted_at FROM reports WHERE report_date=? AND zone=? ORDER BY id DESC LIMIT 1", (report_date, zone))
    if d.empty:
        return "🔴 Non soumis", "—"
    return "🟢 Soumis", str(d.iloc[0].get('submitted_at') or '—')


def _validate_zone_data(cells, dr, ins, deg, forms):
    """Retourne une liste courte des anomalies de saisie visibles avant soumission."""
    problems = []
    checks = [
        (cells, 'SITE', 'Cells Down'),
        (dr, 'SITE', 'DR2'),
        (ins, 'BASES', 'Instances'),
        (deg, 'SITE NAME', 'Sites dégradés'),
        (forms, 'BASE', 'Formations'),
    ]
    for df, required_col, label in checks:
        if df is None or df.empty or required_col not in df.columns:
            continue
        for idx, row_check in df.iterrows():
            vals = [str(v).strip() for v in row_check.tolist() if pd.notna(v) and str(v).strip() not in ('', '0', '0.0')]
            if vals and not str(row_check.get(required_col, '')).strip():
                problems.append(f"{label} — ligne {idx + 1} : champ « {required_col} » manquant")
    return problems


def _render_zone_home_dashboard(report_date, zone, cells, dr, ins, deg):
    status, submitted_at = _report_status_for_zone(report_date, zone)
    total_cells = int(cells[['2G','3G','4G','5G']].apply(pd.to_numeric, errors='coerce').fillna(0).sum().sum()) if cells is not None and not cells.empty else 0
    total_dr2 = int((dr['DR2'].fillna('').astype(str).str.upper() == 'OUI').sum()) if dr is not None and not dr.empty and 'DR2' in dr.columns else 0
    total_ins = len(ins) if ins is not None else 0
    total_deg = len(deg) if deg is not None else 0
    st.markdown('<div class="section-title">🏠 TABLEAU DE BORD DU JOUR</div>', unsafe_allow_html=True)
    st.caption(f"Zone : {zone} • Date : {report_date} • Statut actuel : {status} • Dernière soumission : {submitted_at}")
    h1, h2, h3, h4 = st.columns(4)
    h1.metric('🚨 Cells Down', total_cells)
    h2.metric('📌 DR2', total_dr2)
    h3.metric('⚙️ Instances', total_ins)
    h4.metric('📉 Sites dégradés', total_deg)


def _render_supervisor_status_dashboard(report_date):
    rows = []
    for zone in ZONES:
        status, submitted_at = _report_status_for_zone(report_date, zone)
        rows.append({'ZONE': zone, 'RAPPORT': status, 'DERNIÈRE SOUMISSION': submitted_at})
    status_df = pd.DataFrame(rows)
    st.markdown('<div class="section-title">🏠 SUIVI DES RAPPORTS PAR ZONE</div>', unsafe_allow_html=True)
    st.dataframe(status_df, use_container_width=True, hide_index=True)

# --- MODE ZONE ---
if ROLE == 'ZONE':
    diff, cells0, dr0, ins0, deg0, forms0, plan0 = load(r, ZONE)
    _copied = st.session_state.get('copy_previous_data')
    if _copied and _copied.get('date') == r:
        diff = _copied.get('diff', diff)
        cells0 = _copied.get('cells', cells0).copy()
        dr0 = _copied.get('dr', dr0).copy()
        ins0 = _copied.get('ins', ins0).copy()
        deg0 = _copied.get('deg', deg0).copy()
        forms0 = _copied.get('forms', forms0).copy()
        st.session_state.pop('copy_previous_data', None)
        st.success(f'✅ Les données du {(_copied.get("date") and (dt_selected - timedelta(days=1)).strftime("%d/%m/%Y"))} ont été reprises. Vérifiez-les avant soumission.')
    if ins0.empty: ins0 = pd.DataFrame({'BASES': [ZONE], 'INSTALLATIONS': [0], 'DÉRANGEMENTS': [0], 'POINTS BLOQUANTS': ['']})
    if forms0.empty: forms0 = pd.DataFrame({'BASE': [ZONE], 'INTITULÉ': [''], 'NOTIONS VUES': ['']})

    # Le tableau de bord de zone est affiché en bas de l'espace Zone.

    st.sidebar.markdown("""
    <div class="sidebar-brand">
      <div class="brand-icon">📡</div>
      <div class="brand-title">YAS DFO-SRTM</div>
      <div class="brand-subtitle">HUB OPÉRATIONNEL MARITIME</div>
    </div>
    <div class="sidebar-section-label">Navigation • Zone</div>
    """, unsafe_allow_html=True)
    zone_menu = st.sidebar.radio(
        "Sous-menus",
        ["🚨 Rapport du jour", "🗓️ Planning", "🧠 Formations polyvalentes ", "🚀 Vérifier & Soumettre"],
        key="zone_menu_desktop",
        label_visibility="collapsed",
        on_change=_desktop_zone_navigation_changed
    )
    if st.session_state.get("yas_mobile_nav_override") and st.session_state.get("yas_mobile_choice") in ["🚨 Rapport du jour", "🗓️ Planning", "🧠 Formations polyvalentes ", "🚀 Vérifier & Soumettre"]:
        zone_menu = st.session_state.get("yas_mobile_choice", zone_menu)
    # Tableau de bord intégré directement dans le carré « ESPACE ZONE ».
    _zone_status, _zone_submitted_at = _report_status_for_zone(r, ZONE)
    _dash_cells = int(cells0[['2G','3G','4G','5G']].apply(pd.to_numeric, errors='coerce').fillna(0).sum().sum()) if cells0 is not None and not cells0.empty else 0
    _dash_dr2 = int((dr0['DR2'].fillna('').astype(str).str.upper() == 'OUI').sum()) if dr0 is not None and not dr0.empty and 'DR2' in dr0.columns else 0
    _dash_ins = len(ins0) if ins0 is not None else 0
    _dash_deg = len(deg0) if deg0 is not None else 0
    _zone_status_safe = html.escape(str(_zone_status))
    _zone_submitted_safe = html.escape(str(_zone_submitted_at))
    st.sidebar.markdown(f'''    <div class="zone-space-card">
      <div class="zone-space-head">
        <div class="zone-space-icon">👤</div>
        <div>
          <div class="zone-space-title">ESPACE ZONE</div>
          <div class="zone-space-subtitle">📍 {html.escape(str(ZONE))} · 📅 {html.escape(str(r))}</div>
        </div>
      </div>
      <div class="zone-space-status">
        <span>ÉTAT DU RAPPORT</span><strong>{_zone_status_safe}</strong>
      </div>
      <div class="zone-dashboard-label">TABLEAU DE BORD</div>
      <div class="zone-dashboard-grid">
        <div class="zone-kpi"><span>🚨</span><b>{_dash_cells}</b><small>Cells</small></div>
        <div class="zone-kpi"><span>📌</span><b>{_dash_dr2}</b><small>DR2</small></div>
        <div class="zone-kpi"><span>⚙️</span><b>{_dash_ins}</b><small>Instances</small></div>
        <div class="zone-kpi"><span>📉</span><b>{_dash_deg}</b><small>Dégradés</small></div>
      </div>
      <div class="zone-space-footer">Dernière soumission : <strong>{_zone_submitted_safe}</strong></div>
    </div>
    ''', unsafe_allow_html=True)

    # ------------------------------------------------------------------
    # BROUILLON PERSISTANT ENTRE LES SOUS-MENUS
    # ------------------------------------------------------------------
    # Streamlit peut supprimer l'état d'un widget lorsqu'il n'est plus rendu
    # (navigation if/elif). On conserve donc explicitement chaque tableau et
    # chaque texte dans session_state, avec un contexte unique DATE + ZONE.
    # Ainsi, l'utilisateur peut aller de Rapport -> Planning -> REX ->
    # Vérifier & Soumettre puis revenir en arrière sans perdre ses saisies.
    _draft_context = f"{ROLE}|{ZONE}|{r}"
    _draft_context_id = hashlib.md5(_draft_context.encode('utf-8')).hexdigest()[:12]

    if st.session_state.get('_draft_context') != _draft_context:
        st.session_state['_draft_context'] = _draft_context
        st.session_state['cells_data'] = cells0.copy()
        st.session_state['dr_data'] = dr0.copy()
        st.session_state['ins_data'] = ins0.copy()
        st.session_state['deg_data'] = deg0.copy()
        st.session_state['forms_data'] = forms0.copy()
        st.session_state['diff_data'] = diff or ''
        st.session_state['edited_pivot'] = get_monthly_pivot_df(dt_selected.year, dt_selected.month, ZONE).copy()

    def _stored_df(name, fallback):
        value = st.session_state.get(name)
        return value.copy() if isinstance(value, pd.DataFrame) else fallback.copy()

    # NOTE UX: les éditeurs utilisent maintenant directement leur DataFrame retourné.
    # Cela évite un second rerun via on_change qui pouvait faire sauter la sélection
    # visuelle d'une cellule/colonne pendant la saisie.
    def _sync_data_editor(widget_key, data_key):
        """Synchronise immédiatement les modifications d'un st.data_editor.

        Streamlit peut déclencher le rerun avant que le DataFrame retourné ne soit
        réutilisé par le menu suivant. Le callback lit donc directement l'état
        natif du widget (edited_rows / added_rows / deleted_rows) et le fusionne
        dans le brouillon persistant. Cela évite de devoir saisir une donnée une
        deuxième fois, notamment dans les lignes nouvellement ajoutées.
        """
        base = st.session_state.get(data_key)
        if not isinstance(base, pd.DataFrame):
            base = pd.DataFrame()
        else:
            base = base.copy()

        state = st.session_state.get(widget_key)
        if isinstance(state, dict):
            # Modifications de cellules existantes.
            for row_idx, changes in state.get('edited_rows', {}).items():
                try:
                    row_idx = int(row_idx)
                except (TypeError, ValueError):
                    continue
                if 0 <= row_idx < len(base):
                    for col, value in changes.items():
                        if col not in base.columns:
                            base[col] = ''
                        base.at[base.index[row_idx], col] = value

            # Nouvelles lignes saisies dans num_rows='dynamic'.
            for row in state.get('added_rows', []):
                if isinstance(row, dict):
                    new_row = {col: '' for col in base.columns}
                    new_row.update(row)
                    base = pd.concat([base, pd.DataFrame([new_row])], ignore_index=True)

            # Lignes supprimées.
            deleted = state.get('deleted_rows', [])
            if deleted:
                valid_deleted = []
                for idx in deleted:
                    try:
                        idx = int(idx)
                    except (TypeError, ValueError):
                        continue
                    if 0 <= idx < len(base):
                        valid_deleted.append(idx)
                if valid_deleted:
                    base = base.drop(base.index[valid_deleted]).reset_index(drop=True)

        st.session_state[data_key] = base.copy()


    cells = _stored_df('cells_data', cells0)
    dr = _stored_df('dr_data', dr0)
    ins = _stored_df('ins_data', ins0)
    deg = _stored_df('deg_data', deg0)
    forms = _stored_df('forms_data', forms0)
    difficulties = st.session_state.get('diff_data', diff or '')

    # Valeurs conservées même lorsque le menu Planning n'est pas rendu.
    weekend_month = st.session_state.get('weekend_month', dt_selected.month)
    m_month = st.session_state.get('monthly_month_zone_simple', dt_selected.month)
    m_year = st.session_state.get('monthly_year_zone_simple', dt_selected.year)
    edited_pivot = st.session_state.get('edited_pivot', get_monthly_pivot_df(m_year, m_month, ZONE)).copy()

    st.caption('📝 Brouillon conservé automatiquement pendant la navigation — vos saisies restent disponibles avant la soumission.')

    if zone_menu == "🚨 Rapport du jour":
        st.markdown('<div class="section-title">🚨 1. CELLS DOWN — incidents réseau</div>', unsafe_allow_html=True)
        st.caption("Ajoutez une ligne uniquement pour un site impacté. Les colonnes 2G/3G/4G/5G servent à compter les cellules hors service.")
        cells_editor_df = cells.copy() if not cells.empty else pd.DataFrame(columns=['SITE','2G','3G','4G','5G','OBSERVATION','STATUT'])
        # Supprime toute colonne vide/Unnamed avant SITE dans Cells Down.
        cells_editor_df = cells_editor_df.loc[
            :,
            ~cells_editor_df.columns.astype(str).str.strip().str.lower().isin(['', 'unnamed: 0', 'unnamed'])
        ].copy()
        # Garantit que SITE est bien la première colonne affichée.
        cells_order = ['SITE', '2G', '3G', '4G', '5G', 'OBSERVATION', 'STATUT']
        for _col in cells_order:
            if _col not in cells_editor_df.columns:
                cells_editor_df[_col] = ''
        cells_editor_df = cells_editor_df[cells_order]
        if 'STATUT' in cells_editor_df.columns:
            cells_editor_df['STATUT'] = cells_editor_df['STATUT'].replace({'UP': '🟢 UP', 'DOWN': '🔴 DOWN'})
        cells = st.data_editor(
                cells_editor_df,
                num_rows='dynamic', use_container_width=True, hide_index=True,
                column_config={
                    '2G': st.column_config.NumberColumn(min_value=0, step=1),
                    '3G': st.column_config.NumberColumn(min_value=0, step=1),
                    '4G': st.column_config.NumberColumn(min_value=0, step=1),
                    '5G': st.column_config.NumberColumn(min_value=0, step=1),
                    'STATUT': st.column_config.SelectboxColumn(options=STATUS_DISPLAY, required=False)
                }, key=f'cells_editor_{_draft_context_id}'
            )
        if 'STATUT' in cells.columns:
            cells['STATUT'] = cells['STATUT'].replace({'🟢 UP': 'UP', '🔴 DOWN': 'DOWN'})
        st.session_state['cells_data'] = cells.copy()
        if not cells.empty:
            # Les cellules ajoutées dans data_editor peuvent être vides ("").
            # On convertit proprement les colonnes numériques avant le calcul.
            for _col in ['2G', '3G', '4G', '5G']:
                if _col in cells.columns:
                    cells[_col] = pd.to_numeric(cells[_col], errors='coerce').fillna(0)
            total = int(cells[['2G','3G','4G','5G']].sum().sum())
        else:
            total = 0

        st.metric('TOTAL CELLS DOWN', total)

        st.markdown('<div class="section-title" style="margin-top:25px;">📌 2. DR2 J-1 — suivi des incidents</div>', unsafe_allow_html=True)
        dr_editor_df = dr.copy() if not dr.empty else pd.DataFrame(columns=['SITE','SITES IMPACTÉS','DR2','ESCALADE','ÉVITABLE ?','POINT BLOQUANT','STATUT'])
        # Nettoyage des anciennes valeurs : « À confirmer » n'est plus proposé.
        for _col in ['DR2', 'ÉVITABLE ?']:
            if _col in dr_editor_df.columns:
                dr_editor_df[_col] = dr_editor_df[_col].replace({'À confirmer': '', 'à confirmer': ''})
        if 'STATUT' in dr_editor_df.columns:
            dr_editor_df['STATUT'] = dr_editor_df['STATUT'].replace({'UP': '🟢 UP', 'DOWN': '🔴 DOWN'})
        dr = st.data_editor(
                dr_editor_df,
                num_rows='dynamic', use_container_width=True, hide_index=True,
                column_config={
                    # DR2 : uniquement OUI / NON
                    'DR2': st.column_config.SelectboxColumn(options=YESNO),
                    # ESCALADE : aucune liste déroulante, saisie libre
                    'ESCALADE': st.column_config.TextColumn(),
                    # ÉVITABLE ? : uniquement OUI / NON
                    'ÉVITABLE ?': st.column_config.SelectboxColumn(options=YESNO),
                    'STATUT': st.column_config.SelectboxColumn(options=STATUS_DISPLAY, required=False)
                }, key=f'dr_editor_{_draft_context_id}'
            )
        if 'STATUT' in dr.columns:
            dr['STATUT'] = dr['STATUT'].replace({'🟢 UP': 'UP', '🔴 DOWN': 'DOWN'})
        for _col in ['DR2', 'ÉVITABLE ?']:
            if _col in dr.columns:
                dr[_col] = dr[_col].replace({'À confirmer': '', 'à confirmer': ''})
        st.session_state['dr_data'] = dr.copy()

        st.markdown('<div class="section-title" style="margin-top:25px;">💬 3. DIFFICULTÉS — ce qui bloque le travail</div>', unsafe_allow_html=True)
        difficulties = st.text_area(
            '',
            value=difficulties or '',
            placeholder="Précisez les pannes d'énergie, coupures FH, blocages d'accès...",
            height=100,
            key=f'diff_{_draft_context_id}'
        )
        st.session_state['diff_data'] = difficulties or ''

        st.markdown('<div class="section-title" style="margin-top:20px;">⚙️ 4. INSTANCES — suivi opérationnel</div>', unsafe_allow_html=True)
        ins = st.data_editor(ins, num_rows='dynamic', use_container_width=True, hide_index=True, key=f'ins_editor_{_draft_context_id}')
        st.session_state['ins_data'] = ins.copy()

        st.markdown('<div class="section-title" style="margin-top:20px;">📉 5. SITES DÉGRADÉS — qualité réseau</div>', unsafe_allow_html=True)
        deg = st.data_editor(deg if not deg.empty else pd.DataFrame(columns=['SITE NAME','2G','3G','4G','DISPONIBILITÉ','BASE']), num_rows='dynamic', use_container_width=True, hide_index=True, key=f'deg_editor_{_draft_context_id}')
        st.session_state['deg_data'] = deg.copy()

        render_daily_synthesis(r, zone=ZONE)

    elif zone_menu == "🗓️ Planning":
        st.markdown('<div class="section-title">🗓️ PLANNING — mensuel & permanences</div>', unsafe_allow_html=True)
        st.caption("Choisissez le mois, générez le planning si nécessaire, puis utilisez « Modifier une affectation » pour une correction ponctuelle.")
        st.markdown('''<div class="legend-box"><b style="background:#FFD84D;padding:4px 8px;border-radius:5px;color:#111;">PJ</b> Jour &nbsp; <b style="background:#F6A623;padding:4px 8px;border-radius:5px;color:#111;">PN</b> Nuit &nbsp; <b style="background:#8BE28B;padding:4px 8px;border-radius:5px;color:#111;">A</b> Astreinte &nbsp; <b style="background:#C8EEFF;padding:4px 8px;border-radius:5px;color:#123A63;">🟦</b> Week-end &nbsp; <b style="background:#FFC7CE;padding:4px 8px;border-radius:5px;color:#8B1E2D;">🎉</b> Jour férié</div>''', unsafe_allow_html=True)

        # ---------------------------
        # PERMANENCES WEEK-END
        # ---------------------------
        st.markdown('<div class="section-title" style="margin-top:15px;">🛠️ PERMANENCES DE WEEK-END PAR BASE</div>', unsafe_allow_html=True)
        wb1, wb2 = st.columns([2, 3])
        with wb1:
            weekend_month = st.selectbox('Mois des week-ends', range(1, 13), index=dt_selected.month - 1, key='weekend_month')
        weekends = weekend_dates(dt_selected.year, weekend_month)
        with wb2:
            selected_weekend = st.selectbox(
                'Week-end à gérer', weekends or [date(dt_selected.year, weekend_month, 1)],
                format_func=lambda d: f"Week-end du {d.strftime('%d/%m/%Y')} au {(d + pd.Timedelta(days=1).to_pytimedelta()).strftime('%d/%m/%Y')}",
                key='selected_weekend'
            )

        bases_options = get_bases_for_zone(r, ZONE)
        st.caption("Chaque agent peut être affecté à une base. Les chauffeurs peuvent être ajoutés directement dans le tableau.")
        weekend_key = f"weekend_{ZONE}_{selected_weekend.strftime('%Y%m%d')}"
        if weekend_key not in st.session_state:
            st.session_state[weekend_key] = get_weekend_permanence_df(dt_selected.year, weekend_month, selected_weekend, ZONE)

        # Tableau simplifié : NOM, PRÉNOMS, JOUR, NUIT et ASTREINTE.
        # BASE / TYPE / MATRICULE restent conservés en interne pour la sauvegarde.
        old_weekend = st.session_state[weekend_key].copy()
        weekend_editor_df = old_weekend.reindex(columns=['NOM', 'PRÉNOMS', 'JOUR', 'NUIT', 'ASTREINTE']).copy()

        weekend_edit_df = st.data_editor(
            weekend_editor_df,
            num_rows='fixed',
            use_container_width=True,
            hide_index=True,
            column_config={
                'NOM': st.column_config.TextColumn('NOM', width='medium'),
                'PRÉNOMS': st.column_config.TextColumn('PRÉNOMS', width='large'),
                'JOUR': st.column_config.SelectboxColumn('JOUR', options=WEEKEND_SHIFT_OPTIONS, width='small'),
                'NUIT': st.column_config.SelectboxColumn('NUIT', options=WEEKEND_SHIFT_OPTIONS, width='small'),
                'ASTREINTE': st.column_config.SelectboxColumn('ASTREINTE', options=WEEKEND_SHIFT_OPTIONS, width='small'),
            },
            key=f'editor_{weekend_key}'
        )

        # On réinjecte les 5 colonnes affichées dans la structure complète
        # avant les métriques, la sauvegarde et l'export.
        weekend_df = old_weekend.copy()
        for col in ['NOM', 'PRÉNOMS', 'JOUR', 'NUIT', 'ASTREINTE']:
            if col not in weekend_df.columns:
                weekend_df[col] = ''
            if col in weekend_edit_df.columns:
                values = weekend_edit_df[col].tolist()
                for i, value in enumerate(values):
                    if i < len(weekend_df):
                        weekend_df.at[weekend_df.index[i], col] = value
        st.session_state[weekend_key] = weekend_df

        wc1, wc2, wc3 = st.columns(3)
        wc1.metric('👷 Techniciens', int((weekend_df.get('TYPE', pd.Series(dtype=str)).astype(str).str.upper() == 'TECHNICIEN').sum()))
        wc2.metric('🚗 Chauffeurs', int((weekend_df.get('TYPE', pd.Series(dtype=str)).astype(str).str.upper() == 'CHAUFFEUR').sum()))
        wc3.metric('📍 Bases couvertes', weekend_df['BASE'].astype(str).replace('', pd.NA).dropna().nunique() if not weekend_df.empty else 0)

        if not weekend_df.empty:
            wcsv = weekend_df.to_csv(index=False).encode('utf-8-sig')
        else:
            wcsv = b''
        w1, w2 = st.columns(2)
        with w1:
            if st.button('💾 Enregistrer ce week-end', type='primary', use_container_width=True, key=f'save_{weekend_key}'):
                save_weekend_permanence_df(weekend_df, dt_selected.year, weekend_month, selected_weekend, ZONE)
                st.success('Permanences du week-end enregistrées.')
        with w2:
            st.download_button(
                '📥 Télécharger les permanences – Excel',
                data=export_weekend_permanence_excel(dt_selected.year, weekend_month, ZONE, selected_weekend, weekend_df),
                file_name=f"Permanences_Weekend_{ZONE}_{selected_weekend.strftime('%d-%m-%Y')}.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True
            )

        # ---------------------------
        # PLANNING MENSUEL — VERSION TRÈS SIMPLE
        # ---------------------------
        st.markdown('<div class="planning-card">', unsafe_allow_html=True)
        st.markdown('<div class="planning-header">🗓️ PLANNING MENSUEL</div>', unsafe_allow_html=True)

        # 1) Choix du mois
        pm1, pm2, pm3 = st.columns([1.5, 1.2, 3.3])
        with pm1:
            m_month = st.selectbox('📅 Mois', range(1, 13), index=dt_selected.month - 1, key='monthly_month_zone_simple')
        with pm2:
            m_year = st.number_input('Année', min_value=2025, max_value=2035, value=dt_selected.year, key='monthly_year_zone_simple')
        with pm3:
            st.markdown('<div style="padding-top:28px;color:#12396F;font-weight:800;">Choisir un agent → définir PJ / PN / A → générer.</div>', unsafe_allow_html=True)

        agents_zone = DEFAULT_AGENTS.get(ZONE, [])
        agent_labels = [f'{a.get("Nom", "")} {a.get("Prénoms", "")}'.strip() for a in agents_zone]
        label_to_agent = {label: a for label, a in zip(agent_labels, agents_zone)}

        # 2) Programmation compacte (un seul bloc)
        with st.expander('⚙️ Programmer un agent', expanded=True):
            if agent_labels:
                selected_label = st.selectbox('👤 Agent', agent_labels, key='monthly_program_agent_simple2')
                selected_agent = label_to_agent[selected_label]
                cfg = get_agent_monthly_schedule_config(m_year, m_month, ZONE, selected_agent.get('Matricule', '-'))

                p1, p2, p3, p4 = st.columns([1, 1, 1, 1.4])
                with p1:
                    agent_pj = st.number_input('🟨 PJ', 0, 31, cfg['PJ'], key='agent_pj_simple2')
                with p2:
                    agent_pn = st.number_input('🟧 PN', 0, 31, cfg['PN'], key='agent_pn_simple2')
                with p3:
                    agent_a = st.number_input('🟩 A', 0, 31, cfg['A'], key='agent_a_simple2')
                with p4:
                    st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
                    save_prog = st.button('💾 Enregistrer', type='primary', use_container_width=True, key='save_agent_simple2')

                if save_prog:
                    save_agent_monthly_schedule_config(m_year, m_month, ZONE, selected_agent, agent_pj, agent_pn, agent_a)
                    st.success(f'Programmation enregistrée pour {selected_label}.')
                    st.rerun()

                st.caption(f'PJ {agent_pj} • PN {agent_pn} • A {agent_a} • Total : {agent_pj + agent_pn + agent_a} gardes')
            else:
                st.warning('Aucun agent disponible dans cette zone.')

        # 3) Génération + planning coloré
        action1, action2, action3 = st.columns([1.4, 1.4, 4.2])
        with action1:
            generate_clicked = st.button('✨ Générer', type='primary', use_container_width=True, key='generate_simple2')
        with action2:
            refresh_clicked = st.button('🔄 Actualiser l’affichage', use_container_width=True, key='refresh_simple2')
        with action3:
            st.markdown('<div style="padding:8px 0;color:#64748B;font-size:12px;">La génération utilise les programmations enregistrées pour chaque agent.</div>', unsafe_allow_html=True)

        if generate_clicked:
            generate_monthly_schedule(m_year, m_month, ZONE, force=True, config=get_monthly_schedule_config(m_year, m_month, ZONE))
            st.success('Planning généré.')
            st.rerun()
        if refresh_clicked:
            st.rerun()

        pivot_df = get_monthly_pivot_df(m_year, m_month, ZONE)
        days_cols = [f'{d:02d}' for d in range(1, calendar.monthrange(int(m_year), int(m_month))[1] + 1)]

        # Filtre unique : tous les agents ou un agent
        fc1, fc2 = st.columns([2, 5])
        with fc1:
            display_agent = st.selectbox('👁️ Afficher', ['Tous les agents'] + agent_labels, key='planning_display_agent_simple2')
        with fc2:
            st.markdown('<div style="padding-top:28px;color:#64748B;font-size:12px;">🟨 PJ = jour &nbsp; 🟧 PN = nuit &nbsp; 🟩 A = astreinte &nbsp; 🟦 week-end &nbsp; 🎉 férié</div>', unsafe_allow_html=True)

        # Afficher le matricule en premier dans le planning mensuel.
        agent_matricules = {
            (str(a.get('Nom','')), str(a.get('Prénoms',''))): a.get('Matricule', '-')
            for a in agents_zone
        }
        planning_display = pivot_df.copy()
        if 'MATRICULE' not in planning_display.columns:
            planning_display.insert(0, 'MATRICULE', [
                agent_matricules.get((str(n), str(p)), '-')
                for n, p in zip(planning_display['NOM'], planning_display['PRÉNOMS'])
            ])
        planning_display = planning_display[['MATRICULE', 'NOM', 'PRÉNOMS', 'FONCTION'] + days_cols].copy()
        if display_agent != 'Tous les agents':
            ag = label_to_agent[display_agent]
            planning_display = planning_display[(planning_display['NOM'] == ag.get('Nom', '')) & (planning_display['PRÉNOMS'] == ag.get('Prénoms', ''))].copy()

        render_colorized_planning_html(planning_display, int(m_year), int(m_month), days_cols, title='Planning')

        # 4) Modification rapide : 3 choix seulement
        with st.expander('✏️ Modifier une affectation', expanded=False):
            if agent_labels:
                edit_label = st.selectbox('Agent', agent_labels, key='edit_agent_simple2')
                edit_agent = label_to_agent[edit_label]
                e1, e2 = st.columns(2)
                with e1:
                    edit_day = st.selectbox('Date', range(1, len(days_cols) + 1), format_func=lambda d: f'{d:02d}/{m_month:02d}/{m_year}', key='edit_day_simple2')
                with e2:
                    existing_role = 'SN'
                    hit = pivot_df[(pivot_df['NOM'] == edit_agent.get('Nom', '')) & (pivot_df['PRÉNOMS'] == edit_agent.get('Prénoms', ''))]
                    if not hit.empty:
                        existing_role = str(hit.iloc[0][f'{edit_day:02d}'])
                    edit_role = st.selectbox('Affectation', ROLES_SHORT, index=ROLES_SHORT.index(existing_role) if existing_role in ROLES_SHORT else 0, key='edit_role_simple2')
                if st.button('💾 Enregistrer la modification', type='primary', use_container_width=True, key='apply_edit_simple2'):
                    pivot_df.loc[(pivot_df['NOM'] == edit_agent.get('Nom', '')) & (pivot_df['PRÉNOMS'] == edit_agent.get('Prénoms', '')), f'{edit_day:02d}'] = edit_role
                    save_monthly_pivot_df(pivot_df, m_year, m_month, ZONE)
                    st.success('Affectation modifiée.')
                    st.rerun()

        # 5) Export
        ex1, ex2 = st.columns(2)
        with ex1:
            st.download_button('📥 Excel', data=export_monthly_excel(m_year, m_month, ZONE), file_name=f'Planning_{ZONE}_{m_year}_{m_month:02d}.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', use_container_width=True, key='download_monthly_excel_simple2')
        with ex2:
            st.download_button('📄 CSV', data=pivot_df.to_csv(index=False).encode('utf-8-sig'), file_name=f'Planning_{ZONE}_{m_year}_{m_month:02d}.csv', mime='text/csv', use_container_width=True, key='download_monthly_csv_simple2')

        st.markdown('</div>', unsafe_allow_html=True)

    elif zone_menu == "🧠 Formations polyvalentes ":
        st.markdown('<div class="section-title">🧠 PARTAGE D\'EXPÉRIENCE & SESSIONS</div>', unsafe_allow_html=True)

        st.markdown('### 📝 Retour d’expérience / Formation')
        forms = st.data_editor(forms, num_rows='dynamic', use_container_width=True, hide_index=True, key=f'forms_editor_{_draft_context_id}')
        st.session_state['forms_data'] = forms.copy()

        st.markdown('### 📸🎥 Photos & vidéos du retour d’expérience')
        st.caption('Ajoutez les photos et vidéos utiles pour documenter une intervention, une anomalie, une formation ou une bonne pratique. Les fichiers sont conservés avec le rapport de la zone et de la date sélectionnée.')
        rex_uploads = st.file_uploader(
            '📤 Envoyer des photos ou vidéos',
            type=['jpg','jpeg','png','webp','gif','mp4','mov','avi','mkv','webm','m4v'],
            accept_multiple_files=True,
            key=f'rex_media_uploader_{r}_{ZONE}'
        )
        if rex_uploads:
            allowed = [f for f in rex_uploads if _media_type_from_mime(f.type, f.name)]
            saved_count = save_rex_media(r, ZONE, allowed)
            if saved_count:
                st.success(f'✅ {saved_count} fichier(s) ajouté(s) au partage d’expérience.')

        media_rows = load_rex_media(r, ZONE)
        if media_rows:
            # ─────────────────────────────────────────────────────────────
            # GALERIE REX PRO
            # ─────────────────────────────────────────────────────────────
            st.markdown(f'#### 👁️ Galerie médias ({len(media_rows)})')

            # Indicateurs rapides.
            photo_count = sum(1 for m in media_rows if m[3] == 'image')
            video_count = sum(1 for m in media_rows if m[3] == 'video')
            total_size_mb = sum((m[5] or 0) for m in media_rows) / (1024 * 1024)
            k1, k2, k3 = st.columns(3)
            with k1:
                st.metric('📸 Photos', photo_count)
            with k2:
                st.metric('🎥 Vidéos', video_count)
            with k3:
                st.metric('💾 Volume', f'{total_size_mb:.1f} Mo')

            # Filtres de galerie.
            filter_cols = st.columns([2.2, 1, 1])
            with filter_cols[0]:
                media_search = st.text_input(
                    '🔍 Rechercher un média',
                    placeholder='Nom du fichier…',
                    key=f'rex_media_search_{ZONE}_{r}'
                ).strip().lower()
            with filter_cols[1]:
                media_filter = st.selectbox(
                    'Type',
                    ['Tous', '📸 Photos', '🎥 Vidéos'],
                    key=f'rex_media_type_filter_{ZONE}_{r}'
                )
            with filter_cols[2]:
                media_sort = st.selectbox(
                    'Tri',
                    ['Plus récent', 'Plus ancien', 'Nom A→Z'],
                    key=f'rex_media_sort_{ZONE}_{r}'
                )

            filtered_media_rows = list(media_rows)
            if media_search:
                filtered_media_rows = [m for m in filtered_media_rows if media_search in str(m[1]).lower()]
            if media_filter == '📸 Photos':
                filtered_media_rows = [m for m in filtered_media_rows if m[3] == 'image']
            elif media_filter == '🎥 Vidéos':
                filtered_media_rows = [m for m in filtered_media_rows if m[3] == 'video']

            if media_sort == 'Nom A→Z':
                filtered_media_rows.sort(key=lambda m: str(m[1]).lower())
            elif media_sort == 'Plus ancien':
                filtered_media_rows.sort(key=lambda m: str(m[7] or ''))
            else:
                filtered_media_rows.sort(key=lambda m: str(m[7] or ''), reverse=True)

            st.caption(f'Affichage : {len(filtered_media_rows)} média(s) sur {len(media_rows)}')

            st.markdown("""
            <style>
            /* Carte média : le popover ⋮ est remonté dans le coin supérieur droit. */
            .rex-media-wrap {
                position: relative;
                width: 100%;
            }
            div[data-testid="stPopover"] {
                position: relative;
                z-index: 50;
                margin-bottom: -48px;
                display: flex;
                justify-content: flex-end;
                pointer-events: auto;
            }
            div[data-testid="stPopover"] > button {
                min-height: 34px;
                width: 34px;
                padding: 0 !important;
                border-radius: 50%;
                background: rgba(7, 18, 28, 0.90) !important;
                border: 1px solid rgba(255,255,255,0.60) !important;
                color: #ffffff !important;
                font-size: 22px !important;
                font-weight: 900 !important;
                box-shadow: 0 3px 12px rgba(0,0,0,.50);
            }
            .rex-thumb-card {
                border: 1px solid rgba(128,128,128,.28);
                border-radius: 12px;
                padding: 6px;
                margin-bottom: 4px;
                background: rgba(128,128,128,.06);
            }
            .rex-thumb-video {
                aspect-ratio: 1 / 1;
                width: 100%;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: linear-gradient(135deg, #20252b, #454c55);
                color: white;
                font-size: 42px;
                position: relative;
            }
            .rex-thumb-video small {
                position: absolute;
                bottom: 8px;
                left: 0;
                right: 0;
                text-align: center;
                font-size: 12px;
                opacity: .85;
            }
            

            /* ===== DATA EDITOR : zéro animation pendant la saisie ===== */
            div[data-testid="stDataEditor"],
            div[data-testid="stDataEditor"] *,
            div[data-testid="stDataEditor"] [role="gridcell"],
            div[data-testid="stDataEditor"] [role="row"],
            div[data-testid="stDataEditor"] [role="columnheader"] {
                transition: none !important;
                animation: none !important;
            }

            /* ===== DATA EDITOR : focus discret ===== */
            /* Evite l'effet de changement d'etat trop marqué au clic. */
            div[data-testid="stDataEditor"] [role="gridcell"]:focus,
            div[data-testid="stDataEditor"] [role="gridcell"]:focus-within {
                outline: none !important;
                box-shadow: none !important;
            }
            div[data-testid="stDataEditor"] [role="gridcell"][aria-selected="true"] {
                background-color: transparent !important;
            }
            div[data-testid="stDataEditor"] [role="columnheader"]:focus,
            div[data-testid="stDataEditor"] [role="columnheader"]:focus-within {
                outline: none !important;
                box-shadow: none !important;
            }
</style>
            """, unsafe_allow_html=True)

            if not filtered_media_rows:
                st.info('🔎 Aucun média ne correspond aux filtres sélectionnés.')
            else:
                # 5 médias par ligne. Le menu ⋮ est rendu AVANT la miniature
                # puis remonté par CSS : il apparaît donc visuellement en haut à droite.
                thumb_cols = 5
                for row_start in range(0, len(filtered_media_rows), thumb_cols):
                    row = filtered_media_rows[row_start:row_start + thumb_cols]
                    cols = st.columns(thumb_cols, gap='small')

                    for col, media in zip(cols, row):
                        media_id, filename, stored_name, media_type, mime_type, size_bytes, uploaded_by, uploaded_at = media
                        file_path = MEDIA_DIR / str(ZONE) / str(r) / stored_name

                        if not file_path.exists():
                            continue

                        with col:
                            with open(file_path, 'rb') as media_file:
                                media_bytes = media_file.read()

                            # ⋮ EN HAUT À DROITE : téléchargement + plein écran regroupés.
                            menu_cols = st.columns([9, 1], gap='small')
                            with menu_cols[1]:
                                with st.popover('⋮', use_container_width=True):
                                    st.markdown('**Options du média**')
                                    if st.button(
                                        '⛶ Plein écran',
                                        key=f'rex_media_fullscreen_{media_id}',
                                        use_container_width=True
                                    ):
                                        st.session_state[f'rex_selected_media_{ZONE}_{r}'] = {
                                            'id': media_id,
                                            'filename': filename,
                                            'path': str(file_path),
                                            'media_type': media_type,
                                            'mime_type': mime_type,
                                        }
                                        st.session_state[f'rex_media_fullscreen_{ZONE}_{r}'] = True
                                        st.rerun()

                                    st.download_button(
                                        '⬇️ Télécharger',
                                        data=media_bytes,
                                        file_name=filename,
                                        mime=mime_type or 'application/octet-stream',
                                        key=f'rex_media_download_{media_id}',
                                        use_container_width=True
                                    )

                            if media_type == 'image':
                                st.image(str(file_path), use_container_width=True, caption=None)
                                st.caption(f'📸 {filename if len(filename) <= 22 else filename[:19] + "..."}')
                            elif media_type == 'video':
                                st.markdown(
                                    '<div class="rex-thumb-video">▶<small>🎥 VIDÉO</small></div>',
                                    unsafe_allow_html=True
                                )
                                st.caption(f'🎥 {filename if len(filename) <= 22 else filename[:19] + "..."}')


# Affichage grand format déclenché depuis le menu ⋮.
            selected_key = f'rex_selected_media_{ZONE}_{r}'
            fullscreen_key = f'rex_media_fullscreen_{ZONE}_{r}'
            selected_media = st.session_state.get(selected_key)
            if selected_media and st.session_state.get(fullscreen_key):
                st.divider()
                st.markdown(f"### ⛶ Plein écran : {selected_media['filename']}")
                if selected_media['media_type'] == 'image':
                    st.image(selected_media['path'], use_container_width=True)
                elif selected_media['media_type'] == 'video':
                    st.video(selected_media['path'], format=selected_media['mime_type'] or None)
                if st.button('✕ Fermer', key=f'rex_media_close_fullscreen_{ZONE}_{r}'):
                    st.session_state[fullscreen_key] = False
                    st.rerun()

        else:
            st.info('Aucune photo ou vidéo n’a encore été ajoutée pour ce rapport.')

    elif zone_menu == "🚀 Vérifier & Soumettre":
        st.markdown('<div class="section-title">🚀 VÉRIFICATION & SOUMISSION</div>', unsafe_allow_html=True)
        st.info("Toutes les informations saisies dans les différents menus seront enregistrées en une seule fois : Cells Down, DR2, difficultés, instances, sites dégradés, permanences week-end, planning mensuel et formations.")

        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.metric("Cells Down", int(cells[['2G','3G','4G','5G']].fillna(0).sum().sum()) if not cells.empty else 0)
        with s2:
            st.metric("DR2", int((dr['DR2'].fillna('') == 'OUI').sum()) if not dr.empty else 0)
        with s3:
            st.metric("Instances", len(ins))
        with s4:
            st.metric("Sites dégradés", len(deg))

        st.markdown("### 📋 Éléments qui seront soumis")
        st.write("✅ Incidentologie • ✅ Opérations & instances • ✅ Permanences week-end • ✅ Planning mensuel • ✅ Rex & formations")

        validation_issues = _validate_zone_data(cells, dr, ins, deg, forms)
        if validation_issues:
            st.warning(f'⚠️ {len(validation_issues)} anomalie(s) de saisie détectée(s) :')
            for issue in validation_issues[:8]:
                st.write(f'• {issue}')
            if len(validation_issues) > 8:
                st.caption(f'… et {len(validation_issues) - 8} autre(s).')
        else:
            st.success('✅ Aucun champ incohérent détecté dans les tableaux.')

        confirm_submit = st.checkbox(
            "J’ai vérifié les informations saisies et je confirme l’envoi.",
            key=f"confirm_submit_{r}_{ZONE}"
        )
        if st.button(
            f'🚀 CONFIRMER ET SOUMETTRE LE RAPPORT DU {r}',
            type='primary',
            use_container_width=True,
            disabled=(not confirm_submit or bool(validation_issues))
        ):
            # Enregistrement unique de toutes les données quotidiennes.
            save(r, ZONE, difficulties, cells, dr, ins, deg, forms, pd.DataFrame())
            for _wk in weekend_dates(dt_selected.year, weekend_month):
                _key = f"weekend_{ZONE}_{_wk.strftime('%Y%m%d')}"
                if _key in st.session_state:
                    save_weekend_permanence_df(st.session_state[_key], dt_selected.year, weekend_month, _wk, ZONE)

            # Enregistre le planning mensuel uniquement s'il a été modifié dans l'éditeur.
            # Le planning généré automatiquement est déjà enregistré en base.
            try:
                current_monthly = get_monthly_pivot_df(m_year, m_month, ZONE)
                if not edited_pivot.equals(current_monthly):
                    save_monthly_pivot_df(edited_pivot, m_year, m_month, ZONE)
            except Exception as exc:
                st.warning(f"Le rapport quotidien a été enregistré, mais le planning mensuel n'a pas pu être mis à jour : {exc}")

            st.session_state['_draft_saved_context'] = _draft_context
            st.balloons()
            st.success(f'✅ Tout le rapport de la zone {ZONE} du {r} a été soumis en une seule fois !')

    # ------------------------------------------------------------------
    # SYNTHÈSE DE FIN D'ESPACE ZONE
    # ------------------------------------------------------------------
    st.markdown('<div class="zone-dashboard-bottom">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📊 SYNTHÈSE DE LA ZONE</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.write("")

# --- MODE CHEF / SUPERVISEUR ---
else:
    rep, cells, dr, ins, deg, forms, plan = qdf('SELECT zone ZONE,submitted_by "REMPLI PAR",submitted_at "SOUMIS LE",difficulties DIFFICULTES FROM reports WHERE report_date=? ORDER BY zone', (r,)), \
                                           qdf("SELECT zone ZONE,site SITE,g2 '2G',g3 '3G',g4 '4G',g5 '5G',observation OBSERVATION,statut STATUT FROM cells_down WHERE report_date=? ORDER BY zone", (r,)), \
                                           qdf("SELECT zone ZONE,site SITE,sites_impactes 'SITES IMPACTÉS',dr2 DR2,escalade ESCALADE,evitable 'ÉVITABLE ?',point_bloquant 'POINT BLOQUANT',statut STATUT FROM dr2 WHERE report_date=? ORDER BY zone", (r,)), \
                                           qdf("SELECT zone ZONE,base BASE,installations INSTALLATIONS,derangements DÉRANGEMENTS,points_bloquants 'POINTS BLOQUANTS' FROM instances WHERE report_date=? ORDER BY zone", (r,)), \
                                           qdf("SELECT zone ZONE,site_name 'SITE NAME',g2 '2G',g3 '3G',g4 '4G',disponibilite 'DISPONIBILITÉ',base BASE FROM degraded WHERE report_date=? ORDER BY zone", (r,)), \
                                           qdf("SELECT zone ZONE,base BASE,intitule 'INTITULÉ',notions 'NOTIONS VUES' FROM formations WHERE report_date=? ORDER BY zone", (r,)), \
                                           qdf("SELECT zone ZONE,entite ENTITÉ,matricule MATRICULE,nom NOM,prenoms PRÉNOMS,fonction FONCTION,niveau 'NIVEAU HIÉRARCHIQUE',contrat 'NATURE CONTRAT',contact CONTACT,role_garde 'RÔLE / GARDE' FROM planning WHERE report_date=? ORDER BY zone", (r,))

    submitted = rep.ZONE.tolist() if not rep.empty else []
    missing = [z for z in ZONES if z not in submitted]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric('RAPPORTS TRANSMIS', f'{len(submitted)}/{len(ZONES)}')
    k2.metric('TOTAL CELLS DOWN', int(cells[['2G','3G','4G','5G']].fillna(0).sum().sum()) if not cells.empty else 0)
    k3.metric('INCIDENTS DR2', int((dr.DR2.fillna('') == 'OUI').sum()) if not dr.empty else 0)
    k4.metric('PERMANENCES WEEK-END', int(qdf('SELECT COUNT(*) c FROM weekend_permanence WHERE weekend_start LIKE ? AND zone IN ({})'.format(','.join(['?']*len(ZONES))), tuple([f'%/{dt_selected.month:02d}/{dt_selected.year}'] + ZONES)).iloc[0,0]) if ZONES else 0)

    st.write("")
    _render_supervisor_status_dashboard(r, )
    st.write("")
    if missing: st.warning(f'⚠️ Zones non récapitulées : {", ".join(missing)}')
    else: st.success('✅ Rapport global complet !')

    st.sidebar.markdown("""
    <div class="sidebar-brand">
      <div class="brand-icon">📡</div>
      <div class="brand-title">YAS DFO-SRTM</div>
      <div class="brand-subtitle">HUB OPÉRATIONNEL MARITIME</div>
    </div>
    <div class="sidebar-section-label">Navigation • Superviseur</div>
    """, unsafe_allow_html=True)
    sup_menu = st.sidebar.radio(
        "Sous-menus",
        ["✨ Actualités opérationnelles", "📄 Problématiques", "📅 Week-ends", "🗓️ Planning secteurs"],
        key="sup_menu_desktop",
        label_visibility="collapsed",
        on_change=_desktop_supervisor_navigation_changed
    )
    if st.session_state.get("yas_mobile_nav_override") and st.session_state.get("yas_mobile_choice") in ["✨ Actualités opérationnelles", "📄 Problématiques", "📅 Week-ends", "🗓️ Planning secteurs"]:
        sup_menu = st.session_state.get("yas_mobile_choice", sup_menu)
    st.sidebar.markdown(f'''
    <div class="sidebar-user-card">
      👤 <strong>SUPERVISEUR GÉNÉRAL</strong><br>
      🌐 Secteur : <strong>GENERAL</strong><br>
      📅 Rapport : <strong>{r}</strong>
    </div>
    ''', unsafe_allow_html=True)

    if sup_menu == "✨ Actualités opérationnelles":
        st.markdown('<div class="section-title">✨ ACTUALITÉS OPÉRATIONNELLES</div>', unsafe_allow_html=True)
        
        st.markdown(f"""<div class=\"ops-hero\"><div><b>📡 Situation du {r}</b><br><span>Suivi des informations transmises par les secteurs et aperçu des derniers points opérationnels.</span></div><div class=\"ops-hero-pill\">{len(rep)} RAPPORT(S)</div></div>""", unsafe_allow_html=True)
        c_syn1, c_syn2 = st.columns(2)
        with c_syn1:
            st.markdown("**🚨 1. CELLS DOWN — incidents réseau GLOBAL**")
            if not cells.empty:
                st.dataframe(cells, use_container_width=True, hide_index=True)
            else:
                st.info("Aucune cellule hors service signalée aujourd'hui.")
                
        with c_syn2:
            st.markdown("**📌 DR2 GLOBAL (J-1)**")
            if not dr.empty:
                st.dataframe(dr, use_container_width=True, hide_index=True)
            else:
                st.info("Aucun incident DR2 consigné pour cette date.")

        render_daily_synthesis(r, global_data=(rep, cells, dr, ins, deg, forms, plan))

    elif sup_menu == "📄 Problématiques":
        st.markdown('<div class="section-title">💬 DIFFICULTÉS GLOBALES PAR SECTEUR</div>', unsafe_allow_html=True)
        if not rep.empty:
            for _, r_row in rep.iterrows():
                with st.expander(f"📍 Secteur {r_row['ZONE']} — Soumis par {r_row['REMPLI PAR']} à {r_row['SOUMIS LE']}"):
                    st.write(r_row['DIFFICULTES'] if r_row['DIFFICULTES'] else "Aucune difficulté majeure signalée.")
        else:
            st.info("Aucun rapport secteur transmis.")

        st.markdown('<div class="section-title" style="margin-top:20px;">⚙️ INSTANCES ET SITES DÉGRADÉS CONSOLIDÉS</div>', unsafe_allow_html=True)
        c_ins1, c_ins2 = st.columns(2)
        with c_ins1:
            st.markdown("**⚙️ Instances Terrain**")
            st.dataframe(ins, use_container_width=True, hide_index=True)
        with c_ins2:
            st.markdown("**📉 Sites Dégradés**")
            st.dataframe(deg, use_container_width=True, hide_index=True)

        st.markdown('<div class="section-title" style="margin-top:20px;">🧠 PARTAGE D\'EXPÉRIENCE DU JOUR</div>', unsafe_allow_html=True)
        st.dataframe(forms, use_container_width=True, hide_index=True)

    elif sup_menu == "📅 Week-ends":
        st.markdown('<div class="section-title">📅 PERMANENCES WEEK-END CONSOLIDÉES PAR BASE</div>', unsafe_allow_html=True)
        sup_weekends = weekend_dates(dt_selected.year, dt_selected.month)
        sw = st.selectbox(
            'Week-end à consulter', sup_weekends or [date(dt_selected.year, dt_selected.month, 1)],
            format_func=lambda d: f"Week-end du {d.strftime('%d/%m/%Y')} au {(d + pd.Timedelta(days=1).to_pytimedelta()).strftime('%d/%m/%Y')}",
            key='sup_weekend'
        )
        for z in ZONES:
            st.markdown(f"**📍 BASE / SECTEUR : {z}**")
            wdf = get_weekend_permanence_df(dt_selected.year, dt_selected.month, sw, z)
            st.dataframe(wdf, use_container_width=True, hide_index=True)

    elif sup_menu == "🗓️ Planning secteurs":
        st.markdown('<div class="section-title">🗓️ PLANNING MENSUEL CONSOLIDÉ — TOUS LES SECTEURS</div>', unsafe_allow_html=True)
        c_pm1, c_pm2, c_pm3 = st.columns([2, 2, 3])
        with c_pm1:
            m_month_sup = st.selectbox('Mois à consulter', range(1, 13), index=dt_selected.month - 1, key='m_month_sup')
        with c_pm2:
            m_year_sup = st.number_input('Année', min_value=2025, max_value=2035, value=dt_selected.year, key='m_year_sup')
        with c_pm3:
            sector_filter = st.multiselect('Secteurs', ZONES, default=ZONES, key='planning_sector_filter')

        # Filtres de vue consolidée
        vf1, vf2, vf3 = st.columns([2, 2, 3])
        with vf1:
            sup_view = st.selectbox('Vue', ['Mois complet', 'Un jour précis', 'Un weekend'], key='sup_planning_view')
        nd_sup = calendar.monthrange(m_year_sup, m_month_sup)[1]
        sup_days = [f'{d:02d}' for d in range(1, nd_sup + 1)]
        sup_visible_days = sup_days
        if sup_view == 'Un jour précis':
            with vf2:
                sup_day = st.selectbox('Jour', range(1, nd_sup + 1), format_func=lambda d: f'{d:02d}/{m_month_sup:02d}/{m_year_sup}', key='sup_planning_day')
            sup_visible_days = [f'{sup_day:02d}']
        elif sup_view == 'Un weekend':
            sats = [d for d in range(1, nd_sup + 1) if date(m_year_sup, m_month_sup, d).weekday() == 5]
            with vf2:
                sup_sat = st.selectbox('Weekend', sats or [1], format_func=lambda d: f'Sam {d:02d}/{m_month_sup:02d} + Dim {d+1:02d}/{m_month_sup:02d}' if d < nd_sup else f'Sam {d:02d}/{m_month_sup:02d}', key='sup_planning_weekend')
            sup_visible_days = [f'{sup_sat:02d}']
            if sup_sat + 1 <= nd_sup:
                sup_visible_days.append(f'{sup_sat+1:02d}')
        with vf3:
            sup_roles = st.multiselect('Rôles', ROLES_SHORT, default=ROLES_SHORT, key='sup_planning_role_filter')

        consolidated = []
        for z in (sector_filter or []):
            piv = get_monthly_pivot_df(m_year_sup, m_month_sup, z).copy()
            if piv.empty:
                continue
            piv.insert(0, 'ZONE', z)
            consolidated.append(piv)

        if consolidated:
            all_piv = pd.concat(consolidated, ignore_index=True)
            # Matricule affiché dans le planning mensuel consolidé également.
            mat_map = {}
            for z in (sector_filter or []):
                for a in DEFAULT_AGENTS.get(z, []):
                    mat_map[(z, str(a.get('Nom','')), str(a.get('Prénoms','')))] = a.get('Matricule', '-')
            all_piv.insert(1, 'MATRICULE', [
                mat_map.get((str(z), str(n), str(p)), '-')
                for z, n, p in zip(all_piv['ZONE'], all_piv['NOM'], all_piv['PRÉNOMS'])
            ])
            display_cols = ['ZONE', 'MATRICULE', 'NOM', 'PRÉNOMS', 'FONCTION'] + sup_visible_days
            display = all_piv[display_cols].copy()
            if set(sup_roles) != set(ROLES_SHORT):
                display = display[display[sup_visible_days].isin(sup_roles).any(axis=1)].copy()

            # Couleurs : même palette que les plannings des secteurs.
            styles = pd.DataFrame('', index=display.index, columns=display.columns)
            holidays_sup = togo_holidays(m_year_sup)
            role_colors_sup = {'PJ':'#FFD84D','PN':'#F6A623','A':'#8BE28B','C':'#E5E7EB','Repos':'#C8EEFF','SN':'#F1F5F9'}
            for col in display.columns:
                if col in ['ZONE','MATRICULE','NOM','PRÉNOMS','FONCTION']:
                    styles[col] = 'background-color:#EAF4FB; color:#12396F; font-weight:800;'
                    continue
                dtc = date(m_year_sup, m_month_sup, int(col))
                for idx in display.index:
                    v = str(display.at[idx,col])
                    bg = role_colors_sup.get(v, '#FFFFFF')
                    styles.at[idx,col] = f'background-color:{bg}; color:#111827; font-weight:800; text-align:center;'
                    if dtc in holidays_sup:
                        styles.at[idx,col] += 'border-left:2px solid #E56A76;border-right:2px solid #E56A76;'
                    elif dtc.weekday() >= 5 and v not in role_colors_sup:
                        styles.at[idx,col] = 'background-color:#C8EEFF; color:#123A63; font-weight:800; text-align:center;'

            sup_config = {
                'ZONE': st.column_config.TextColumn('SECTEUR', disabled=True, width='small'),
                'MATRICULE': st.column_config.TextColumn('MATRICULE', disabled=True, width='medium'),
                'NOM': st.column_config.TextColumn('NOM', disabled=True, width='medium'),
                'PRÉNOMS': st.column_config.TextColumn('PRÉNOMS', disabled=True, width='medium'),
                'FONCTION': st.column_config.TextColumn('FONCTION', disabled=True, width='large'),
            }
            for d in sup_visible_days:
                dtc = date(m_year_sup, m_month_sup, int(d))
                label = f'🎉 {d}' if dtc in holidays_sup else (f'🟦 {d}' if dtc.weekday() >= 5 else d)
                sup_config[d] = st.column_config.SelectboxColumn(label, options=ROLES_SHORT, disabled=True, width='small')

            st.data_editor(display.style.apply(lambda _: styles, axis=None), use_container_width=True, hide_index=True, column_config=sup_config, num_rows='fixed', key='supervisor_monthly_view')

            recaps=[]
            for z in (sector_filter or []):
                rz=monthly_summary(m_year_sup,m_month_sup,z)
                if not rz.empty:
                    rz.insert(0,'ZONE',z); recaps.append(rz)
            if recaps:
                st.markdown('<div class="section-title" style="margin-top:20px;">📊 RÉCAPITULATIF MENSUEL CONSOLIDÉ</div>', unsafe_allow_html=True)
                global_recap=pd.concat(recaps,ignore_index=True)
                st.dataframe(global_recap,use_container_width=True,hide_index=True)

                oo=BytesIO()
                with pd.ExcelWriter(oo,engine='xlsxwriter') as w:
                    global_recap.to_excel(w,sheet_name='Recap Global',index=False)
                    for z in (sector_filter or []):
                        zp=get_monthly_pivot_df(m_year_sup,m_month_sup,z)
                        zp.to_excel(w,sheet_name=f'Planning {z}',index=False)
                        ws=w.sheets[f'Planning {z}']
                        navy_fmt=w.book.add_format({'bold':True,'font_color':'#FFFFFF','bg_color':'#12396F','border':1,'align':'center'})
                        role_fmt={
                            'PJ':w.book.add_format({'bg_color':'#FFD84D','bold':True,'border':1,'align':'center'}),
                            'PN':w.book.add_format({'bg_color':'#F6A623','bold':True,'border':1,'align':'center'}),
                            'A':w.book.add_format({'bg_color':'#8BE28B','bold':True,'border':1,'align':'center'}),
                            'C':w.book.add_format({'bg_color':'#E5E7EB','bold':True,'border':1,'align':'center'}),
                            'Repos':w.book.add_format({'bg_color':'#C8EEFF','bold':True,'border':1,'align':'center'}),
                            'SN':w.book.add_format({'bg_color':'#F1F5F9','border':1,'align':'center'}),
                        }
                        for ci,cname in enumerate(zp.columns): ws.write(0,ci,cname,navy_fmt)
                        ws.freeze_panes(1,3)
                        ws.autofilter(0,0,max(len(zp),1),max(len(zp.columns)-1,0))
                        ws.set_column(0,0,20); ws.set_column(1,1,26); ws.set_column(2,2,42); ws.set_column(3,len(zp.columns)-1,8)
                        for ri in range(len(zp)):
                            for ci,cname in enumerate(zp.columns[3:], start=3):
                                ws.write(ri+1,ci,str(zp.iloc[ri][cname]),role_fmt.get(str(zp.iloc[ri][cname]),role_fmt['SN']))
                st.download_button('📥 Télécharger le planning mensuel consolidé',data=oo.getvalue(),file_name=f'Planning_Mensuel_Maritime_{m_year_sup}_{m_month_sup:02d}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',type='primary',use_container_width=True,key='download_supervisor_monthly')
        else:
            st.info('Aucun planning disponible pour les secteurs sélectionnés.')

    # --- EXPORTATION EXCEL CONSOLIDÉE ---
    st.write("")
    st.markdown('<div class="section-title">📥 EXPORT DU RAPPORT CONSOLIDÉ (EXCEL)</div>', unsafe_allow_html=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        if not rep.empty: rep.to_excel(writer, sheet_name='Synthèse Reports', index=False)
        if not cells.empty: cells.to_excel(writer, sheet_name='Cells Down', index=False)
        if not dr.empty: dr.to_excel(writer, sheet_name='DR2', index=False)
        if not ins.empty: ins.to_excel(writer, sheet_name='Instances', index=False)
        if not deg.empty: deg.to_excel(writer, sheet_name='Sites Dégradés', index=False)
        if not forms.empty: forms.to_excel(writer, sheet_name='Formations', index=False)
        for z in ZONES:
            wdf = get_weekend_permanence_df(dt_selected.year, dt_selected.month, weekend_dates(dt_selected.year, dt_selected.month)[0] if weekend_dates(dt_selected.year, dt_selected.month) else date(dt_selected.year, dt_selected.month, 1), z)
            if not wdf.empty:
                wdf.insert(0, 'ZONE', z)
                wdf.to_excel(writer, sheet_name=f'Weekend {z}', index=False)
        
    excel_data = output.getvalue()
    
    st.download_button(
        label=f"📊 Télécharger le Rapport Global du {r} (Excel)",
        data=excel_data,
        file_name=f"Rapport_Global_Maritime_{r.replace('/', '-')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True
    )

# --- PIED DE PAGE ---
st.markdown(
    '<div style="text-align:center;color:#64748B;font-size:11px;margin:30px 0 10px 0;">'
    'YAS DFO-SRTM • Hub Opérationnel Maritime • Interface simplifiée • V3'
    '</div>',
    unsafe_allow_html=True
)
