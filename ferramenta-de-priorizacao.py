# app.py (versão com a correção definitiva do cache e UnhashableParamError)

import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import gspread
import io

# --- Funções de Conexão e Leitura (Reestruturadas) ---

@st.cache_data(ttl=300) # Cacheia o resultado (o DataFrame) por 5 minutos
def get_data_from_gsheets():
    """
    Função única e robusta para conectar e ler os dados do Google Sheets.
    Esta função é cacheada, o que significa que ela só será executada 
    a cada 5 minutos ou quando o cache for limpo.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"].to_dict()
        creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        sa = gspread.service_account_from_dict(creds_dict)
        sheet = sa.open("Base de Dados - Ferramenta de Priorização")
        worksheet = sheet.worksheet("Sheet1")
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Garante que a coluna 'demanda_legal' seja booleana
        if 'demanda_legal' in df.columns:
            df['demanda_legal'] = df['demanda_legal'].apply(lambda x: True if str(x).upper() == 'TRUE' else False)
        
        return df
    except Exception as e:
        st.error(f"Erro ao carregar os dados do Google Sheets: {e}")
        return pd.DataFrame()

def gravar_projeto(data):
    """
    Função separada para gravar dados. Ela se conecta a cada vez para garantir
    que a gravação seja sempre feita, sem depender de cache.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"].to_dict()
        creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        sa = gspread.service_account_from_dict(creds_dict)
        sheet = sa.open("Base de Dados - Ferramenta de Priorização")
        worksheet = sheet.worksheet("Sheet1")
        
        new_row = [
            None, # ID é gerado automaticamente
            data['Nome do Projeto'], data['Demanda Legal'], data['Alinhamento Estratégico'],
            data['Impacto em EBITDA'], data['Complexidade Técnica'], data['Custo (Tempo e Recursos)'],
            data['Engajamento da Área Requisitante'], data['Dependência de Fornecedores']
        ]
        worksheet.append_row(new_row)
        return True
    except Exception as e:
        st.error(f"Erro ao gravar os dados na folha de cálculo: {e}")
        return False

# --- Dicionários de Mapeamento (Critério -> Nota) ---
MAPA_ALINHAMENTO = {"Desconectado da estratégia da empresa": 1, "Levemente conectado a temas operacionais": 2, "Conectado a um objetivo estratégico secundário": 3, "Atende diretamente um objetivo estratégico prioritário": 4, "É essencial para a execução de uma frente estratégica central": 5}
MAPA_EBITDA = {"Nenhum impacto financeiro estimável": 1, "Impacto operacional localizado e difícil de quantificar": 2, "Geração de eficiência escalável ou corte de custos moderado": 3, "Aumento de receita ou economia > R$ 500k/ano": 4, "Impacto financeiro direto, claro, e potencial multimilionário": 5}
MAPA_COMPLEXIDADE = {"Solução simples, com dados e lógica prontos": 1, "Requer pequenas transformações ou integrações": 2, "Demanda uso de modelos básicos, múltiplas fontes": 3, "Envolve arquitetura complexa, pipelines robustos": 4, "Alto risco técnico, dependência de tecnologias emergentes": 5}
MAPA_CUSTO = {"Entregável em até 2 semanas com equipe atual": 1, "Exige até 1 mês com recursos existentes": 2, "Precisa de squad dedicado por mais de 1 mês": 3, "Necessita orçamento adicional, contratação ou serviços externos": 4, "Alto custo recorrente e/ou necessidade de aquisição relevante": 5}
MAPA_ENGAJAMENTO = {"Área requisitante ausente ou passiva": 1, "Pouco engajamento, sem interlocutor fixo": 2, "Engajamento esporádico e reativo": 3, "Existe Data Owner claro e colaborativo": 4, "Cocriação ativa com liderança da área e patrocínio executivo": 5}
MAPA_DEPENDENCIA = {"Nenhum fornecedor envolvido. Tudo interno": 1, "Fornecedor envolvido, mas contrato vigente e serviços maduros": 2, "Alguma dependência de entregas de terceiros, com SLA razoável": 3, "Dependência crítica de fornecedor específico, sem redundância": 4, "Fornecedores múltiplos, novos ou instáveis, com risco de travamento": 5}

# --- Funções de Cálculo e Classificação ---
def calcular_notas(df):
    if df.empty: return df
    
    colunas_map = {
        'alinhamento': ('score_alinhamento', MAPA_ALINHAMENTO), 'ebitda': ('score_ebitda', MAPA_EBITDA),
        'complexidade': ('score_complexidade', MAPA_COMPLEXIDADE), 'custo': ('score_custo', MAPA_CUSTO),
        'dependencia': ('score_dependencia', MAPA_DEPENDENCIA)
    }
    for col_db, (col_score, mapa) in colunas_map.items():
        if col_db in df.columns:
            df[f'score_{col_db}'] = df[col_db].map(mapa)

    if 'engajamento' in df.columns:
        df['score_engajamento'] = 6 - df['engajamento'].map(MAPA_ENGAJAMENTO)

    df['Nota Impacto'] = df[['score_alinhamento', 'score_ebitda']].mean(axis=1)
    df['Nota Esforço'] = df[['score_complexidade', 'score_custo', 'score_engajamento', 'score_dependencia']].mean(axis=1)
    return df

