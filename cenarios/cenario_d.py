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

                # 🚨 FILTRO E RENOMEAÇÃO DE COLUNAS PARA O LAYOUT EXECUTIVO SOLICITADO
                # Dicionário mapeia: 'nome_na_view': 'Nome que você quer na tela'
                colunas_mapeadas = {
                    "nome_solicitante": "Requisitante",
                    "rm":               "Nr RM",
                    "desc_item":        "Descrição",
                    "data_emissao":     "Dt Requisição",
                    "data_necessidade": "Dt Necessidade",
                    "status_documento": "Status RM",
                    "data_ocorrencia":  "Data Aprovação",
                    "nome_aprovador":   "Aprovador"
                }
                
                # Garante que só tentará exibir colunas que realmente existem no DataFrame
                colunas_existentes = [col for col in colunas_mapeadas.keys() if col in df_bruto.columns]
                
                # Filtra apenas as colunas desejadas na ordem estipulada
                df_exibicao = df_bruto[colunas_existentes].copy()
                
                # Aplica os novos títulos amigáveis
                df_exibicao.rename(columns=colunas_mapeadas, inplace=True)
                
                # Organiza a exibição visual na tela do Streamlit
                st.write(f"📋 Exibindo **{len(df_exibicao)}** registro(s) da requisição:")
                st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
                
            else:
                st.info("Nenhum dado localizado para os critérios selecionados.")
                
        except Exception as e:
            st.error(f"❌ Erro ao processar a tabela do Cenário D: {e}")


# Execução automática nativa pelo Streamlit na navegação do menu lateral
if __name__ == "__main__":
    renderizar_cenario_d()
