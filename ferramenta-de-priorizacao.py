# app.py (versão com a correção final do NameError)

import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import gspread
import io

# --- Configuração da Conexão com o Google Sheets ---

@st.cache_resource(ttl=600)
def connect_gsheets():
    """Conecta-se ao Google Sheets e retorna o objeto da worksheet."""
    try:
        creds_dict = st.secrets["gcp_service_account"].to_dict()
        creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        sa = gspread.service_account_from_dict(creds_dict)
        # Coloque aqui o NOME EXATO da sua folha de cálculo
        sheet = sa.open("Base de Dados - Ferramenta de Priorização") 
        return sheet.worksheet("Sheet1") # Ou o nome da sua aba
    except Exception as e:
        st.error(f"Erro ao conectar ao Google Sheets: {e}")
        return None

@st.cache_data(ttl=60)
def ler_projetos_do_gsheets():
    """Conecta-se e lê todos os projetos. O resultado desta função (o DataFrame) é cacheado."""
    worksheet = connect_gsheets() # CORREÇÃO: Chamando a função correta
    if worksheet is None:
        return pd.DataFrame()
    
    try:
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        if 'demanda_legal' in df.columns:
            df['demanda_legal'] = df['demanda_legal'].apply(lambda x: True if str(x).upper() == 'TRUE' else False)
        return df
    except Exception:
        return pd.DataFrame()

def gravar_projeto(data):
    """Conecta-se e grava um novo projeto. Não é cacheada."""
    worksheet = connect_gsheets() # CORREÇÃO: Chamando a função correta
    if worksheet:
        new_row = [None, data['Nome do Projeto'], data['Demanda Legal'], data['Alinhamento Estratégico'], data['Impacto em EBITDA'], data['Complexidade Técnica'], data['Custo (Tempo e Recursos)'], data['Engajamento da Área Requisitante'], data['Dependência de Fornecedores']]
        worksheet.append_row(new_row)
        return True
    return False

# --- Dicionários de Mapeamento (Critério -> Nota) ---
MAPA_ALINHAMENTO = {"Desconectado da estratégia da empresa": 1, "Levemente conectado a temas operacionais": 2, "Conectado a um objetivo estratégico secundário": 3, "Atende diretamente um objetivo estratégico prioritário": 4, "É essencial para a execução de uma frente estratégica central": 5}
MAPA_EBITDA = {"Nenhum impacto financeiro estimável": 1, "Impacto operacional localizado e difícil de quantificar": 2, "Geração de eficiência escalável ou corte de custos moderado": 3, "Aumento de receita ou economia > R$ 500k/ano": 4, "Impacto financeiro direto, claro, e potencial multimilionário": 5}
MAPA_COMPLEXIDADE = {"Solução simples, com dados e lógica prontos": 1, "Requer pequenas transformações ou integrações": 2, "Demanda uso de modelos básicos, múltiplas fontes": 3, "Envolve arquitetura complexa, pipelines robustos": 4, "Alto risco técnico, dependência de tecnologias emergentes": 5}
MAPA_CUSTO = {"Entregável em até 2 semanas com equipe atual": 1, "Exige até 1 mês com recursos existentes": 2, "Precisa de squad dedicado por mais de 1 mês": 3, "Necessita orçamento adicional, contratação ou serviços externos": 4, "Alto custo recorrente e/ou necessidade de aquisição relevante": 5}
MAPA_ENGAJAMENTO = {"Área requisitante ausente ou passiva": 1, "Pouco engajamento, sem interlocutor fixo": 2, "Engajamento esporádico e reativo": 3, "Existe Data Owner claro e colaborativo": 4, "Cocriação ativa com liderança da área e patrocínio executivo": 5}
MAPA_DEPENDENCIA = {"Nenhum fornecedor envolvido. Tudo interno": 1, "Fornecedor envolvido, mas contrato vigente e serviços maduros": 2, "Alguma dependência de entregas de terceiros, com SLA razoável": 3, "Dependência crítica de fornecedor específico, sem redundância": 4, "Fornecedores múltiplos, novos ou instáveis, com risco de travamento": 5}

def calcular_notas(df):
    if df.empty: return df
    
    colunas_db_map = {
        'alinhamento': 'score_alinhamento', 'ebitda': 'score_ebitda',
        'complexidade': 'score_complexidade', 'custo': 'score_custo',
        'dependencia': 'score_dependencia'
    }
    mapas = {
        'alinhamento': MAPA_ALINHAMENTO, 'ebitda': MAPA_EBITDA,
        'complexidade': MAPA_COMPLEXIDADE, 'custo': MAPA_CUSTO,
        'dependencia': MAPA_DEPENDENCIA
    }
    for col_db, col_score in colunas_db_map.items():
        if col_db in df.columns:
            df[col_score] = df[col_db].map(mapas[col_db])

    if 'engajamento' in df.columns:
        df['score_engajamento'] = 6 - df['engajamento'].map(MAPA_ENGAJAMENTO)

    df['Nota Impacto'] = df[['score_alinhamento', 'score_ebitda']].mean(axis=1)
    df['Nota Esforço'] = df[['score_complexidade', 'score_custo', 'score_engajamento', 'score_dependencia']].mean(axis=1)
    return df

def classificar_projetos(df):
    ponto_corte = 2.5
    conditions
