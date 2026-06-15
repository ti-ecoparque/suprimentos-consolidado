# cenarios/cenario_c.py
import streamlit as st
import pandas as pd

def renderizar_cenario_c(periodo, status_selecionados, supabase, Skinner_status):
    if len(periodo) != 2:
        st.warning("Por favor, selecione as duas datas (Início e Fim) no calendário.")
        st.stop()
        
    if not status_selecionados:
        st.warning("Por favor, marque ao menos um Status antes de executar a busca.")
        st.stop()
        
    data_inicio = periodo[0].strftime("%Y-%m-%d")
    data_fim = periodo[1].strftime("%Y-%m-%d")
    
    resposta_periodo = (
        supabase
        .table("vw_conferencia_rm")
        .select("*")
        .gte("data_emissao", data_inicio)
        .lte("data_emissao", data_fim)
        .in_("status_atendimento", status_selecionados)
        .execute()
    )
    dados_periodo = resposta_periodo.data
    
    if not dados_periodo:
        st.info("Nenhuma RM localizada no período informado para os filtros selecionados.")
        st.stop()
        
    df_periodo = pd.DataFrame(dados_periodo)
    df_periodo.columns = df_periodo.columns.str.lower()
    
    st.success(f"Mapeada(s) {df_periodo['rm'].nunique()} RM(s) distintas no período consultado.")
    
    for col in ["rm", "mat", "qtd_solicitada", "qtd_comprada"]:
        if col in df_periodo.columns:
            df_periodo[col] = pd.to_numeric(df_periodo[col], errors="coerce").fillna(0).astype(int)
            
    if "data_emissao" in df_periodo.columns:
        df_periodo["data_emissao"] = pd.to_datetime(df_periodo["data_emissao"], errors="coerce").dt.strftime("%d/%m/%Y")
        
    df_visual = df_periodo.rename(columns={
        "rm": "RM",
        "pedido": "Pedidos Vinculados",
        "mat": "Material",
        "desc_item": "Descrição",
        "data_emissao": "Data Emissão",
        "qtd_solicitada": "Qtd Solicitada",
        "qtd_comprada": "Qtd Comprada",
        "status_atendimento": "Status"
    })
    
    colunas_final = ["RM", "Pedidos Vinculados", "Material", "Descrição", "Data Emissão", "Qtd Solicitada", "Qtd Comprada", "Status"]
    colunas_validas = [c for c in colunas_final if c in df_visual.columns]
    df_filtrado = df_visual[colunas_validas].copy()
    
    if "RM" in df_filtrado.columns:
        df_filtrado = df_filtrado.sort_values(by=["RM", "Material"])
        
    st.dataframe(
        df_filtrado.style.map(Skinner_status, subset=['Status']),
        use_container_width=True,
        hide_index=True
    )
