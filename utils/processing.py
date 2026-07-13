import pandas as pd
import datetime

def processar_e_unificar_dados(df_rm_bruto, df_pc_bruto, df_vinculo, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_pc, filtro_periodo):
    cols_exclusivas_rm = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str", "seq_item"]
    
    # 1. Limpeza RM
    df_rm_limpo = pd.DataFrame(index=df_rm_bruto.index)
    for c in df_rm_bruto.columns:
        if c in cols_exclusivas_rm:
            s = df_rm_bruto[c].iloc[:, 0] if isinstance(df_rm_bruto[c], pd.DataFrame) else df_rm_bruto[c]
            df_rm_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
    df_rm_limpo["rm_str"] = df_rm_limpo.get("rm", "---")
    df_rm_limpo["mat_str"] = df_rm_limpo.get("mat", "---")
    df_rm_limpo = df_rm_limpo.drop_duplicates().copy()

    # 2. Limpeza Vínculos
    if not df_vinculo.empty:
        df_vinculo_limpo = pd.DataFrame(index=df_vinculo.index)
        for c in ["rm", "pedido"]:
            if c in df_vinculo.columns:
                s = df_vinculo[c].iloc[:, 0] if isinstance(df_vinculo[c], pd.DataFrame) else df_vinculo[c]
                df_vinculo_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
        df_vinculo_limpo["rm_str"] = df_vinculo_limpo.get("rm", "---")
        df_vinculo_limpo["pedido_str"] = df_vinculo_limpo.get("pedido", "---")
        df_rm_consolidada = pd.merge(df_rm_limpo, df_vinculo_limpo[["rm_str", "pedido_str"]], on="rm_str", how="outer")
    else:
        df_rm_consolidada = df_rm_limpo.copy()
        df_rm_consolidada["pedido_str"] = "---"

    # 3. Limpeza PC
    df_pc_limpo = pd.DataFrame(index=df_pc_bruto.index)
    if not df_pc_bruto.empty:
        df_pc_bruto_copy = df_pc_bruto.copy()
        df_pc_bruto_copy["pedido_str"] = df_pc_bruto_copy.get("pedido", "---")
        df_pc_bruto_copy["mat_str"] = df_pc_bruto_copy.get("mat", "---")
        df_pc_bruto_copy["comprador_limpo"] = df_pc_bruto_copy.get("comprador", "---")
        df_pc_bruto_copy["status_pc"] = df_pc_bruto_copy.get("status_documento", "---")
        df_pc_bruto_copy["data_ocorrencia_pc"] = df_pc_bruto_copy.get("data_oficial_ocorrencia", df_pc_bruto_copy.get("data_ocorrencia", "---"))
        df_pc_bruto_copy["nome_aprovador_pc"] = df_pc_bruto_copy.get("nome_aprovador", "---")
        df_pc_bruto_copy["quantidade_comprada"] = df_pc_bruto_copy.get("whitespace_qty", df_pc_bruto_copy.get("quantidade", 0))

        cols_finais_pc = ["pedido_str", "mat_str", "comprador_limpo", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]
        for c in df_pc_bruto_copy.columns:
            if c in cols_finais_pc:
                s = df_pc_bruto_copy[c].iloc[:, 0] if isinstance(df_pc_bruto_copy[c], pd.DataFrame) else df_pc_bruto_copy[c]
                df_pc_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()

    if "pedido_str" not in df_pc_limpo.columns: df_pc_limpo["pedido_str"] = "---"
    if "mat_str" not in df_pc_limpo.columns: df_pc_limpo["mat_str"] = "---"
    if "comprador_limpo" not in df_pc_limpo.columns: df_pc_limpo["comprador_limpo"] = "---"
    df_pc_limpo.rename(columns={"comprador_limpo": "comprador"}, inplace=True, errors="ignore")
    df_pc_limpo = df_pc_limpo.drop_duplicates().copy()

    # Cruzamento flexível por material de hoje de manhã
    df_final = pd.merge(df_rm_consolidada, df_pc_limpo, on=["mat_str"], how="outer")

    if "pedido_str_y" in df_final.columns:
        df_final["pedido_str"] = df_final["pedido_str_y"].replace("---", "").fillna(df_final.get("pedido_str_x", "---"))
    elif "pedido_str_x" in df_final.columns:
        df_final["pedido_str"] = df_final["pedido_str_x"]

    todas_colunas_vitais = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str", "pedido_str", "comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]
    for col in todas_colunas_vitais:
        if col not in df_final.columns: df_final[col] = "---"

    s_final_rm = df_final["rm"].iloc[:, 0] if isinstance(df_final["rm"], pd.DataFrame) else df_final["rm"]
    s_final_mat = df_final["mat"].iloc[:, 0] if isinstance(df_final["mat"], pd.DataFrame) else df_final["mat"]
    df_final["rm"] = s_final_rm.fillna(df_final.get("rm_str", "---")).astype(str).str.strip()
    df_final["mat"] = s_final_mat.fillna(df_final.get("mat_str", "---")).astype(str).str.strip()

    df_final["pedido_str"] = df_final["pedido_str"].fillna("---").astype(str).str.strip()
    df_final["nome_solicitante"] = df_final["nome_solicitante"].fillna("---").astype(str).str.strip()
    df_final["comprador"] = df_final["comprador"].fillna("---").astype(str).str.strip()

    if buscar_rm:
        df_final = df_final[df_final["rm"].str.contains(str(buscar_rm).strip(), na=False, regex=False)]
    if filtro_req != "Todos":
        df_final = df_final[df_final["nome_solicitante"] == str(filtro_req).strip()]
    if filtro_comp != "Todos":
        df_final = df_final[df_final["comprador"] == str(filtro_comp).strip()]
    if buscar_pc and str(buscar_pc).strip() not in ["", "---", "nan", "None"]:
        df_final = df_final[df_final["pedido_str"].str.contains(str(buscar_pc).strip(), na=False, regex=False)]
    if filtro_status_pc != "Todos":
        df_final = df_final[df_final["status_pc"].astype(str).str.strip().str.upper() == {"Aprovado":"A","Em Aprovação":"E","Reprovado":"R"}[filtro_status_pc].upper()]

    df_final["seq_item"] = df_final.get("seq_item", pd.Series(dtype=str, index=df_final.index)).fillna("---").astype(str)
    df_final["rm_mat_seq_key"] = df_final["rm"].astype(str) + "_" + df_final["mat"].astype(str) + "_" + df_final["seq_item"]
    df_final = df_final.drop_duplicates(subset=["rm_mat_seq_key"]).copy()

    # Cálculo de Datas
    lista_alertas_data, lista_entrega_dt_bruta, lista_necessidade_dt_bruta, indices_para_manter = [], [], [], []
    ignorar_calendario = (buscar_rm != "") or (buscar_pc != "")
    
    # 🌟 CORREÇÃO DO FILTRO: Extrai explicitamente a posição [0] e [1] da lista de datas
    data_inicio_filtro = filtro_periodo[0] if isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2 else None
    data_fim_filtro = filtro_periodo[1] if isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2 else None

    for idx in df_final.index:
        val_entrega = df_final.loc[idx, "entrega"]
        val_necessidade = df_final.loc[idx, "data_necessidade"]
        val_emissao = df_final.loc[idx, "data_emissao"]
        
        def conv(valor):
            if pd.isna(valor) or str(valor).strip() in ["", "---", "nan", "None", "NaT"]: return None
            try:
                if hasattr(valor, "date"): return valor.date()
                t_str = str(valor).strip()[:10]
                if "-" in t_str: return datetime.datetime.strptime(t_str, "%Y-%m-%d").date()
                elif "/" in t_str: return datetime.datetime.strptime(t_str, "%d/%m/%Y").date()
            except Exception: pass
            return None

        dt_ent, dt_nec, dt_emi = conv(val_entrega), conv(val_necessidade), conv(val_emissao)

        if not ignorar_calendario and data_inicio_filtro and data_fim_filtro:
            if dt_emi is None or not (data_inicio_filtro <= dt_emi <= data_fim_filtro): continue

        indices_para_manter.append(idx)
        lista_entrega_dt_bruta.append(dt_ent)
        lista_necessidade_dt_bruta.append(dt_nec)

        if dt_ent is None or dt_nec is None: lista_alertas_data.append("Data não informada")
        else:
            diferenca = (dt_ent - dt_nec).days
            if diferenca > 0: lista_alertas_data.append(f"Atraso de {diferenca} dias")
            elif diferenca < 0: lista_alertas_data.append(f"Adiantado {abs(diferenca)} dias")
            else: lista_alertas_data.append("No prazo")

    df_final = df_final.loc[indices_para_manter].copy()
    df_final["alerta_data"] = lista_alertas_data
    return df_final, lista_entrega_dt_bruta, lista_necessidade_dt_bruta
