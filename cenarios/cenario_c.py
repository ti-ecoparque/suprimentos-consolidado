# Código focado na busca por período e status das RMs
# cenarios/cenario_c.py
import streamlit as st
import pandas as pd

def renderizar_cenario_c(periodo, status_selecionados, supabase, Skinner_status):
    # Validação do intervalo de datas do Streamlit
    if len(periodo) != 2:
        st.warning("⏳ Por favor, selecione a data de início e a data de término no calendário.")
        st.stop()
        
    data_inicio, data_fim = periodo[0].strftime("%Y-%m-%d"), periodo[1].strftime("%Y-%m-%d")
    
    if not status_selecionados:
        st.warning("⚠️ Selecione ao menos um Status para realizar a filtragem por período.")
        st.stop()

    with st.spinner("Buscando dados do período no Supabase..."):
        resposta_periodo = (
            supabase
            .table("vw_conferencia_rm")  # Reutiliza a View unificada de conferência
            .select("*")
            .gte("data_emissao", data_inicio)
            .lte("data_emissao", data_fim)
            .in_("status_atendimento", status_selecionados)
            .execute()
        )
        dados_periodo = resposta_periodo.data

    if not dados_periodo:
        st.info("✨ Nenhuma Requisição de Material (RM) localizada para o período e status selecionados.")
        st.stop()

    df_periodo = pd.DataFrame(dados_periodo)
    df_periodo.columns = df_periodo.columns.str.lower()

    # Exibe resumo do volume localizado
    rms_unicas = df_periodo["rm"].nunique() if "rm" in df_periodo.columns else 0
    st.success(f"📊 Encontrada(s) **{rms_unicas}** RM(s) no período selecionado.")

    # Padronização e formatação de tipos de colunas para exibição amigável
    for col in ["rm", "mat", "qtd_solicitada", "qtd_comprada"]:
        if col in df_periodo.columns:
            df_periodo[col] = pd.to_numeric(df_periodo[col], errors="coerce").fillna(0).astype(int)

    if "data_emissao" in df_periodo.columns:
        df_periodo["data_emissao"] = pd.to_datetime(df_periodo["data_emissao"], errors="coerce").dt.strftime("%d/%m/%Y")

    df_visual = df_periodo.rename(columns={
        "rm": "RM",
        "pedido": "Pedidos Gerados",
        "mat": "Material",
        "desc_item": "Descrição do Item",
        "data_emissao": "Data Emissão",
        "qtd_solicitada": "Qtd Solicitada",
        "qtd_comprada": "Qtd Comprada",
        "status_atendimento": "Status"
    })

    colunas_final = ["RM", "Data Emissão", "Material", "Descrição do Item", "Qtd Solicitada", "Qtd Comprada", "Pedidos Gerados", "Status"]
    colunas_validas = [c for c in colunas_final if c in df_visual.columns]
    df_filtrado = df_visual[colunas_validas].copy()

    # Ordena o relatório por número da RM e depois pelo Código do Material
    if "RM" in df_filtrado.columns and "Material" in df_filtrado.columns:
        df_filtrado = df_filtrado.sort_values(by=["RM", "Material"], ascending=[False, True])

    st.dataframe(
        df_filtrado.style.map(Skinner_status, subset=['Status']),
        use_container_width=True,
        hide_index=True
    )
