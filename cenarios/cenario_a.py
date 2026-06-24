# Código focado na renderização do Pedido Unificado
# cenarios/cenario_a.py
import streamlit as st
import pandas as pd

# Se a sessão caiu (F5), tenta resgatar o usuário direto da URL antes de barrar o acesso
if "logado" not in st.session_state or not st.session_state.logado:
    usuario_url = st.query_params.get("u")
    
    if usuario_url:
        # Se achou o parâmetro na URL, revalida e loga em segundo plano de forma invisível
        st.session_state.logado = True
        st.session_state.usuario_atual = usuario_url
    else:
        # Se realmente não tiver a chave de login na URL, bloqueia o acesso
        st.warning("⚠️ Acesso restrito. Por favor, faça login na tela inicial antes de continuar.")
        if st.button("Ir para a Tela de Login"):
            st.switch_page("app.py")
        st.stop()

def renderizar_cenario_a(pedido, pedidos, rm_para_conferencia, supabase, Skinner_status):
    resposta_itens = (
        supabase
        .table("vw_pedidos")
        .select("*")
        .in_("pedido", pedidos)
        .execute()
    )
    dados_itens = resposta_itens.data
    
    if not dados_itens:
        st.warning(f"Pedido {pedido} não possui itens cadastrados.")
        st.stop()
        
    df = pd.DataFrame(dados_itens)
    df.columns = df.columns.str.lower()
    
    colunas_seguras = [c for c in ["pedido", "mat", "quantidade", "desc_item", "nome_fantasia", "cnpj", "total_pedido"] if c in df.columns]
    df = df.drop_duplicates(subset=colunas_seguras).copy()
    
    for col in ["pedido", "quantidade", "mat"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
            
    for col_data in ["emissao", "entrega"]:
        if col_data in df.columns:
            df[col_data] = pd.to_datetime(df[col_data], errors="coerce").dt.strftime("%d/%m/%Y")
            
    if "total_pedido" in df.columns:
        df["total_pedido"] = pd.to_numeric(df["total_pedido"], errors="coerce").fillna(0)
        df["total_pedido"] = df["total_pedido"].map(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        df["total_pedido"] = df["total_pedido"].where(~df.duplicated(subset=["pedido"]), "")
            
    st.success(f"Pedido {pedido} encontrado com {len(df)} itens")
    
    nome_filial = df["nome_filial"].iloc[0] if "nome_filial" in df.columns and not df.empty else ""
    data_consulta = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")
    
    inf_col1, inf_col2, inf_col3, inf_col4 = st.columns(4)
    with inf_col1:
        st.markdown(f"**RM:** {rm_para_conferencia}")
    with inf_col2:
        st.markdown(f"**Pedido:** {pedido}")
    with inf_col3:
        st.markdown(f"**Filial:** {nome_filial}")
    with inf_col4:
        st.markdown(f"**Data da Consulta:** {data_consulta}")
        
    st.divider()
    
    df_visual = df.rename(columns={
        "pedido": "Pedido",
        "mat": "Material",
        "desc_item": "Descrição",
        "quantidade": "Qtd Solicitada",
        "emissao": "Emissão",
        "entrega": "Entrega",
        "situacao_pedido": "Status",
        "nome_fantasia": "Fornecedor",
        "cnpj": "CNPJ",
        "total_pedido": "Valor Total"
    })
    
    colunas_final = ["Pedido", "Material", "Descrição", "Qtd Solicitada", "Emissão", "Entrega", "Valor Total", "Fornecedor", "CNPJ", "Status"]
    colunas_validas = [c for c in colunas_final if c in df_visual.columns]
    df_filtrado = df_visual[colunas_validas].copy()
    
    if "Material" in df_filtrado.columns:
        df_filtrado = df_filtrado.sort_values(by="Material")
        
    st.dataframe(
        df_filtrado.style.map(Skinner_status, subset=['Status']), 
        use_container_width=True, 
        hide_index=True
    )
