"""Karben4 brand theme for the Streamlit QM Yield Tool.

Colors/fonts pulled directly from karben4.com (2026-07-07):
navy #161B23 (body/bg), green #7BE72D (primary accent), gold #F5D500 (secondary
accent), Bebas Neue (headings), Mulish (body), Exo (buttons/labels).
"""

import streamlit as st

NAVY = "#161B23"
NAVY_SURFACE = "#1E2530"
NAVY_SURFACE_2 = "#252D3A"
GREEN = "#7BE72D"
GOLD = "#F5D500"
TEXT = "#F4F6F8"
TEXT_MUTED = "#9AA4B2"
BORDER = "#333B47"

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Exo:wght@500;600;700&family=Mulish:wght@400;500;600;700&display=swap');

:root {{
  --k4-navy: {NAVY};
  --k4-surface: {NAVY_SURFACE};
  --k4-surface-2: {NAVY_SURFACE_2};
  --k4-green: {GREEN};
  --k4-gold: {GOLD};
  --k4-text: {TEXT};
  --k4-text-muted: {TEXT_MUTED};
  --k4-border: {BORDER};
}}

html, body, [class*="css"] {{
  font-family: 'Mulish', sans-serif;
  color: var(--k4-text);
}}

.stApp {{
  background:
    radial-gradient(1200px 500px at 10% -10%, rgba(123,231,45,0.06), transparent 60%),
    var(--k4-navy);
}}

/* Honeycomb watermark strip under the header, echoing the K4 logo hexagons */
.k4-hex-rule {{
  display: flex;
  gap: 6px;
  margin: 0 0 1.1rem 0;
}}
.k4-hex-rule span {{
  width: 22px;
  height: 22px;
  clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
}}

/* Headings — Bebas Neue, condensed industrial, gold like the brewery's H1s */
h1, h2, h3, .stApp [data-testid="stMarkdownContainer"] h1,
.stApp [data-testid="stMarkdownContainer"] h2, .stApp [data-testid="stMarkdownContainer"] h3 {{
  font-family: 'Bebas Neue', sans-serif;
  letter-spacing: 0.03em;
  color: var(--k4-gold);
  text-transform: uppercase;
}}
h1 {{ font-size: 2.6rem !important; border-bottom: 3px solid var(--k4-green); padding-bottom: 0.4rem; display: inline-block; }}
h4, h5, h6 {{ font-family: 'Exo', sans-serif; color: var(--k4-text); }}

/* Caption under the title */
[data-testid="stCaptionContainer"] {{ color: var(--k4-text-muted); font-family: 'Mulish', sans-serif; }}

/* Sidebar */
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #10141B 0%, var(--k4-navy) 100%);
  border-right: 1px solid var(--k4-border);
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
  color: var(--k4-green);
  font-family: 'Bebas Neue', sans-serif;
}}

/* Tabs styled like the brewery's top nav pills */
.stTabs [data-baseweb="tab-list"] {{
  gap: 4px;
  background: var(--k4-surface);
  padding: 6px;
  border-radius: 10px;
  border: 1px solid var(--k4-border);
}}
.stTabs [data-baseweb="tab"] {{
  font-family: 'Exo', sans-serif;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  font-size: 0.85rem;
  color: var(--k4-text-muted);
  border-radius: 7px;
  padding: 8px 16px;
}}
.stTabs [aria-selected="true"] {{
  background: var(--k4-green) !important;
  color: var(--k4-navy) !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: transparent; }}
.stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* Buttons — bright green "SHOP"-style CTA */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  font-family: 'Exo', sans-serif;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  background: var(--k4-green);
  color: var(--k4-navy);
  border: none;
  border-radius: 6px;
  padding: 0.5rem 1.1rem;
  transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
}}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {{
  background: #8FF23F;
  box-shadow: 0 0 0 3px rgba(123,231,45,0.25);
  transform: translateY(-1px);
}}
.stButton > button:focus-visible {{ outline: 2px solid var(--k4-gold); outline-offset: 2px; }}

/* Secondary / delete-style buttons keep gold outline instead of solid green fill */
button[kind="secondary"] {{
  background: transparent !important;
  color: var(--k4-gold) !important;
  border: 1.5px solid var(--k4-gold) !important;
}}

/* Metrics / stat tiles */
[data-testid="stMetric"] {{
  background: var(--k4-surface);
  border: 1px solid var(--k4-border);
  border-left: 4px solid var(--k4-green);
  border-radius: 8px;
  padding: 0.9rem 1rem;
}}
[data-testid="stMetricLabel"] {{
  font-family: 'Exo', sans-serif;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  color: var(--k4-text-muted);
}}
[data-testid="stMetricValue"] {{
  font-family: 'Bebas Neue', sans-serif;
  color: var(--k4-gold);
  font-size: 2rem;
}}

/* Dataframes / tables */
[data-testid="stDataFrame"], [data-testid="stTable"] {{
  border: 1px solid var(--k4-border);
  border-radius: 8px;
  overflow: hidden;
}}
[data-testid="stDataFrame"] div[role="columnheader"] {{
  background: var(--k4-surface-2) !important;
  color: var(--k4-gold) !important;
  font-family: 'Exo', sans-serif;
  text-transform: uppercase;
  font-size: 0.78rem;
  letter-spacing: 0.03em;
}}

/* Inputs, selects, sliders */
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div, .stDateInput input {{
  background: var(--k4-surface) !important;
  color: var(--k4-text) !important;
  border: 1px solid var(--k4-border) !important;
  border-radius: 6px !important;
}}
.stSlider [data-testid="stTickBarMin"], .stSlider [data-testid="stTickBarMax"] {{ color: var(--k4-text-muted); }}

/* Expanders / containers */
[data-testid="stExpander"] {{
  background: var(--k4-surface);
  border: 1px solid var(--k4-border);
  border-radius: 8px;
}}

/* Alerts */
[data-testid="stAlert"] {{ border-radius: 8px; font-family: 'Mulish', sans-serif; }}
.stSuccess {{ border-left: 4px solid var(--k4-green) !important; }}

/* Charts (Vega/Altair) sit on a themed surface */
[data-testid="stArrowVegaLiteChart"], .vega-embed {{
  background: var(--k4-surface) !important;
  border-radius: 8px;
  padding: 0.5rem;
  border: 1px solid var(--k4-border);
}}

/* File uploader */
[data-testid="stFileUploaderDropzone"] {{
  background: var(--k4-surface);
  border: 1.5px dashed var(--k4-border);
  border-radius: 8px;
}}

hr {{ border-color: var(--k4-border); }}
</style>
"""

HEX_RULE_HTML = (
    '<div class="k4-hex-rule">'
    f'<span style="background:{TEXT_MUTED};"></span>'
    f'<span style="background:{GREEN};"></span>'
    f'<span style="background:{NAVY_SURFACE_2};border:1px solid {BORDER};"></span>'
    f'<span style="background:{TEXT_MUTED};"></span>'
    '</div>'
)


def apply():
    """Inject the Karben4 brand theme. Call once, right after st.set_page_config()."""
    st.markdown(CSS, unsafe_allow_html=True)
