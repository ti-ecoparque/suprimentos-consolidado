import pandas as pd

def executar_consultas_supabase(supabase, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_rm, filtro_status_pc):
    df_rm_bruto = pd.DataFrame()
    df_pc_bruto = pd.DataFrame()
    df_vinculo = pd.DataFrame()

    # A. Rota Isolada por Número da RM
    if buscar_rm and str(buscar_rm).strip() != "":
        rm_alvo = str(buscar_rm).strip()
        rm_parametro = int(rm_alvo) if rm_alvo.isdigit() else rm_alvo
        
        # 1. Busca direta na visão de RMs do Supabase
        res_rm = supabase.table("vw_approvo_rm").select("*").eq("rm", rm_parametro).limit(500).execute()
        df_rm_bruto = pd.DataFrame(res_rm.data)
        
        # 🚨 PONTE INTELIGENTE: Tenta buscar o número exato na coluna RM
        res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").eq("rm", int(rm_alvo) if rm_alvo.isdigit() else 0).execute()
        df_vinculo = pd.DataFrame(res_vinculo.data)
        
        # 🌟 MULTI-MATCH: Se não achou na coluna RM, busca o texto contido na coluna observacao (Mata o problema do print!)
        if df_vinculo.empty:
            res_vinculo_obs = supabase.table("pedido_compra").select("rm", "pedido").ilike("observacao", f"%{rm_alvo}%").execute()
            df_vinculo = pd.DataFrame(res_vinculo_obs.data)
        
        if not df_vinculo.empty and "pedido" in df_vinculo.columns:
            lista_peds_pontes = [str(int(float(x))) for x in df_vinculo["pedido"].unique() if pd.notna(x)]
            if lista_peds_pontes:
                res_pc = supabase.table("vw_approvo_pc").select("*").in_("pedido", lista_peds_pontes).limit(500).execute()
                df_pc_bruto = pd.DataFrame(res_pc.data)
                
    # B. Rota Isolada por Número do PC
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

    # C. Fluxo de Filtros de Combinação Padrão
    else:
        query_rm = supabase.table("vw_approvo_rm").select("*")
        if filtro_req != "Todos": query_rm = query_rm.eq("nome_solicitante", filtro_req)
        if filtro_status_rm != "Todos":
            query_rm = query_rm.eq("status_documento", {"Aprovado":"A","Em Aprovação":"E","Reprovado":"R"}[filtro_status_rm])
        res_rm = query_rm.limit(500).execute()
        df_rm_bruto = pd.DataFrame(res_rm.data)

        lista_rms_encontradas = [int(float(x)) for x in df_rm_bruto["rm"].unique() if pd.notna(x)] if "rm" in df_rm_bruto.columns else []
        query_vinculo = supabase.table("pedido_compra").select("rm", "pedido")
        if lista_rms_encontradas: query_vinculo = query_vinculo.in_("rm", lista_rms_encontradas)
        res_vinculo = query_vinculo.execute()
        df_vinculo = pd.DataFrame(res_vinculo.data)

        lista_peds_vinculados = [str(int(float(x))) for x in df_vinculo["pedido"].unique() if pd.notna(x)] if "pedido" in df_vinculo.columns else []
        deve_buscar_pc = filtro_comp != "Todos" or filtro_status_pc != "Todos" or len(lista_peds_vinculados) > 0

        if deve_buscar_pc:
            query_pc = supabase.table("vw_approvo_pc").select("*")
            if filtro_comp != "Todos": query_pc = query_pc.eq("nome_solicitante", filtro_comp)
            if filtro_status_pc != "Todos": query_pc = query_pc.eq("status_documento", {"Aprovado":"A","Em Aprovação":"E","Reprovado":"R"}[filtro_status_pc])
            elif lista_peds_vinculados: query_pc = query_pc.in_("pedido", lista_peds_vinculados)
            res_pc = query_pc.limit(500).execute()
            df_pc_bruto = pd.DataFrame(res_pc.data)

    if not df_pc_bruto.empty and "entregas_agendadas" in df_pc_bruto.columns:
        df_pc_bruto.drop(columns=["entregas_agendadas"], inplace=True)

    return df_rm_bruto, df_pc_bruto, df_vinculo
