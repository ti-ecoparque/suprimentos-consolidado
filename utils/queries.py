import pandas as pd

def executar_consultas_supabase(supabase, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_rm, filtro_status_pc):
    df_rm_bruto = pd.DataFrame()
    df_pc_bruto = pd.DataFrame()
    df_vinculo = pd.DataFrame()

    # Rota A: Busca isolada por número de RM
    if buscar_rm and str(buscar_rm).strip() != "":
        rm_alvo = str(buscar_rm).strip()
        rm_parametro = int(rm_alvo) if rm_alvo.isdigit() else rm_alvo
        
        res_rm = supabase.table("vw_approvo_rm").select("*").eq("rm", rm_parametro).limit(500).execute()
        df_rm_bruto = pd.DataFrame(res_rm.data)
        
        res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").eq("rm", int(rm_alvo) if rm_alvo.isdigit() else 0).execute()
        df_vinculo = pd.DataFrame(res_vinculo.data)
        
        if not df_vinculo.empty and "pedido" in df_vinculo.columns:
            lista_peds_pontes = [str(int(float(x))) for x in df_vinculo["pedido"].unique() if pd.notna(x)]
            if lista_peds_pontes:
                res_pc = supabase.table("vw_approvo_pc").select("*").in_("pedido", lista_peds_pontes).limit(500).execute()
                df_pc_bruto = pd.DataFrame(res_pc.data)

    # Rota B: Busca isolada por número de PC
    elif buscar_pc and str(buscar_pc).strip() != "":
        pc_alvo = str(buscar_pc).strip()
        query_pc = supabase.table("vw_approvo_pc").select("*").eq("pedido", pc_alvo)
        res_pc = query_pc.limit(500).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)
        
        res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").eq("pedido", int(pc_alvo) if pc_alvo.isdigit() else 0).execute()
        df_vinculo = pd.DataFrame(res_vinculo.data)
        
        lista_rms_pontes = [int(float(x)) for x in df_vinculo["rm"].unique() if pd.notna(x)] if "rm" in df_vinculo.columns else []
        if lista_rms_pontes:
            res_rm = supabase.table("vw_approvo_rm").select("*").in_("rm", lista_rms_pontes).execute()
            df_rm_bruto = pd.DataFrame(res_rm.data)

    # Rota C: Rota de filtros por nome/status (Sincronizada com o fluxo de hoje de manhã!)
    else:
        query_rm = supabase.table("vw_approvo_rm").select("*")
        if filtro_req != "Todos": 
            query_rm = query_rm.eq("nome_solicitante", filtro_req)
        if filtro_status_rm != "Todos":
            query_rm = query_rm.eq("status_documento", {"Aprovado":"A","Em Aprovação":"E","Reprovado":"R"}[filtro_status_rm])
        res_rm = query_rm.limit(500).execute()
        df_rm_bruto = pd.DataFrame(res_rm.data)

        # Resgata os vínculos intermediários de chaves
        query_vinculo = supabase.table("pedido_compra").select("rm", "pedido").limit(2000)
        res_vinculo = query_vinculo.execute()
        df_vinculo = pd.DataFrame(res_vinculo.data)

        # 🔥 A MÁGICA DE HOJE DE MANHÃ: Se buscou por Requisitante, traz um lote completo e global
        # de compras do banco para o Pandas cruzar via RAM, restaurando Thais e Junior na hora!
        query_pc = supabase.table("vw_approvo_pc").select("*")
        if filtro_comp != "Todos": 
            query_pc = query_pc.eq("nome_aprovador", filtro_comp)
        if filtro_status_pc != "Todos": 
            query_pc = query_pc.eq("status_documento", {"Aprovado":"A","Em Aprovação":"E","Reprovado":"R"}[filtro_status_pc])
            
        res_pc = query_pc.limit(1500).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)

    # Injeção das chaves técnicas de strings que o processamento utiliza para o Outer Join
    if not df_rm_bruto.empty and "rm" in df_rm_bruto.columns:
        df_rm_bruto["rm_str"] = df_rm_bruto["rm"].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_rm_bruto["mat_str"] = df_rm_bruto["mat"].astype(str).str.replace('.0', '', regex=False).str.strip()
        
    if not df_pc_bruto.empty and "pedido" in df_pc_bruto.columns:
        df_pc_bruto["pedido_str"] = df_pc_bruto["pedido"].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_pc_bruto["mat_str"] = df_pc_bruto["mat"].astype(str).str.replace('.0', '', regex=False).str.strip()

    if not df_vinculo.empty and "pedido" in df_vinculo.columns:
        df_vinculo["pedido_str"] = df_vinculo["pedido"].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_vinculo["rm_str"] = df_vinculo["rm"].astype(str).str.replace('.0', '', regex=False).str.strip()

    return df_rm_bruto, df_pc_bruto, df_vinculo
