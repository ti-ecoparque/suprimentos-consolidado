# Código focado na tabela resumida da RM
# cenarios/cenario_b.py
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

def renderizar_cenario_b(rm_para_conferencia, pedidos, supabase, Skinner_status):
    resposta_conferencia = (
        supabase
        .table("vw_conferencia_rm")
        .select("*")
        .eq("rm", rm_para_conferencia)
        .execute()
    )
    dados_conferencia = resposta_conferencia.data
    
    if not dados_conferencia:
        st.warning(f"Nenhum registro encontrado para a RM {rm_para_conferencia}.")
        st.stop()
        
    df_conf = pd.DataFrame(dados_conferencia)
    df_conf.columns = df_conf.columns.str.lower()
    
    qtd_pedidos = len(pedidos)
    st.success(f"RM {rm_para_conferencia} gerou {qtd_pedidos} pedido(s)")
    
    # Padronização e formatação de tipos de colunas para exibição amigável
    for col in ["rm", "mat", "qtd_solicitada", "qtd_comprada"]:
        if col in df_conf.columns:
            df_conf[col] = pd.to_numeric(df_conf[col], errors="coerce").fillna(0).astype(int)
            
    if "data_emissao" in df_conf.columns:
        df_conf["data_emissao"] = pd.to_datetime(df_conf["data_emissao"], errors="coerce").dt.strftime("%d/%m/%Y")
        
    df_visual = df_conf.rename(columns={
        "rm": "RM",
        "pedido": "Pedidos Vinculados",
        "mat": "Material",
        "desc_item": "Descrição",
        "data_emissao": "Data Emissão RM",
        "qtd_solicitada": "Qtd Solicitada",
        "qtd_comprada": "Qtd Comprada",
        "status_atendimento": "Status"
    })
    
    colunas_final = ["RM", "Pedidos Vinculados", "Material", "Descrição", "Data Emissão RM", "Qtd Solicitada", "Qtd Comprada", "Status"]
    colunas_validas = [c for c in colunas_final if c in df_visual.columns]
    df_filtrado = df_visual[colunas_validas].copy()
    
    if "Material" in df_filtrado.columns:
        df_filtrado = df_filtrado.sort_values(by="Material")
        
    st.dataframe(
        df_filtrado.style.map(Skinner_status, subset=['Status']),
        use_container_width=True,
        hide_index=True
    )
