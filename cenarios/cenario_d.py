import streamlit as st
import pandas as pd

# Se a sessão caiu (F5), tenta resgatar o usuário direto da URL antes de barrar o acesso
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


def renderizar_cenario_d(rm_para_conferencia, pedidos, supabase, skinner_status):
    st.subheader("📊 Cenário D — Análise Avançada de Suprimentos")
    st.write("Consulta consolidada de dados através da nova view corporativa `vw_nova`.")
    
    # ==========================================================
    # 🔍 1. FILTROS DINÂMICOS NA INTERFACE (SIDEBAR OU PAINEL)
    # ==========================================================
    st.markdown("### 🛠️ Filtros de Refinamento")
    
    # Criamos colunas para os filtros ficarem alinhados lado a lado
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Exemplo de Filtro 1: Status do Item
        status_opcoes = ["Todos", "Pendente", "Integrado", "Cancelado"]
        filtro_status = st.selectbox("Status do Item:", status_opcoes)
        
    with col2:
        # Exemplo de Filtro 2: Campo de busca de texto livre (ex: Descrição ou Fornecedor)
        busca_texto = st.text_input("Buscar por descrição ou palavra-chave:", "").strip()
        
    with col3:
        # Exemplo de Filtro 3: Filtro numérico ou caixas de seleção adicionais
        apenas_com_divergencia = st.checkbox("Exibir apenas itens com divergência", value=False)

    # ==========================================================
    # 🚀 2. CONSTRUÇÃO DA QUERY DINÂMICA (SUPABASE)
    # ==========================================================
    with st.spinner("Carregando e aplicando filtros na view `vw_nova`..."):
        try:
            # Inicializa a query apontando para a sua nova view 'vw_nova'
            query = supabase.table("vw_nova").select("*")
            
            # Filtro base obrigatório passado por parâmetro na função (se a view usar a coluna 'rm')
            if rm_para_conferencia:
                query = query.eq("rm", rm_para_conferencia)
            
            # Aplica o filtro de Status se não for "Todos"
            if filtro_status != "Todos":
                query = query.eq("status_descricao", filtro_status) # Ajuste o nome da coluna conforme sua view
                
            # Aplica busca por texto aproximado (ILIKE ignora maiúsculas/minúsculas)
            if busca_texto:
                query = query.ilike("descricao_item", f"%{busca_texto}%") # Ajuste o nome da coluna conforme sua view

            # Executa a consulta de forma otimizada
            resposta_nova = query.execute()
            dados_vw_nova = resposta_nova.data
            
        except Exception as e:
            st.error(f"❌ Erro ao consultar a view `vw_nova` no Supabase: {e}")
            dados_vw_nova = []

    # ==========================================================
    # 📦 3. EXIBIÇÃO E PROCESSAMENTO DOS RESULTADOS
    # ==========================================================
    if dados_vw_nova:
        df_nova = pd.DataFrame(dados_vw_nova)
        
        # Filtro em memória via Pandas para regras que dependem de cálculos complexos
        if apenas_com_divergencia and "qtd_solicitada" in df_nova.columns and "qtd_atendida" in df_nova.columns:
            df_nova = df_nova[df_nova["qtd_solicitada"] != df_nova["qtd_atendida"]]
            
        st.success(f"✔️ **{len(df_nova)}** registro(s) localizado(s) com os filtros aplicados.")
        
        # Exibe a tabela formatada na tela
        st.dataframe(df_nova, use_container_width=True, hide_index=True)
        
        # Retorna o DataFrame tratado caso os outros arquivos usem esse resultado
        return df_nova
    else:
        st.info("✨ Nenhum registro encontrado para os critérios de busca selecionados.")
        return pd.DataFrame()
