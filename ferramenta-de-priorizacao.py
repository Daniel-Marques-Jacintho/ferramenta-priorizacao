# ferramenta de priorizacao

import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import gspread
from gspread_dataframe import set_with_dataframe
import io

# ===================================================================
# INÍCIO DO CÓDIGO DE DEPURAÇÃO TEMPORÁRIO
# ===================================================================

st.header("⚠️ Depuração de Segredos (Remover Depois!)")
try:
    # Tenta aceder à secção de segredos
    secrets_dict = st.secrets["gcp_service_account"]
    st.success("A secção [gcp_service_account] foi encontrada nos segredos!")
    
    # Verifica se a chave privada existe
    if "private_key" in secrets_dict:
        st.success("O campo 'private_key' foi encontrado!")
        st.text("Início da chave privada (primeiros 50 caracteres):")
        # Mostra o início da chave para confirmar que não está vazia
        st.code(secrets_dict["private_key"][:50] + "...")
    else:
        st.error("ERRO CRÍTICO: O campo 'private_key' NÃO foi encontrado no dicionário de segredos!")

    st.text("Todos os campos encontrados nos segredos:")
    # Escreve todos os nomes de campos que a app encontrou
    st.write(list(secrets_dict.keys()))

except Exception as e:
    st.error(f"Não foi possível ler os segredos. Erro: {e}")
    st.warning("Verifique se a secção [gcp_service_account] existe no seu painel de Segredos na Streamlit Cloud.")


# ===================================================================
# FIM DO CÓDIGO DE DEPURAÇÃO
# ===================================================================

# --- Configuração da Conexão com o Google Sheets ---

@st.cache_resource(ttl=600)
def connect_gsheets():
    """Conecta-se ao Google Sheets usando as credenciais do Streamlit Secrets."""
    sa = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
    # Coloque aqui o NOME EXATO da sua folha de cálculo
    sheet = sa.open("Base de Dados - Ferramenta de Priorização") 
    return sheet.worksheet("Sheet1") # Ou o nome da sua aba

def gravar_projeto(worksheet, data):
    """Grava uma nova linha com os dados do projeto."""
    # Transforma o dicionário numa lista na ordem correta das colunas
    new_row = [
        None, # ID será gerado pelo Sheets
        data['Nome do Projeto'], data['Demanda Legal'], data['Alinhamento Estratégico'],
        data['Impacto em EBITDA'], data['Complexidade Técnica'], data['Custo (Tempo e Recursos)'],
        data['Engajamento da Área Requisitante'], data['Dependência de Fornecedores']
    ]
    worksheet.append_row(new_row)

@st.cache_data(ttl=60)
def ler_projetos(worksheet):
    """Lê todos os projetos da folha de cálculo."""
    df = pd.DataFrame(worksheet.get_all_records())
    # Garante que a coluna 'demanda_legal' seja booleana
    if 'demanda_legal' in df.columns:
        df['demanda_legal'] = df['demanda_legal'].apply(lambda x: True if str(x).upper() == 'TRUE' else False)
    return df

