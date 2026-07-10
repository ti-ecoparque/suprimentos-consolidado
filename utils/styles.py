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

    # Resgate do número do material estável
    df_final["mat"] = df_final["mat"].replace("---", None).fillna(df_final["mat_str"]).astype(str).str.strip()

    ordem_colunas_exibicao = ["nome_solicitante", "rm", "mat", "desc_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "comprador", "pedido_str", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc", "sit_item", "alerta_data"]
    colunas_multi_index = {
        "nome_solicitante": ("REQUISICAO DE MATERIAL MEGA", "Requisitante"), "rm": ("REQUISICAO DE MATERIAL MEGA", "Nr. RM"), "mat": ("REQUISICAO DE MATERIAL MEGA", "Nr. Material"), "desc_item": ("REQUISICAO DE MATERIAL MEGA", "Descrição"), "qtd_solicitada": ("REQUISICAO DE MATERIAL MEGA", "Qt. Sol."), "data_emissao": ("REQUISICAO DE MATERIAL MEGA", "Data da Requisição"), "data_necessidade": ("REQUISICAO DE MATERIAL MEGA", "Data da Nec."),
        "status_documento": ("APPROVAL (RM)", "Status da Aprovação"), "data_ocorrencia": ("APPROVAL (RM)", "Data da Aprovação"), "nome_aprovador": ("APPROVAL (RM)", "Aprovador"),
        "comprador": ("PEDIDO DE COMPRA MEGA", "Comprador"), "pedido_str": ("PEDIDO DE COMPRA MEGA", "Nr. PC"), "entrega": ("PEDIDO DE COMPRA MEGA", "Data de Entrega"), "quantidade_comprada": ("PEDIDO DE COMPRA MEGA", "Qt. Compr."),
        "status_pc": ("APPROVAL (PC)", "Status da Aprovação"), "data_ocorrencia_pc": ("APPROVAL (PC)", "Data da Aprovação"), "nome_aprovador_pc": ("APPROVAL (PC)", "Aprovador"),
        "sit_item": ("SITUAÇÃO DO ITEM", "Situação"), "alerta_data": ("ALERTA DE DATA", "Alerta de Entrega")
    }

    df_exibicao = df_final[ordem_colunas_exibicao].copy()
    df_exibicao.columns = pd.MultiIndex.from_tuples([colunas_multi_index[c] for c in ordem_colunas_exibicao])

    df_excel = df_final[ordem_colunas_exibicao].copy()
    df_excel.columns = [f"{colunas_multi_index[c]} - {colunas_multi_index[c]}" for c in ordem_colunas_exibicao]

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
        
        # Cria uma lista limpa com os nomes originais mapeados para bater a posição exata
        lista_colunas_mapeadas = list(df.columns)

        for col in df.columns:
            # 🔥 ENGENHARIA REVERSA DE ÍNDICES: Descobre matematicamente a posição da coluna de 0 a 18
            idx_coluna = lista_colunas_mapeadas.index(col)
            
            for i in df.index:
                pos_lista = mapa_indices.get(i)
                texto_celula = str(df.at[i, col]).strip()
                
                esta_atrasado = False
                esta_adiantado = False
                if pos_lista is not None and lista_entrega_dt_bruta[pos_lista] is not None and lista_necessidade_dt_bruta[pos_lista] is not None:
                    dias_diff = (lista_entrega_dt_bruta[pos_lista] - lista_necessidade_dt_bruta[pos_lista]).days
                    if dias_diff > 0: esta_atrasado = True
                    elif dias_diff < 0: esta_adiantado = True

                # 🌟 REGRA 1: Posição 18 é a coluna final de Alerta de Entrega
                if idx_coluna == 18:
                    if "DATA NÃO INFORMADA" in texto_celula.upper():
                        estilos.at[i, col] = 'background-color: #fff2cc; color: #7f6000; text-align: center;'
                    elif esta_atrasado:
                        estilos.at[i, col] = 'background-color: #fce4d6; color: #c65911; font-weight: bold; text-align: center;'
                    elif esta_adiantado:
                        estilos.at[i, col] = 'background-color: #e6f2ff; color: #1f4e78; font-weight: bold; text-align: center;'
                    else:
                        estilos.at[i, col] = 'background-color: #e2f0d9; color: #375623; text-align: center;'
                
                # 🌟 REGRA 2: Mapeamento matemático por blocos pastéis limpos baseados na posição
                else:
                    if 0 <= idx_coluna <= 6:     # REQUISICAO DE MATERIAL MEGA (0 a 6)
                        estilos.at[i, col] = 'background-color: #f2f7f2; color: #000000;'
                    elif 7 <= idx_coluna <= 9:   # APPROVAL (RM) (7 a 9)
                        estilos.at[i, col] = 'background-color: #e2f0d9; color: #000000;'
                    elif 10 <= idx_coluna <= 13: # PEDIDO DE COMPRA MEGA (10 a 13)
                        estilos.at[i, col] = 'background-color: #fbf2fa; color: #000000;'
                    elif 14 <= idx_coluna <= 16: # APPROVAL (PC) (14 a 16)
                        estilos.at[i, col] = 'background-color: #f3daf1; color: #000000;'
                    elif idx_coluna == 17:       # SITUAÇÃO DO ITEM (17)
                        estilos.at[i, col] = 'background-color: #e2efda; color: #375623; font-weight: bold; text-align: center;'
                    else:
                        estilos.at[i, col] = 'background-color: #ffffff; color: #000000;'
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
            th.col_heading.level1 { text-align: center !important; font-weight: normal !important; }
        </style>
    """, unsafe_allow_html=True)

    df_estilizado = df_exibicao.style.apply(aplicar_cores_corpo, axis=None)
    st.dataframe(df_estilizado, use_container_width=True, hide_index=True)
