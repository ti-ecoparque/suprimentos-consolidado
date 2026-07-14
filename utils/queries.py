import pandas as pd

def executar_consultas_supabase(supabase, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_rm, filtro_status_pc):
    df_rm_bruto = pd.DataFrame()
    df_pc_bruto = pd.DataFrame()
    df_vinculo = pd.DataFrame()

    # Rota A: Busca isolada por número de RM - TOTALMENTE PRESERVADO
    if buscar_rm and str(buscar_rm).strip() != "":
        rm_alvo = str(buscar_rm).strip()
        rm_parametro = int(rm_alvo) if rm_alvo.isdigit() else rm_alvo
        
        res_rm = supabase.table("vw_approvo_rm").select("*").eq("rm", rm_parametro).limit(500).execute()
        df_rm_bruto = pd.DataFrame(res_rm.data)
        
        res_pc = supabase.table("pedido_compra").select("*").eq("rm", str(rm_alvo)).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)

    # Rota B: Busca isolada por número do PC - TOTALMENTE PRESERVADO
    elif buscar_pc and str(buscar_pc).strip() != "":
        pc_alvo = str(buscar_pc).strip()
        
        res_pc = supabase.table("pedido_compra").select("*").eq("pedido", int(pc_alvo) if pc_alvo.isdigit() else 0).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)
        
        lista_rms_pontes = [str(x).replace('.0', '').strip() for x in df_pc_bruto["rm"].unique() if pd.notna(x)] if "rm" in df_pc_bruto.columns else []
        if lista_rms_pontes:
            res_rm = supabase.table("vw_approvo_rm").select("*").in_("rm", lista_rms_pontes).execute()
            df_rm_bruto = pd.DataFrame(res_rm.data)

    # Rota C: Fluxo de Filtros Combinados Globais (Onde o filtro do comprador Thais é corrigido!)
    else:
        # 1. Puxa as RMs filtradas (Blocos REQUISICAO e APPROVAL RM totalmente preservados!)
        query_rm = supabase.table("vw_approvo_rm").select("*")
        if filtro_req != "Todos" and str(filtro_req).strip() != "":
            query_rm = query_rm.ilike("nome_solicitante", f"%{str(filtro_req).strip()}%")
        if filtro_status_rm != "Todos":
            query_rm = query_rm.eq("status_documento", {"Aprovado":"A","Em Aprovação":"E","Reprovado":"R"}[filtro_status_rm])
        res_rm = query_rm.limit(1000).execute()
        df_rm_bruto = pd.DataFrame(res_rm.data)

        # 2. 🌟 BUSCA COMERCIAL DUPLA INTELIGENTE:
        # Puxa os dados da tabela pedido_compra olhando as RMs da tela OU o comprador digitado diretamente!
        query_pc = supabase.table("pedido_compra").select("*")
        
        lista_rms_finais = []
        if not df_rm_bruto.empty and "rm" in df_rm_bruto.columns:
            lista_rms_finais = [str(x).replace('.0', '').strip() for x in df_rm_bruto["rm"].unique() if pd.notna(x) and str(x).strip() != ""]

        # Se o usuário digitou um comprador específico (Ex: Thais)
        if filtro_comp != "Todos" and str(filtro_comp).strip() != "":
            comp_alvo = str(filtro_comp).strip()
            # Varre os registros do comprador na tabela pedido_compra
            query_pc = query_pc.ilike("comprador", f"%{comp_alvo}%")
        # Caso contrário, se houver RMs na tela, filtra o lote delas nativamente para cache
        elif lista_rms_finais:
            query_pc = query_pc.in_("rm", lista_rms_finais)
            
        res_pc = query_pc.limit(1000).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)

        # 🌟 COMPLEMENTO DE BACKUP OPERACIONAL PARA BUSCA DE REQUISITANTE CONTIDO:
        # Se você buscou o comprador Thais mas as RMs dele vieram vazias por serem NULL no comprador do banco,
        # faz uma segunda varredura reversa para resgatar os pares de RMs legítimos e não dar tela em branco!
        if df_pc_bruto.empty and filtro_comp != "Todos" and lista_rms_finais:
            res_pc_backup = supabase.table("pedido_compra").select("*").in_("rm", lista_rms_finais).limit(1000).execute()
            df_pc_bruto = pd.DataFrame(res_pc_backup.data)

    # Camada isolada de cache para o Approval PC por número de pedido - TOTALMENTE PRESERVADO
    lista_peds_cache = []
    if not df_pc_bruto.empty and "pedido" in df_pc_bruto.columns:
        lista_peds_cache = [str(x).replace('.0', '').strip() for x in df_pc_bruto["pedido"].unique() if pd.notna(x) and str(x).strip() != ""]
        
    if lista_peds_cache:
        res_vinculo = supabase.table("vw_approvo_pc").select("*").in_("pedido", lista_peds_cache).execute()
        df_vinculo = pd.DataFrame(res_vinculo.data)

    # Inicialização uniforme das strings de acoplamento do Pandas
    if not df_rm_bruto.empty and "rm" in df_rm_bruto.columns:
        df_rm_bruto["rm_str"] = df_rm_bruto["rm"].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_rm_bruto["mat_str"] = df_rm_bruto["mat"].astype(str).str.replace('.0', '', regex=False).str.strip()
        
    if not df_pc_bruto.empty and "pedido" in df_pc_bruto.columns:
        df_pc_bruto["pedido_str"] = df_pc_bruto["pedido"].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_pc_bruto["mat_str"] = df_pc_bruto["mat"].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_pc_bruto["rm_str"] = df_pc_bruto["rm"].astype(str).str.replace('.0', '', regex=False).str.strip()

    if not df_vinculo.empty and "pedido" in df_vinculo.columns:
        df_vinculo["pedido_str"] = df_vinculo["pedido"].astype(str).str.replace('.0', '', regex=False).str.strip()

    return df_rm_bruto, df_pc_bruto, df_vinculo