# (O resto do seu código, dicionários de mapa, cálculos e interface, permanece o mesmo)
# --- Dicionários de Mapeamento (Critério -> Nota) ---
MAPA_ALINHAMENTO = {"Desconectado da estratégia da empresa": 1, "Levemente conectado a temas operacionais": 2, "Conectado a um objetivo estratégico secundário": 3, "Atende diretamente um objetivo estratégico prioritário": 4, "É essencial para a execução de uma frente estratégica central": 5}
MAPA_EBITDA = {"Nenhum impacto financeiro estimável": 1, "Impacto operacional localizado e difícil de quantificar": 2, "Geração de eficiência escalável ou corte de custos moderado": 3, "Aumento de receita ou economia > R$ 500k/ano": 4, "Impacto financeiro direto, claro, e potencial multimilionário": 5}
MAPA_COMPLEXIDADE = {"Solução simples, com dados e lógica prontos": 1, "Requer pequenas transformações ou integrações": 2, "Demanda uso de modelos básicos, múltiplas fontes": 3, "Envolve arquitetura complexa, pipelines robustos": 4, "Alto risco técnico, dependência de tecnologias emergentes": 5}
MAPA_CUSTO = {"Entregável em até 2 semanas com equipe atual": 1, "Exige até 1 mês com recursos existentes": 2, "Precisa de squad dedicado por mais de 1 mês": 3, "Necessita orçamento adicional, contratação ou serviços externos": 4, "Alto custo recorrente e/ou necessidade de aquisição relevante": 5}
MAPA_ENGAJAMENTO = {"Área requisitante ausente ou passiva": 1, "Pouco engajamento, sem interlocutor fixo": 2, "Engajamento esporádico e reativo": 3, "Existe Data Owner claro e colaborativo": 4, "Cocriação ativa com liderança da área e patrocínio executivo": 5}
MAPA_DEPENDENCIA = {"Nenhum fornecedor envolvido. Tudo interno": 1, "Fornecedor envolvido, mas contrato vigente e serviços maduros": 2, "Alguma dependência de entregas de terceiros, com SLA razoável": 3, "Dependência crítica de fornecedor específico, sem redundância": 4, "Fornecedores múltiplos, novos ou instáveis, com risco de travamento": 5}

def calcular_notas(df):
    if df.empty: return df
    df['score_alinhamento'] = df['alinhamento'].map(MAPA_ALINHAMENTO)
    df['score_ebitda'] = df['ebitda'].map(MAPA_EBITDA)
    df['score_complexidade'] = df['complexidade'].map(MAPA_COMPLEXIDADE)
    df['score_custo'] = df['custo'].map(MAPA_CUSTO)
    df['score_engajamento'] = 6 - df['engajamento'].map(MAPA_ENGAJAMENTO)
    df['score_dependencia'] = df['dependencia'].map(MAPA_DEPENDENCIA)
    df['Nota Impacto'] = df[['score_alinhamento', 'score_ebitda']].mean(axis=1)
    df['Nota Esforço'] = df[['score_complexidade', 'score_custo', 'score_engajamento', 'score_dependencia']].mean(axis=1)
    return df

def classificar_projetos(df):
    ponto_corte = 2.5
    conditions = [(df['demanda_legal'] == True), (df['Nota Impacto'] >= ponto_corte) & (df['Nota Esforço'] < ponto_corte), (df['Nota Impacto'] >= ponto_corte) & (df['Nota Esforço'] >= ponto_corte), (df['Nota Impacto'] < ponto_corte) & (df['Nota Esforço'] < ponto_corte), (df['Nota Impacto'] < ponto_corte) & (df['Nota Esforço'] >= ponto_corte)]
    choices = ['Prioridade Legal', 'Ganhos Rápidos', 'Projetos Maiores', 'Projetos Rápidos', 'Reavaliar']
    df['Classificação'] = np.select(conditions, choices, default='N/A')
    return df, ponto_corte, ponto_corte

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Priorizacao_Projetos')
    return output.getvalue()
    
# --- Interface Principal ---
st.set_page_config(page_title="Matriz de Priorização de Projetos", page_icon="📊", layout="wide")
st.title("Matriz de Priorização de Projetos")
st.markdown("Selecione a descrição que melhor se adequa ao projeto em cada critério.")

# Conecta-se à worksheet do Google Sheets
worksheet = connect_gsheets()

