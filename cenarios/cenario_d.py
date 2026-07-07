import streamlit as st
import pandas as pd
import os
from supabase import create_client

# 1. TRAVA DE SEGURANÇA E AUTO-LOGIN (À PROVA DE F5)
if "logado" not in st.session_state or not st.session_state.logado:
    usuario_url = st.query_params.get("u")
    if usuario_url:
        st.session_state.logado = True
        st.session_state.usuario_atual = usuario_url
    else:
        st.warning("⚠️ Acesso restrito. Por favor, faça login na tela inicial antes de continuar.")
        if st.button("Ir para a Tela de Login"):
            st.switch_page("app.py")
        st.stop()


def renderizar_cenario_d(rm_para_conferencia="", pedidos=None, supabase=None, Skinner_status=None):
    """
    Cenário D - Exibição Consolidada da view vw_approvo_rm
    Mapeia colunas corporativas e traduz as siglas de status de aprovação.
    """
    st.subheader("✅ Approvo Status — Cenário D")
    st.write("Acompanhamento unificado de Requisições de Material e fluxos do Approvo.")
    st.divider()

    # 2. INICIALIZAÇÃO LOCAL DO BANCO (SE ACESSADO DIRETO PELO MENU LATERAL)
    if supabase is None:
        SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 3. CAMPO DE BUSCA INICIAL (FILTRO RÁPIDO)
    buscar_rm = st.text_input("Filtrar por Número da RM:", value=rm_para_conferencia).strip()

    # 4. CONSULTA DOS DADOS NA VIEW
    with st.spinner("Consultando dados na view `vw_approvo_rm`..."):
        try:
            query = supabase.table("vw_approvo_rm").select("*")
            
            if buscar_rm:
                query = query.eq("rm", str(buscar_rm))
                
            resposta = query.execute()
            dados = resposta.data
            
            if dados:
                df_bruto = pd.DataFrame(dados)
                
                # 🚨 MAPEAMENTO E TRADUÇÃO DO STATUS (A -> Aprovado, E -> Em Aprovação, R -> Reprovado)
                # O .get() evita erros caso o banco traga alguma sigla nova ou imprevista
                mapa_status = {"A": "Aprovado", "E": "Em Aprovação", "R": "Reprovado"}
                if "status_documento" in df_bruto.columns:
                    df_bruto["status_documento"] = df_bruto["status_documento"].map(lambda x: mapa_status.get(str(x).upper().strip(), x))

                # TRATAMENTO E FORMATAÇÃO DE DATAS PARA O PADRÃO BRASILEIRO (DD/MM/AAAA)
                colunas_data = ["data_emissao", "data_necessidade"]
                for col in colunas_data:
                    if col in df_bruto.columns:
                        df_bruto[col] = pd.to_datetime(df_bruto[col], errors="coerce").dt.strftime("%d/%m/%Y")
                        
                # A data da ocorrência (Aprovação) ganha também os minutos para auditoria completa
                if "data_ocorrencia" in df_bruto.columns:
                    df_bruto["data_ocorrencia"] = pd.to_datetime(df_bruto["data_ocorrencia"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")

                colunas_multi_index = {
                    "nome_solicitante": ("REQUISICAO DE MATERIAL MEGA", "Requisitante"),
                    "rm":               ("REQUISICAO DE MATERIAL MEGA", "Nr. RM"),
                    "mat":              ("REQUISICAO DE MATERIAL MEGA", "Nr. Material"),
                    "desc_item":        ("REQUISICAO DE MATERIAL MEGA", "Descrição"),
                    "qtd_solicitada":   ("REQUISICAO DE MATERIAL MEGA", "Qt. Sol."),
                    "data_emissao":     ("REQUISICAO DE MATERIAL MEGA", "Data da Requisição"),
                    "data_necessidade": ("REQUISICAO DE MATERIAL MEGA", "Data da Nec."),
                    
                    "status_documento": ("APPROVAL (RM)", "Status da Aprovação"),
                    "data_ocorrencia":  ("APPROVAL (RM)", "Data da Aprovação"),
                    "nome_aprovador":   ("APPROVAL (RM)", "Aprovador"),
                }
                
                # Garante que filtra apenas o que existe no banco
                colunas_existentes = [col for col in colunas_multi_index.keys() if col in df_bruto.columns]
                df_exibicao = df_bruto[colunas_existentes].copy()
                
                # Aplica o MultiIndex criando os blocos agrupados no topo
                df_exibicao.columns = pd.MultiIndex.from_tuples([colunas_multi_index[c] for c in colunas_existentes])
                
                # 2. FUNÇÃO AUXILIAR CSS PARA PINTAR O CORPO DAS COLUNAS (OPCIONAL)
                # Caso queira pintar o fundo das linhas com tons bem claros seguindo o print
                def aplicar_cores_colunas(df):
                    estilos = pd.DataFrame('', index=df.index, columns=df.columns)
                    
                    for col in df.columns:
                        # Se a coluna pertencer ao grupo da Requisição (Verde bem claro)
                        if col[0] == "REQUISICAO DE MATERIAL MEGA":
                            estilos[col] = 'background-color: #e2f0d9; color: #000000;'
                        # Se a coluna pertencer ao Approval da RM (Verde Médio)
                        elif col[0] == "APPROVAL (RM)":
                            estilos[col] = 'background-color: #c6e0b4; color: #000000;'
                            
                    return estilos

                # 3. RENDERIZAÇÃO DA TABELA ESTILIZADA COM CSS INJETADO NO CABEÇALHO
                # Injeta CSS bruto para forçar o Streamlit a pintar as caixas superiores do cabeçalho
                st.markdown("""
                    <style>
                        /* Alvo: Primeira linha do super cabeçalho */
                        th.col_heading.level0 {
                            font-weight: bold !important;
                            color: #000000 !important;
                            text-align: center !important;
                        }
                        /* Bloco 1: Requisição Mega */
                        th.col_heading.level0.id0_9 { background-color: #e2f0d9 !important; }
                        /* Bloco 2: Approval RM */
                        th.col_heading.level0.id10_12 { background-color: #a9d08e !important; }
                    </style>
                """, unsafe_allow_html=True)

                # Aplica a estilização nas células de dados e renderiza
                df_estilizado = df_exibicao.style.apply(aplicar_cores_colunas, axis=None)
                
                st.dataframe(df_estilizado, use_container_width=True, hide_index=True)
                
        except Exception as e:
            st.error(f"❌ Erro ao processar a tabela do Cenário D: {e}")


# Execução automática nativa pelo Streamlit na navegação do menu lateral
if __name__ == "__main__":
    renderizar_cenario_d()
