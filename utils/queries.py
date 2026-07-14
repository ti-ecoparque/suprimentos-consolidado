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
        
        # Busca direta na tabela física com os dados comerciais integrados
        res_pc = supabase.table("pedido_compra").select("*").eq("rm", int(rm_alvo) if rm_alvo.isdigit() else 0).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)

    # Rota B: Busca isolada por número do PC
    elif buscar_pc and str(buscar_pc).strip() != "":
        pc_alvo = str(buscar_pc).strip()
        
        res_pc = supabase.table("pedido_compra").select("*").eq("pedido", int(pc_alvo) if pc_alvo.isdigit() else 0).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)
        
        lista_rms_pontes = [int(float(x)) for x in df_pc_bruto["rm"].unique() if pd.notna(x)] if "rm" in df_pc_bruto.columns else []
        if lista_rms_pontes:
            res_rm = supabase.table("vw_approvo_rm").select("*").in_("rm", lista_rms_pontes).execute()
            df_rm_bruto = pd.DataFrame(res_rm.data)

    # Rota C: Fluxo de Filtros Combinados Globais
    else:
        query_rm = supabase.table("vw_approvo_rm").select("*")
        if filtro_req != "Todos" and str(filtro_req).strip() != "":
            query_rm = query_rm.ilike("nome_solicitante", f"%{str(filtro_req).strip()}%")
        if filtro_status_rm != "Todos":
            query_rm = query_rm.eq("status_documento", {"Aprovado":"A","Em Aprovação":"E","Reprovado":"R"}[filtro_status_rm])
        res_rm = query_rm.limit(1000).execute()
        df_rm_bruto = pd.DataFrame(res_rm.data)

        # 🌟 BUSCA COMERCIAL DIRETA: Puxa o lote da tabela física pedido_compra aplicando o filtro de comprador
        query_pc = supabase.table("pedido_compra").select("*")
        if filtro_comp != "Todos" and str(filtro_comp).strip() != "":
            query_pc = query_pc.ilike("comprador", f"%{str(filtro_comp).strip()}%")
        res_pc = query_pc.limit(2000).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)

    # Inicialização uniforme das strings técnicas para o Pandas
    if not df_rm_bruto.empty and "rm" in df_rm_bruto.columns:
        df_rm_bruto["rm_str"] = df_rm_bruto["rm"].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_rm_bruto["mat_str"] = df_rm_bruto["mat"].astype(str).str.replace('.0', '', regex=False).str.strip()
        
    if not df_pc_bruto.empty and "pedido" in df_pc_bruto.columns:
        df_pc_bruto["pedido_str"] = df_pc_bruto["pedido"].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_pc_bruto["mat_str"] = df_pc_bruto["mat"].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_pc_bruto["rm_str"] = df_pc_bruto["rm"].astype(str).str.replace('.0', '', regex=False).str.strip()

    return df_rm_bruto, df_pc_bruto, df_vinculo
