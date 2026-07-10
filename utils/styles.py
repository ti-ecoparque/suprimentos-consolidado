import pandas as pd
import streamlit as st
import datetime
import io

def renderizar_grid_multiindex_colorido(df_final, lista_entrega_dt_bruta, lista_necessidade_dt_bruta):
    if "status_documento" in df_final.columns:
        df_final["status_documento"] = df_final["status_documento"].map(lambda x: {"A":"Aprovado","E":"Em Aprovação","R":"Reprovado"}.get(str(x).strip().upper(), "---") if pd.notna(x) else "---")
    if "status_pc" in df_final.columns:
        df_final["status_pc"] = df_final["status_pc"].map(lambda x: {"A":"Aprovado","E":"Em Aprovação","R":"Reprovado"}.get(str(x).strip().upper(), "---") if pd.notna(x) else "---")

    df_final["qtd_solicitada"] = pd.to_numeric(df_final["qtd_solicitada"], errors="coerce").fillna(0).astype(int)
    df_final["quantidade_comprada"] = pd.to_numeric(df_final["quantidade_comprada"], errors="coerce").fillna(0).astype(int)

    def formatar_visual_seguro(valor, incluir_hora=False):
        if pd.isna(valor) or str(valor).strip() in ["", "---", "nan", "None", "NaT"]: return "Data não informada"
        try:
            if hasattr(valor, "strftime"): return valor.strftime("%d/%m/%Y %H:%M" if incluir_hora else "%d/%m/%Y")
            t_str = str(valor).strip()[:10]
            if "-" in t_str: return datetime.datetime.strptime(t_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            return valor
        except Exception: pass
        return "Data não informada"

    for col in ["data_emissao", "data_necessidade", "entrega"]:
        if col in df_final.columns: df_final[col] = df_final[col].apply(lambda x: formatar_visual_seguro(x, incluir_hora=False))
    for col in ["data_ocorrencia", "data_ocorrencia_pc"]:
        if col in df_final.columns: df_final[col] = df_final[col].apply(lambda x: formatar_visual_seguro(x, incluir_hora=True))

    ordem_colunas_exibicao = ["nome_solicitante", "rm", "mat", "desc_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "comprador", "pedido_str", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc", "sit_item", "alerta_data"]
    colunas_multi_index = {
        "nome_solicitante": ("REQUISICAO DE MATERIAL MEGA", "Requisitante"), "rm": ("REQUISICAO DE MATERIAL MEGA", "Nr. RM"), "mat": ("REQUISICAO DE MATERIAL MEGA", "Nr. Material"), "desc_item": ("REQUISICAO DE MATERIAL MEGA", "Descrição"), "qtd_solicitada": ("REQUISICAO DE MATERIAL MEGA", "Qt. Sol."), "data_emissao": ("REQUISICAO DE MATERIAL MEGA", "Data da Requisição"), "data_necessidade": ("REQUISICAO DE MATERIAL MEGA", "Data da Nec."),
        "status_documento": ("APPROVAL (RM)", "Status da Aprovação"), "data_ocorrencia": ("APPROVAL (RM)", "Data da Aprovação"), "nome_aprovador": ("APPROVAL (RM)", "Aprovador"),
        "comprador": ("PEDIDO DE COMPRA MEGA", "Comprador"), "pedido_str": ("PEDIDO DE COMPRA MEGA", "Nr. PC"), "entrega": ("PEDIDO DE COMPRA MEGA", "Data de Entrega"), "quantidade_comprada": ("PEDIDO DE COMPRA MEGA", "Qt. Compr."),
        "status_pc": ("APPROVAL (PC)", "Status da Aprovação"), "data_ocorrencia_pc": ("APPROVAL (PC)", "Data da Aprovação"), "nome_aprovador_pc": ("APPROVAL (PC)", "Aprovador"),
        "sit_item": ("SITUAÇÃO DO ITEM", "Situação"), "alerta_data": ("ALERTA DE DATA", "Alerta de Entrega")
    }

    # 1. Cria a base estável para visualização no Streamlit (Mantém o MultiIndex na tela)
    df_exibicao = df_final[ordem_colunas_exibicao].copy()
    df_exibicao.columns = pd.MultiIndex.from_tuples([colunas_multi_index[c] for c in ordem_colunas_exibicao])

    # 2. Cria uma cópia limpa e achata o cabeçalho exclusivamente para salvar no Excel (.xlsx)
    df_excel = df_final[ordem_colunas_exibicao].copy()
    df_excel.columns = [f"{colunas_multi_index[c][0]} - {colunas_multi_index[c][1]}" for c in ordem_colunas_exibicao]

    # 📥 GERAÇÃO CONSOLIDADA EM BYTES IMUNE A ERROS
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_excel.to_excel(writer, index=False, sheet_name='Approvo Status')
    dados_excel = output.getvalue()

    st.download_button(
        label="📥 Exportar Painel para o Excel (.xlsx)",
        data=dados_excel,
        file_name=f"approvo_status_{datetime.date.today().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
    st.divider()

    def aplicar_cores_corpo(df):
        estilos = pd.DataFrame('', index=df.index, columns=df.columns)
        mapa_indices = {orig_idx: pos for pos, orig_idx in enumerate(df_final.index) if orig_idx in df.index}
        for col in df.columns:
            grupo = col
            for i in df.index:
                pos_lista = mapa_indices.get(i)
                tem_atraso = lista_entrega_dt_bruta[pos_lista] is not None and lista_necessidade_dt_bruta[pos_lista] is not None and (lista_entrega_dt_bruta[pos_lista] > lista_necessidade_dt_bruta[pos_lista]) if pos_lista is not None else False
                if tem_atraso: estilos.at[i, col] = 'background-color: #fce4d6; color: #000000;'
                else:
                    if grupo == "REQUISICAO DE MATERIAL MEGA": estilos.at[i, col] = 'background-color: #f2f7f2; color: #000000;'
                    elif grupo == "APPROVAL (RM)": estilos.at[i, col] = 'background-color: #e2f0d9; color: #000000;'
                    elif grupo == "PEDIDO DE COMPRA MEGA": estilos.at[i, col] = 'background-color: #fbf2fa; color: #000000;'
                    elif grupo == "APPROVAL (PC)": estilos.at[i, col] = 'background-color: #f3daf1; color: #000000;'
                if not tem_atraso:
                    if grupo == "SITUAÇÃO DO ITEM": estilos.at[i, col] = 'background-color: #a9d08e; color: #000000; font-weight: bold; text-align: center;'
                    elif grupo == "ALERTA DE DATA": estilos.at[i, col] = 'background-color: #fff2cc; color: #000000; text-align: center;'
        return estilos

    st.markdown("""
        <style>
            th.col_heading.level0 { font-weight: bold !important; color: #000000 !important; text-align: center !important; }
            th.col_heading.level0.id0_6 { background-color: #e2f0d9 !important; }
            th.col_heading.level0.id7_9 { background-color: #a9d08e !important; }
            th.col_heading.level0.id10_13 { background-color: #f2dcfa !important; }
            th.col_heading.level0.id14_16 { background-color: #df9ff2 !important; }
            th.col_heading.level0.id17 { background-color: #a9d08e !important; color: #000000 !important; }
            th.col_heading.level0.id18 { background-color: #ffe599 !important; }
            th.col_heading.level1 { text-align: center !important; }
        </style>
    """, unsafe_allow_html=True)

    df_estilizado = df_exibicao.style.apply(aplicar_cores_corpo, axis=None)
    st.dataframe(df_estilizado, use_container_width=True, hide_index=True)
