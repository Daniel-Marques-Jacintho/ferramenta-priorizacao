# app.py (versão com fonte personalizada Montserrat)

import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import io

# --- Configuração da Página e Tema Visual ---
st.set_page_config(page_title="Matriz de Priorização de Projetos", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# Injeta CSS para aplicar o tema de cores e a NOVA FONTE
st.markdown("""
<style>
    /* Importa a fonte Montserrat do Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');

    /* Aplica a nova fonte a todos os elementos da aplicação */
    html, body, [class*="st-"], [class*="css-"] {
        font-family: 'Montserrat', sans-serif;
    }

    /* Cor de fundo da aplicação principal */
    .main {
        background-color: #FFFFFF;
    }
    /* Cor de fundo da barra lateral */
    [data-testid="stSidebar"] {
        background-color: #f79433; /* Cor secundária */
    }
    /* Cor do texto na barra lateral */
    [data-testid="stSidebar"] * {
        color: #191e50; /* Cor primária para o texto */
    }
    /* Cor do texto DENTRO dos campos de input para preto */
    [data-testid="stSidebar"] input, [data-testid="stSidebar"] textarea {
        color: #000000 !important;
    }
    /* Cor dos títulos principais na página */
    h1, h2, h3 {
        color: #191e50; /* Cor primária */
        font-family: 'Montserrat', sans-serif; /* Garante que os títulos também usem a fonte */
    }
    /* Estilo dos botões */
    .stButton>button {
        color: #FFFFFF;
        background-color: #191e50; /* Cor primária nos botões */
        border: none;
        border-radius: 5px;
        padding: 10px 24px;
        width: 100%;
        font-family: 'Montserrat', sans-serif;
    }
    .stButton>button:hover {
        background-color: #2b3380;
        color: #FFFFFF;
    }
    /* Estilo dos expanders */
    .st-expander-header {
        font-size: 1.1em !important;
        font-weight: bold !important;
        color: #191e50 !important;
        font-family: 'Montserrat', sans-serif;
    }
</style>
""", unsafe_allow_html=True)


# --- Funções de Conexão com o Google Sheets ---
@st.cache_resource(ttl=300)
def connect_gsheets():
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"].to_dict()
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        sa = gspread.authorize(creds)
        sheet = sa.open("Base de Dados - Ferramenta de Priorização")
        return sheet.worksheet("Sheet1")
    except Exception as e:
        st.error(f"Erro Crítico ao conectar: {e}")
        return None

@st.cache_data(ttl=60)
def get_data_from_gsheets():
    worksheet = connect_gsheets()
    if worksheet is None: return pd.DataFrame()
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        if 'demanda_legal' in df.columns:
            df['demanda_legal'] = df['demanda_legal'].apply(lambda x: True if str(x).upper() == 'TRUE' else False)
        return df
    except Exception:
        return pd.DataFrame()

def find_row_by_id(worksheet, project_id):
    try:
        cell = worksheet.find(str(project_id), in_column=1)
        return cell.row
    except (gspread.exceptions.CellNotFound, AttributeError):
        return None

def update_projeto(worksheet, project_id, data_row):
    row_number = find_row_by_id(worksheet, project_id)
    if row_number:
        try:
            headers = worksheet.row_values(1)
            update_values = [data_row.get(h, '') for h in headers]
            worksheet.update(f'A{row_number}', [update_values])
            return True
        except Exception as e:
            st.error(f"Erro ao atualizar o projeto: {e}")
            return False
    return False

def delete_projeto(worksheet, project_id):
    row_number = find_row_by_id(worksheet, project_id)
    if row_number:
        try:
            worksheet.delete_rows(row_number)
            return True
        except Exception as e:
            st.error(f"Erro ao excluir o projeto: {e}")
            return False
    return False

def gravar_projeto(worksheet, data_row):
    try:
        all_ids = worksheet.col_values(1)[1:]
        all_ids = [int(i) for i in all_ids if str(i).isdigit()]
        next_id = max(all_ids) + 1 if all_ids else 1
        data_row['ID'] = next_id
        
        headers = worksheet.row_values(1)
        new_row_ordered = [data_row.get(h, '') for h in headers]
        worksheet.append_row(new_row_ordered)
        return True
    except Exception as e:
        st.error(f"Erro ao gravar o novo projeto: {e}")
        return False

# --- Dicionários e Funções de Cálculo ---
MAPA_ALINHAMENTO = {"Desconectado da estratégia da empresa": 1, "Levemente conectado a temas operacionais": 2, "Conectado a um objetivo estratégico secundário": 3, "Atende diretamente um objetivo estratégico prioritário": 4, "É essencial para a execução de uma frente estratégica central": 5}
MAPA_EBITDA = {"Nenhum impacto financeiro estimável": 1, "Impacto operacional localizado e difícil de quantificar": 2, "Geração de eficiência escalável ou corte de custos moderado": 3, "Aumento de receita ou economia > R$ 500k/ano": 4, "Impacto financeiro direto, claro, e potencial multimilionário": 5}
MAPA_COMPLEXIDADE = {"Solução simples, com dados e lógica prontos": 1, "Requer pequenas transformações ou integrações": 2, "Demanda uso de modelos básicos, múltiplas fontes": 3, "Envolve arquitetura complexa, pipelines robustos": 4, "Alto risco técnico, dependência de tecnologias emergentes": 5}
MAPA_CUSTO = {"Entregável em até 2 semanas com equipe atual": 1, "Exige até 1 mês com recursos existentes": 2, "Precisa de squad dedicado por mais de 1 mês": 3, "Necessita orçamento adicional, contratação ou serviços externos": 4, "Alto custo recorrente e/ou necessidade de aquisição relevante": 5}
MAPA_ENGAJAMENTO = {"Área requisitante ausente ou passiva": 1, "Pouco engajamento, sem interlocutor fixo": 2, "Engajamento esporádico e reativo": 3, "Existe Data Owner claro e colaborativo": 4, "Cocriação ativa com liderança da área e patrocínio executivo": 5}
MAPA_DEPENDENCIA = {"Nenhum fornecedor envolvido. Tudo interno": 1, "Fornecedor envolvido, mas contrato vigente e serviços maduros": 2, "Alguma dependência de entregas de terceiros, com SLA razoável": 3, "Dependência crítica de fornecedor específico, sem redundância": 4, "Fornecedores múltiplos, novos ou instáveis, com risco de travamento": 5}

def processar_dataframe(df):
    if df.empty: return df

    mapas = {'alinhamento': MAPA_ALINHAMENTO, 'ebitda': MAPA_EBITDA, 'complexidade': MAPA_COMPLEXIDADE, 'custo': MAPA_CUSTO, 'dependencia': MAPA_DEPENDENCIA}
    for col_db, mapa in mapas.items():
        if col_db in df.columns:
            df[f'score_{col_db}'] = df[col_db].map(mapa)
    if 'engajamento' in df.columns:
        df['score_engajamento'] = 6 - df['engajamento'].map(MAPA_ENGAJAMENTO)

    df['Nota Impacto'] = df[['score_alinhamento', 'score_ebitda']].mean(axis=1)
    df['Nota Esforço'] = df[['
