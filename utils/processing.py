import pandas as pd
import datetime

def processar_e_unificar_dados(df_rm_bruto, df_pc_bruto, df_vinculo, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_pc, filtro_periodo):
    cols_exclusivas_rm = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str", "seq_item"]

    # 1. Higienização das RMs da esquerda
    df_rm_limpo = pd.DataFrame(index=df_rm_bruto.index)
    for c in df_rm_bruto.columns:
        if c in cols_exclusivas_rm:
            s = df_rm_bruto[c].iloc[:, 0] if isinstance(df_rm_bruto[c], pd.DataFrame) else df_rm_bruto[c]
            df_rm_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
    df_rm_limpo["rm_str"] = df_rm_limpo.get("rm", "---")
    df_rm_limpo["mat_str"] = df_rm_limpo.get("mat", "---")
    df_rm_limpo["linha_id"] = df_rm_limpo.index.astype(str)

    # 2. Higienização da Tabela Comercial (Pedido de Compra Mega Direto!)
    df_pc_limpo = pd.DataFrame(index=df_pc_bruto.index)
    if not df_pc_bruto.empty:
        df_pc_bruto_copy = df_pc_bruto.copy()
        df_pc_bruto_copy["pedido_str"] = df_pc_bruto_copy.get("pedido", "---").astype(str).str.replace('.0', '', regex=False).str.strip()
        df_pc_bruto_copy["rm_str"] = df_pc_bruto_copy.get("rm", "---").astype(str).str.replace('.0', '', regex=False).str.strip()
        df_pc_bruto_copy["comprador_limpo"] = df_pc_bruto_copy.get("comprador", "---")
        df_pc_bruto_copy["entrega_limpa"] = df_pc_bruto_copy.get("entrega", "---")
        
        df_pc_bruto_copy["quantidade_comprada"] = "None"
        df_pc_bruto_copy["status_pc"] = "---"
        df_pc_bruto_copy["data_ocorrencia_pc"] = "---"
        df_pc_bruto_copy["nome_aprovador_pc"] = "---"

        cols_finais_pc = ["pedido_str", "rm_str", "comprador_limpo", "entrega_limpa", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]
        for c in df_pc_bruto_copy.columns:
            if c in cols_finais_pc:
                s = df_pc_bruto_copy[c].iloc[:, 0] if isinstance(df_pc_bruto_copy[c], pd.DataFrame) else df_pc_bruto_copy[c]
                df_pc_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()

    if "pedido_str" not in df_pc_limpo.columns: df_pc_limpo["pedido_str"] = "---"
    if "rm_str" not in df_pc_limpo.columns: df_pc_limpo["rm_str"] = "---"
    df_pc_limpo.rename(columns={"comprador_limpo": "comprador", "entrega_limpa": "entrega"}, inplace=True, errors="ignore")
    
    # 🌟 TRAVA ANTIDUPLICAÇÃO EXTRA: Remove duplicados olhando estritamente a RM na tabela de compras
    df_pc_limpo = df_pc_limpo.drop_duplicates(subset=["rm_str"]).copy()

    # 🌟 O CRUZAMENTO ABSOLUTO: Une horizontalmente os dados olhando ÚNICA e EXCLUSIVAMENTE o número da RM (rm_str)!
    df_final = pd.merge(df_rm_limpo, df_pc_limpo, on=["rm_str"], how="left")

    todas_colunas_vitais = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str", "pedido_str", "comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc", "linha_id"]
    for col in todas_colunas_vitais:
        if col not in df_final.columns: df_final[col] = "---"

    df_final["pedido_str"] = df_final["pedido_str"].fillna("---").astype(str).str.strip()
    df_final["comprador"] = df_final["comprador"].fillna("---").astype(str).str.strip()
    df_final["quantidade_comprada"] = df_final["quantidade_comprada"].replace("---", "None")

    # Filtros textuais via contains rápidos
    if buscar_rm:
        df_final = df_final[df_final["rm"].astype(str).str.contains(str(buscar_rm).strip(), na=False, regex=False)]
    if filtro_req != "Todos":
        df_final = df_final[df_final["nome_solicitante"].astype(str).str.contains(str(filtro_req).strip(), na=False, regex=False)]
    if filtro_comp != "Todos":
        df_final = df_final[df_final["comprador"].astype(str).str.contains(str(filtro_comp).strip(), na=False, regex=False)]

    df_final = df_final.drop_duplicates(subset=["linha_id"]).copy()

    # Cálculo de Datas Cronológico Rígido
    lista_alertas_data, lista_entrega_dt_bruta, lista_necessidade_dt_bruta, indices_para_manter = [], [], [], []
    ignorar_calendario = (buscar_rm != "") or (buscar_pc != "")
    
    possui_intervalo_valido = isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2
    data_inicio_filtro = filtro_periodo[0] if possui_intervalo_valido else None
    data_fim_filtro = filtro_periodo[1] if possui_intervalo_valido else None

    for idx in df_final.index:
        val_entrega = df_final.loc[idx, "entrega"]
        val_necessidade = df_final.loc[idx, "data_necessidade"]
        val_emissao = df_final.loc[idx, "data_emissao"]
        
        def conv(valor):
            if pd.isna(valor) or str(valor).strip() in ["", "---", "nan", "None", "NaT", "Data não informada"]: return None
            try:
                if hasattr(valor, "date"): return valor.date()
                t_str = str(valor).strip()[:10]
                if "-" in t_str: return datetime.datetime.strptime(t_str, "%Y-%m-%d").date()
                elif "/" in t_str: return datetime.datetime.strptime(t_str, "%d/%m/%Y").date()
            except Exception: pass
            return None

        dt_ent, dt_nec, dt_emi = conv(val_entrega), conv(val_necessidade), conv(val_emissao)

        if data_inicio_filtro and data_fim_filtro and not ignorar_calendario:
            if dt_emi is None or not (data_inicio_filtro <= dt_emi <= data_fim_filtro): continue

        indices_para_manter.append(idx)
        lista_entrega_dt_bruta.append(dt_ent)
        lista_necessidade_dt_bruta.append(dt_nec)

        if dt_ent is None or dt_nec is None: 
            lista_alertas_data.append("Data não informada")
        else:
            diferenca = (dt_ent - dt_nec).days
            if diferenca > 0: lista_alertas_data.append(f"Atraso de {diferenca} dias")
            elif diferenca < 0: lista_alertas_data.append(f"Adiantado {abs(diferenca)} dias")
            else: lista_alertas_data.append("No prazo")

    df_final = df_final.loc[indices_para_manter].copy()
    df_final["alerta_data"] = lista_alertas_data
    return df_final, lista_entrega_dt_bruta, lista_necessidade_dt_bruta
