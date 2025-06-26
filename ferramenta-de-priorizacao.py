# app.py (versão com a correção final do ValueError e lógica simplificada)

import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
import io

# --- Configuração da Página e Tema Visual ---
st.set_page_config(page_title="Matriz de Priorização de Projetos", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
    .main { background-color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #191e50; }
    [data-testid="stSidebar"] * { color: #FFFFFF; }
    h1, h2, h3 { color: #191e50; }
    .stButton>button { color: #FFFFFF; background-color: #f79433; border: none; border-radius: 5px; padding: 10px 24px; }
    .stButton>button:hover { background-color: #d87e2a; color: #FFFFFF; }
    .st-expander-header { font-size: 1.1em !important; font-weight: bold !important; color: #191e50 !important; }
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
    """Aplica todos os cálculos e classificações a um DataFrame inteiro."""
    if df.empty: return df

    # Mapeia os inputs de texto para scores numéricos
    df['score_alinhamento'] = df['alinhamento'].map(MAPA_ALINHAMENTO)
    df['score_ebitda'] = df['ebitda'].map(MAPA_EBITDA)
    df['score_complexidade'] = df['complexidade'].map(MAPA_COMPLEXIDADE)
    df['score_custo'] = df['custo'].map(MAPA_CUSTO)
    df['score_engajamento'] = 6 - df['engajamento'].map(MAPA_ENGAJAMENTO)
    df['score_dependencia'] = df['dependencia'].map(MAPA_DEPENDENCIA)

    # Calcula as notas de Impacto e Esforço
    df['Nota Impacto'] = df[['score_alinhamento', 'score_ebitda']].mean(axis=1)
    df['Nota Esforço'] = df[['score_complexidade', 'score_custo', 'score_engajamento', 'score_dependencia']].mean(axis=1)
    
    # Classifica os projetos
    ponto_corte = 2.5
    if 'demanda_legal' not in df.columns: df['demanda_legal'] = False
    
    conditions = [(df['demanda_legal'] == True), (df['Nota Impacto'] >= ponto_corte) & (df['Nota Esforço'] < ponto_corte), (df['Nota Impacto'] >= ponto_corte) & (df['Nota Esforço'] >= ponto_corte), (df['Nota Impacto'] < ponto_corte) & (df['Nota Esforço'] < ponto_corte), (df['Nota Impacto'] < ponto_corte) & (df['Nota Esforço'] >= ponto_corte)]
    choices = ['Prioridade Legal', 'Ganhos Rápidos', 'Projetos Maiores', 'Projetos Rápidos', 'Reavaliar']
    df['Classificação'] = np.select(conditions, choices, default='N/A')
    
    return df

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Priorizacao_Projetos')
    return output.getvalue()

# --- Estrutura Principal da Aplicação ---
def main():
    st.title("Matriz de Priorização de Projetos")
    st.markdown("Adicione, edite ou visualize os projetos para classificá-los em uma matriz de Impacto vs. Esforço.")

    if 'editing_project_id' not in st.session_state:
        st.session_state.editing_project_id = None
    
    df_projetos = get_data_from_gsheets()
    
    # --- Formulário na Barra Lateral ---
    st.sidebar.header(f"{'Editar Projeto' if st.session_state.editing_project_id else 'Adicionar Novo Projeto'}")

    project_to_edit = {}
    if st.session_state.editing_project_id:
        project_to_edit = df_projetos[df_projetos['ID'] == st.session_state.editing_project_id].to_dict('records')[0]
    
    options_alinhamento = list(MAPA_ALINHAMENTO.keys())
    options_ebitda = list(MAPA_EBITDA.keys())
    options_complexidade = list(MAPA_COMPLEXIDADE.keys())
    options_custo = list(MAPA_CUSTO.keys())
    options_engajamento = list(MAPA_ENGAJAMENTO.keys())
    options_dependencia = list(MAPA_DEPENDENCIA.keys())

    nome = st.sidebar.text_input("Nome do Projeto", value=project_to_edit.get('nome_projeto', ''))
    demanda_legal = st.sidebar.checkbox("É uma Demanda Legal?", value=project_to_edit.get('demanda_legal', False))
    st.sidebar.subheader("Critérios de Impacto")
    alinhamento = st.sidebar.radio("Alinhamento estratégico", options=options_alinhamento, index=options_alinhamento.index(project_to_edit.get('alinhamento', options_alinhamento[2])))
    ebitda = st.sidebar.radio("Impacto em EBITDA", options=options_ebitda, index=options_ebitda.index(project_to_edit.get('ebitda', options_ebitda[2])))
    st.sidebar.subheader("Critérios de Esforço")
    complexidade = st.sidebar.radio("Complexidade técnica", options=options_complexidade, index=options_complexidade.index(project_to_edit.get('complexidade', options_complexidade[2])))
    custo = st.sidebar.radio("Custo (Tempo e Recursos)", options=options_custo, index=options_custo.index(project_to_edit.get('custo', options_custo[2])))
    engajamento = st.sidebar.radio("Engajamento da Área", options=options_engajamento, index=options_engajamento.index(project_to_edit.get('engajamento', options_engajamento[2])))
    dependencia = st.sidebar.radio("Dependência de Fornecedores", options=options_dependencia, index=options_dependencia.index(project_to_edit.get('dependencia', options_dependencia[2])))

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Salvar"):
            dados_brutos = {'nome_projeto': nome, 'demanda_legal': demanda_legal, 'alinhamento': alinhamento, 'ebitda': ebitda, 'complexidade': complexidade, 'custo': custo, 'engajamento': engajamento, 'dependencia': dependencia}
            
            # Processa a linha única para obter todos os campos calculados
            df_temp = pd.DataFrame([dados_brutos])
            df_processado = processar_dataframe(df_temp)
            projeto_final = df_processado.to_dict('records')[0]
            
            worksheet = connect_gsheets()
            if worksheet:
                if st.session_state.editing_project_id:
                    projeto_final['ID'] = st.session_state.editing_project_id
                    if update_projeto(worksheet, st.session_state.editing_project_id, projeto_final):
                        st.success("Projeto atualizado!")
                        st.session_state.editing_project_id = None
                        st.cache_data.clear()
                        st.rerun()
                else:
                    if gravar_projeto(worksheet, projeto_final):
                        st.success("Projeto adicionado!")
                        st.cache_data.clear()
                        st.rerun()
    with col2:
        if st.session_state.editing_project_id:
            if st.button("Cancelar"):
                st.session_state.editing_project_id = None
                st.rerun()

    # --- Exibição dos Resultados ---
    if not df_projetos.empty:
        # Aplica os cálculos a todos os dados lidos para exibição consistente
        df_classificado = processar_dataframe(df_projetos.copy())

        st.subheader("Lista de Projetos")
        for index, row in df_classificado.sort_values(by="ID", ascending=False).iterrows():
            with st.expander(f"{row['nome_projeto']} (Impacto: {row['Nota Impacto']:.2f} | Esforço: {row['Nota Esforço']:.2f})"):
                st.write(f"**Classificação:** {row['Classificação']}")
                edit_col, del_col = st.columns([0.15, 1])
                with edit_col:
                    if st.button("Editar", key=f"edit_{row['ID']}"):
                        st.session_state.editing_project_id = row['ID']
                        st.rerun()
                with del_col:
                    if st.button("Excluir", key=f"del_{row['ID']}"):
                        worksheet = connect_gsheets()
                        if worksheet and delete_projeto(worksheet, row['ID']):
                            st.success(f"Projeto '{row['nome_projeto']}' excluído.")
                            st.session_state.editing_project_id = None
                            st.cache_data.clear()
                            st.rerun()
        
        st.subheader("Matriz de Priorização")
        ponto_corte = 2.5
        fig = px.scatter(df_classificado, x="Nota Esforço", y="Nota Impacto", text="nome_projeto", color="Classificação", color_discrete_map={'Prioridade Legal': '#8A2BE2', 'Ganhos Rápidos': '#32CD32', 'Projetos Maiores': '#1E90FF', 'Projetos Rápidos': '#f79433', 'Reavaliar': '#FF4500'}, size_max=40)
        fig.add_vline(x=ponto_corte, line_dash="dash", line_color="gray")
        fig.add_hline(y=ponto_corte, line_dash="dash", line_color="gray")
        fig.add_annotation(x=ponto_corte/2, y=ponto_corte/2, text="Projetos Rápidos", showarrow=False, font=dict(color="gray", size=10))
        fig.add_annotation(x=(ponto_corte + 6) / 2, y=ponto_corte/2, text="Reavaliar", showarrow=False, font=dict(color="gray", size=10))
        fig.add_annotation(x=ponto_corte/2, y=(ponto_corte + 6) / 2, text="Ganhos Rápidos", showarrow=False, font=dict(color="gray", size=10))
        fig.add_annotation(x=(ponto_corte + 6) / 2, y=(ponto_corte + 6) / 2, text="Projetos Maiores", showarrow=False, font=dict(color="gray", size=10))
        fig.update_traces(textposition='top center')
        fig.update_xaxes(range=[0, 6])
        fig.update_yaxes(range=[0, 6])
        fig.update_layout(xaxis_title="Esforço →", yaxis_title="Impacto →", legend_title="Classificação", height=600)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Exportar Dados")
        excel_data = to_excel(df_classificado)
        st.download_button(label="📥 Download como Excel", data=excel_data, file_name="matriz_priorizacao_completa.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Nenhum projeto encontrado. Adicione o primeiro usando o formulário na barra lateral.")

if __name__ == "__main__":
    main()
