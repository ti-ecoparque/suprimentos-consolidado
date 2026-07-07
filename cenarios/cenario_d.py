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
    Função padrão que renderiza a tela do Approvo Status (Cenário D).
    Realiza a leitura da nova view de ocorrências históricas vw_approvo_rm.
    """
    st.subheader("✅ Approvo Status — Cenário D")
    st.write("Histórico completo de ocorrências e assinaturas de aprovação por RM.")
    st.divider()

    # 2. INICIALIZAÇÃO LOCAL DO BANCO (SE CLICADO PELO MENU LATERAL)
    if supabase is None:
        SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 3. FILTROS AVANÇADOS NA INTERFACE
    col1, col2, col3 = st.columns(3)
    with col1:
        buscar_rm = st.text_input("Filtrar por Número da RM:", value=rm_para_conferencia).strip()
    with col2:
        buscar_aprovador = st.text_input("Buscar por Nome do Aprovador:", "").strip()
    with col3:
        filtro_status_doc = st.selectbox("Status no Approvo:", ["Todos", "Aprovado", "Rejeitado", "Pendente"])

    # 4. CONSULTA DOS DADOS NA NOVA VIEW
    with st.spinner("Consultando histórico na view `vw_approvo_rm`..."):
        try:
            # Aponta para a nova view criada
            query = supabase.table("vw_approvo_rm").select("*")
            
            # Aplicação dos filtros dinâmicos
            if buscar_rm:
                query = query.eq("rm", str(buscar_rm))
            if buscar_aprovador:
                query = query.ilike("nome_aprovador", f"%{buscar_aprovador}%")
            if filtro_status_doc != "Todos":
                query = query.eq("status_documento", filtro_status_doc)
                
            resposta = query.execute()
            dados = resposta.data
            
            if dados:
                df = pd.DataFrame(dados)
                
                # Formata as datas para exibição legível na tabela brasileira
                if "data_ocorrencia" in df.columns:
                    df["data_ocorrencia"] = pd.to_datetime(df["data_ocorrencia"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")
                
                # Ordena os registros para mostrar sempre os itens na sequência correta do documento
                if "seq_item" in df.columns:
                    df = df.sort_values(by="seq_item")
                    
                # Exibe a tabela estruturada na tela
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum histórico de ocorrência localizado para os critérios aplicados.")
                
        except Exception as e:
            st.error(f"❌ Erro ao processar a consulta do Cenário D: {e}")


# Execução nativa se clicado direto no menu lateral esquerdo
if __name__ == "__main__":
    renderizar_cenario_d()