with st.sidebar.form("novo_projeto_form", clear_on_submit=True):
    st.header("Adicionar Novo Projeto")
    nome = st.text_input("Nome do Projeto")
    demanda_legal = st.checkbox("É uma Demanda Legal ou de Auditoria? (prioridade máxima)")
    st.subheader("Critérios de Impacto")
    alinhamento = st.radio("Alinhamento estratégico", options=MAPA_ALINHAMENTO.keys(), index=2)
    ebitda = st.radio("Impacto em EBITDA", options=MAPA_EBITDA.keys(), index=2)
    st.subheader("Critérios de Esforço")
    complexidade = st.radio("Complexidade técnica", options=MAPA_COMPLEXIDADE.keys(), index=2)
    custo = st.radio("Custo (Tempo e Recursos)", options=MAPA_CUSTO.keys(), index=2)
    engajamento = st.radio("Engajamento da Área Requisitante", options=MAPA_ENGAJAMENTO.keys(), index=2)
    dependencia = st.radio("Dependência de Fornecedores", options=MAPA_DEPENDENCIA.keys(), index=2)
    submitted = st.form_submit_button("Adicionar Projeto")

if submitted:
    novo_projeto_data = {"Nome do Projeto": nome, "Demanda Legal": demanda_legal, "Alinhamento Estratégico": alinhamento, "Impacto em EBITDA": ebitda, "Complexidade Técnica": complexidade, "Custo (Tempo e Recursos)": custo, "Engajamento da Área Requisitante": engajamento, "Dependência de Fornecedores": dependencia}
    gravar_projeto(worksheet, novo_projeto_data)
    st.sidebar.success("Projeto adicionado com sucesso ao Google Sheets!")
    st.cache_data.clear()

df_projetos = ler_projetos(worksheet)

if not df_projetos.empty:
    df_com_notas = calcular_notas(df_projetos.copy())
    df_classificado, imp_corte, esf_corte = classificar_projetos(df_com_notas)
    st.subheader("Tabela de Priorização")
    colunas_para_exibir = ["nome_projeto", "demanda_legal", "Nota Impacto", "Nota Esforço", "Classificação"]
    st.dataframe(df_classificado[colunas_para_exibir].rename(columns=lambda c: c.replace('_', ' ').title()).round(2))
    st.subheader("Matriz de Priorização")
    fig = px.scatter(df_classificado, x="Nota Esforço", y="Nota Impacto", text="nome_projeto", color="Classificação", color_discrete_map={'Prioridade Legal': '#8A2BE2', 'Ganhos Rápidos': '#32CD32', 'Projetos Maiores': '#1E90FF', 'Projetos Rápidos': '#FFD700', 'Reavaliar': '#FF4500'}, size_max=40, hover_data=colunas_para_exibir)
    fig.add_vline(x=esf_corte, line_dash="dash", line_color="gray")
    fig.add_hline(y=imp_corte, line_dash="dash", line_color="gray")
    fig.add_annotation(x=esf_corte/2, y=imp_corte/2, text="Projetos Rápidos", showarrow=False, font=dict(color="gray", size=10))
    fig.add_annotation(x=(esf_corte + 6) / 2, y=imp_crote/2, text="Reavaliar", showarrow=False, font=dict(color="gray", size=10))
    fig.add_annotation(x=esf_corte/2, y=(imp_corte + 6) / 2, text="Ganhos Rápidos", showarrow=False, font=dict(color="gray", size=10))
    fig.add_annotation(x=(esf_corte + 6) / 2, y=(imp_corte + 6) / 2, text="Projetos Maiores", showarrow=False, font=dict(color="gray", size=10))
    fig.update_traces(textposition='top center')
    fig.update_xaxes(range=[0, 6])
    fig.update_yaxes(range=[0, 6])
    fig.update_layout(xaxis_title="Esforço →", yaxis_title="Impacto →", legend_title="Classificação", height=600)
    st.plotly_chart(fig, use_container_width=True)
    st.subheader("Exportar Dados")
    excel_data = to_excel(df_classificado)
    st.download_button(label="📥 Download como Excel", data=excel_data, file_name="matriz_priorizacao_detalhada.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Nenhum projeto foi adicionado. Adicione o primeiro usando o formulário na barra lateral.")
