import pandas as pd
import datetime

def processar_e_unificar_dados(df_rm_bruto, df_pc_bruto, df_vinculo, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_pc, filtro_periodo):
    cols_exclusivas_rm = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str", "seq_item"]

    # 1. Higienização das RMs da esquerda (REQUISICAO e APPROVAL RM) - TOTALMENTE PRESERVADO
    df_rm_limpo = pd.DataFrame(index=df_rm_bruto.index)
    for c in df_rm_bruto.columns:
        if c in cols_exclusivas_rm:
            s = df_rm_bruto[c].iloc[:, 0] if isinstance(df_rm_bruto[c], pd.DataFrame) else df_rm_bruto[c]
            df_rm_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
    df_rm_limpo["rm_str"] = df_rm_limpo.get("rm", "---")
    df_rm_limpo["mat_str"] = df_rm_limpo.get("mat", "---")
    df_rm_limpo["linha_id"] = df_rm_limpo.index.astype(str)

    # 2. Higienização da Tabela de Compras (PEDIDO DE COMPRA MEGA)
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
    
    # Remove duplicados na tabela de compras baseado unicamente na RM para não triplicar linhas
    df_pc_limpo = df_pc_limpo.drop_duplicates(subset=["rm_str"]).copy()

    # 🌟 A REGRA DE OURO REESTABELECIDA: O relacionamento une os blocos olhando puramente o número da RM!
    # Isso traz de volta os pedidos da Adrielle, Karolina e PCP instantaneamente!
    df_final = pd.merge(df_rm_limpo, df_pc_limpo, on=["rm_str"], how="left")

    if "mat_str_x" in df_final.columns:
        df_final["mat_str"] = df_final["mat_str_x"]

    # 3. Injeção isolada em segundo plano do APPROVAL PC (TOTALMENTE PRESERVADO)
    if not df_vinculo.empty and "pedido_str" in df_final.columns:
        df_app_pc_limpo = pd.DataFrame()
        df_app_pc_limpo["pedido_str"] = df_vinculo["pedido_str"].astype(str)
        df_app_pc_limpo["status_pc_real"] = df_vinculo.get("status_documento", "---")
        df_app_pc_limpo["data_pc_real"] = df_vinculo.get("data_ocorrencia", "---")
        df_app_pc_limpo["aprovador_pc_real"] = df_vinculo.get("nome_aprovador", "---")
        df_app_pc_limpo = df_app_pc_limpo.drop_duplicates(subset=["pedido_str"]).copy()

        df_final = pd.merge(df_final, df_app_pc_limpo, on=["pedido_str"], how="left")
        
        if "status_pc_real" in df_final.columns:
            df_final["status_pc"] = df_final["status_pc_real"].fillna("---")
            df_final["data_ocorrencia_pc"] = df_final["data_pc_real"].fillna("---")
            df_final["nome_aprovador_pc"] = df_final["aprovador_pc_real"].fillna("---")

    todas_colunas_vitais = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str", "pedido_str", "comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc", "linha_id"]
    for col in todas_colunas_vitais:
        if col not in df_final.columns: df_final[col] = "---"

    df_final["pedido_str"] = df_final["pedido_str"].fillna("---").astype(str).str.strip()
    df_final["comprador"] = df_final["comprador"].fillna("---").astype(str).str.strip().replace("nan", "---")
    df_final["quantidade_comprada"] = df_final["quantidade_comprada"].replace("---", "None")

    # Filtros contains dinâmicos da interface
    if buscar_rm:
        df_final = df_final[df_final["rm"].astype(str).str.contains(str(buscar_rm).strip(), na=False, regex=False)]
    if filtro_req != "Todos":
        df_final = df_final[df_final["nome_solicitante"].astype(str).str.contains(str(filtro_req).strip(), na=False, regex=False)]
        
    if filtro_comp != "Todos" and str(filtro_comp).strip() != "":
        c_alvo = str(filtro_comp).strip().lower()
        cond_comprador = df_final["comprador"].astype(str).str.lower().str.contains(c_alvo, na=False)
        cond_aprovador = df_final["nome_aprovador_pc"].astype(str).str.lower().str.contains(c_alvo, na=False)
        df_final = df_final[cond_comprador | cond_aprovador]

    df_final = df_final.drop_duplicates(subset=["linha_id"]).copy()

    # Extração segura das posições do calendário
    possui_intervalo_valido = isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2
    data_inicio_filtro = filtro_periodo[0] if possui_intervalo_valido else None
    data_fim_filtro = filtro_periodo[1] if possui_intervalo_valido else None
    ignorar_calendario = (buscar_rm != "") or (buscar_pc != "")

    lista_alertas_data, lista_entrega_dt_bruta, lista_necessidade_dt_bruta, indices_para_manter = [], [], [], []

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