def classificar_projetos(df):
    ponto_corte = 2.5
    if 'demanda_legal' not in df.columns:
        df['demanda_legal'] = False

    conditions = [
        (df['demanda_legal'] == True),
        (df['Nota Impacto'] >= ponto_corte) & (df['Nota Esforço'] < ponto_corte),
        (df['Nota Impacto'] >= ponto_corte) & (df['Nota Esforço'] >= ponto_corte),
        (df['Nota Impacto'] < ponto_corte) & (df['Nota Esforço'] < ponto_corte),
        (df['Nota Impacto'] < ponto_corte) & (df['Nota Esforço'] >= ponto_corte)
    ]
    choices = ['Prioridade Legal', 'Ganhos Rápidos', 'Projetos Maiores', 'Projetos Rápidos', 'Reavaliar']
    df['Classificação'] = np.select(conditions, choices, default='N/A')
    return df, ponto_corte, ponto_corte

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Priorizacao_Projetos')
    return output.getvalue()

# --- Estrutura Principal da Aplicação ---
def main():
    st.set_page_config(page_title="Matriz de Priorização de Projetos", page_icon="📊", layout="wide")
    st.title("Matriz de Priorização de Projetos")
    st.markdown("Selecione a descrição que melhor se adequa ao projeto em cada critério.")

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
        novo_projeto_data = {
            "Nome do Projeto": nome, "Demanda Legal": demanda_legal,
            "Alinhamento Estratégico": alinhamento, "Impacto em EBITDA": ebitda,
            "Complexidade Técnica": complexidade, "Custo (Tempo e Recursos)": custo,
            "Engajamento da Área Requisitante": engajamento, "Dependência de Fornecedores": dependencia
        }
        if gravar_projeto(novo_projeto_data):
            st.sidebar.success("Projeto adicionado com sucesso ao Google Sheets!")
            st.cache_data.clear() # Limpa o cache para recarregar os dados na próxima interação
        else:
            st.sidebar.error("Falha ao gravar no Google Sheets.")

    # --- Cálculos e Exibição dos Resultados ---
    df_projetos = get_data_from_gsheets()

    if not df_projetos.empty:
        df_com_notas = calcular_notas(df_projetos.copy())
        df_classificado, imp_corte, esf_corte = classificar_projetos(df_com_notas)
        
        st.subheader("Tabela de Priorização")
        colunas_para_exibir = ["nome_projeto", "demanda_legal", "Nota Impacto", "Nota Esforço", "Classificação"]
        st.dataframe(df_classificado[colunas_para_exibir].rename(columns=lambda c: c.replace('_', ' ').title()).round(2))

        st.subheader("Matriz de Priorização")
        fig = px.scatter(
            df_classificado, x="Nota Esforço", y="Nota Impacto",
            text="nome_projeto", color="Classificação",
            color_discrete_map={
                'Prioridade Legal': '#8A2BE2', 'Ganhos Rápidos': '#32CD32',
                'Projetos Maiores': '#1E90FF', 'Projetos Rápidos': '#FFD700',
                'Reavaliar': '#FF4500'
            },
            size_max=40, hover_data=colunas_para_exibir
        )
        
        fig.add_vline(x=esf_corte, line_dash="dash", line_color="gray")
        fig.add_hline(y=imp_corte, line_dash="dash", line_color="gray")
        
        fig.add_annotation(x=esf_corte/2, y=imp_corte/2, text="Projetos Rápidos", showarrow=False, font=dict(color="gray", size=10))
        fig.add_annotation(x=(esf_corte + 6) / 2, y=imp_corte/2, text="Reavaliar", showarrow=False, font=dict(color="gray", size=10))
        fig.add_annotation(x=esf_corte/2, y=(imp_corte + 6) / 2, text="Ganhos Rápidos", showarrow=False, font=dict(color="gray", size=10))
        fig.add_annotation(x=(esf_corte + 6) / 2, y=(imp_corte + 6) / 2, text="Projetos Maiores", showarrow=False, font=dict(color="gray", size=10))
        
        fig.update_traces(textposition='top center')
        fig.update_xaxes(range=[0, 6])
        fig.update_yaxes(range=[0, 6])
        fig.update_layout(xaxis_title="Esforço →", yaxis_title="Impacto →", legend_title="Classificação", height=600)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Exportar Dados")
        excel_data = to_excel(df_classificado)
        st.download_button(
            label="📥 Download como Excel",
            data=excel_data,
            file_name="matriz_priorizacao_detalhada.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Nenhum projeto encontrado. Adicione o primeiro usando o formulário na barra lateral ou verifique a conexão com o Google Sheets.")

if __name__ == "__main__":
    main()
