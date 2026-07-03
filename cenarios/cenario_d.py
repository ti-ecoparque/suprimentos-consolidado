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
    Função padrão que renderiza a tela do Approvo Status.
    Aceita os parâmetros se vier da busca da Home, ou inicializa localmente se clicado no menu.
    """
    st.subheader("✅ Approvo Status — Cenário D")
    st.write("Monitore aqui o cruzamento das informações através da nova view `vw_nova`.")
    st.divider()

    # 2. SE NÃO PASSOU O CLIENTE DO SUPABASE (CLIQUE DIRETO NO MENU LATERAL), INICIALIZA LOCALMENTE
    if supabase is None:
        SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 3. FILTROS NA INTERFACE
    col1, col2 = st.columns(2)
    with col1:
        # Se o usuário já buscou uma RM na Home, ela já vem preenchida aqui
        buscar_rm = st.text_input("Filtrar por Número da RM:", value=rm_para_conferencia).strip()
    with col2:
        buscar_fornecedor = st.text_input("Buscar por Nome do Fornecedor:", "").strip()

    # 4. BUSCA DINÂMICA DE DADOS NA VW_NOVA
    with st.spinner("Consultando dados na view `vw_nova`..."):
        try:
            query = supabase.table("vw_nova").select("*")
            
            # Aplica os filtros se o operador preencher os campos
            if buscar_rm:
                query = query.eq("rm", int(buscar_rm))
            if buscar_fornecedor:
                query = query.ilike("fornecedor", f"%{buscar_fornecedor}%") # Ajuste o nome da coluna se necessário
                
            resposta = query.execute()
            dados = resposta.data
            
            if dados:
                df = pd.DataFrame(dados)
                
                # Se a função do Skinner_status foi passada e a coluna existir, aplica a estilização colorida
                if Skinner_status and "status" in df.columns:
                    # Aplica a sua função de cores nas linhas da tabela do Streamlit
                    st.dataframe(df.style.applymap(Skinner_status, subset=["status"]), use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum registro localizado para os filtros selecionados.")
                
        except Exception as e:
            st.error(f"❌ Erro ao processar o Cenário D: {e}")


# 5. EXECUÇÃO AUTOMÁTICA NATIVA DO STREAMLIT NATIVE PAGE
# Quando o usuário clica no menu lateral, o Streamlit executa o arquivo de cima a baixo.
# Esse bloco garante que a função principal seja disparada no clique direto do menu.
if __name__ == "__main__":
    renderizar_cenario_d()
