import streamlit as st
import pandas as pd
import os
from supabase import create_client

# 1. TRAVA DE SEGURANÇA E AUTO-LOGIN (À PROVA DE F5)
if "logado" not in st.session_state or not st.session_state.logado:
    usuario_url = st.query_params.get("u")
    if usuario_url:
        st.session_state.logado = True
        st.session_state.usuario_atual = usuario_url
    else:
        st.warning("⚠️ Acesso restrito. Por favor, faça login na tela inicial antes de continuar.")
        if st.button("Ir para a Tela de Login"):
            st.switch_page("app.py")
        st.stop()


def renderizar_cenario_d(rm_para_conferencia="", pedidos=None, supabase=None, Skinner_status=None):
    st.subheader("✅ Approvo Status — Cenário D")
    st.write("Visão ponta a ponta independente: Filtre por qualquer campo para consolidar a árvore logística.")
    st.divider()

    # 2. INICIALIZAÇÃO DO BANCO
    if supabase is None:
        SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # ==========================================================
    # 🔍 3. COLETA DINÂMICA DE OPÇÕES DO BANCO (CARREGAMENTO DOS FILTROS)
    # ==========================================================
    with st.spinner("Carregando listas de filtros operacionais..."):
        try:
            res_reqs = supabase.table("vw_approvo_rm").select("nome_solicitante").execute()
            opcoes_requisitante = ["Todos"] + sorted(list(set([r["nome_solicitante"] for r in res_reqs.data if r.get("nome_solicitante")])))
            
            res_comps = supabase.table("vw_approvo_pc").select("comprador").execute()
            opcoes_comprador = ["Todos"] + sorted(list(set([c["comprador"] for c in res_comps.data if c.get("comprador")])))
        except Exception:
            opcoes_requisitante = ["Todos"]
            opcoes_comprador = ["Todos"]

    # ==========================================================
    # 🛠️ 4. INTERFACE GRÁFICA DOS FILTROS INDEPENDENTES
    # ==========================================================
    st.markdown("#### 🔍 Painel de Filtros Globais")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    col_f4, col_f5, col_f6 = st.columns(3)
    
    with col_f1:
        buscar_rm = st.text_input("Filtrar por Número da RM:", value=rm_para_conferencia).strip()
    with col_f2:
        filtro_req = st.selectbox("Filtrar por Requisitante:", opcoes_requisitante)
    with col_f3:
        filtro_comp = st.selectbox("Filtrar por Comprador:", opcoes_comprador)
        
    with col_f4:
        filtro_status_rm = st.selectbox("Status da RM:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"])
    with col_f5:
        filtro_status_pc = st.selectbox("Status do PC:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"])
    with col_f6:
        filtro_periodo = st.date_input("Intervalo (Data da Requisição):", value=[], format="DD/MM/YYYY")

    # ==========================================================
    # 🚀 5. CONSTRUÇÃO DA QUERY INTELIGENTE E INDEPENDENTE
    # ==========================================================
    tem_filtro_ativo = buscar_rm or filtro_req != "Todos" or filtro_comp != "Todos" or filtro_status_rm != "Todos" or filtro_status_pc != "Todos" or len(filtro_periodo) == 2
    
    if not tem_filtro_ativo:
        st.info("💡 Selecione qualquer filtro acima ou digite uma RM para carregar os dados consolidados.")
        st.stop()

    with st.spinner("Buscando e cruzando visões comerciais..."):
        try:
            # 📐 A. QUERY NA VIEW DE REQUISIÇÕES (RM)
            query_rm = supabase.table("vw_approvo_rm").select("*")
            
            if buscar_rm:
                query_rm = query_rm.eq("rm", str(buscar_rm))
            if filtro_req != "Todos":
                query_rm = query_rm.eq("nome_solicitante", filtro_req)
            if filtro_status_rm != "Todos":
                mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
                query_rm = query_rm.eq("status_documento", mapa_invertido[filtro_status_rm])
                
            res_rm = query_rm.limit(500).execute()
            df_rm_bruto = pd.DataFrame(res_rm.data)

            if df_rm_bruto.empty:
                st.warning("⚠️ Nenhum registro de RM localizado para os filtros aplicados.")
                st.stop()

            # Extrai a lista de RMs localizadas para buscar os pedidos correspondentes
            lista_rms_encontradas = list(set([int(r) for r in df_rm_bruto["rm"].unique() if r is not None]))

            # 📐 B. QUERY NA TABELA DE VÍNCULO PEDIDO_COMPRA
            res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").in_("rm", lista_rms_encontradas).execute()
            df_vinculo = pd.DataFrame(res_vinculo.data)

            df_pc_bruto = pd.DataFrame()
            if not df_vinculo.empty:
                lista_pedidos = list(set([str(p.get("pedido")) for p in res_vinculo.data if p.get("pedido") is not None]))
                
                if lista_pedidos:
                    # 📐 C. QUERY NA VIEW DE PEDIDOS (PC)
                    query_pc = supabase.table("vw_approvo_pc").select("*").in_("pedido", lista_pedidos)
                    
                    if filtro_comp != "Todos":
                        query_pc = query_pc.eq("comprador", filtro_comp)
                    if filtro_status_pc != "Todos":
                        mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
                        query_pc = query_pc.eq("status_documento", mapa_invertido[filtro_status_pc])
                        
                    res_pc = query_pc.execute()
                    df_pc_bruto = pd.DataFrame(res_pc.data)
                    
                    # Remove a coluna de lista na raiz para matar o erro de 'unhashable type'
                    if "entregas_agendadas" in df_pc_bruto.columns:
                        df_pc_bruto.drop(columns=["entregas_agendadas"], inplace=True)

            # ==========================================================
            # 🔄 6. LOGÍSTICA DE UNIFICAÇÃO (MERGE) E ANTIDUPLICIDADE
            # ==========================================================
            df_rm_bruto["rm_str"] = df_rm_bruto["rm"].astype(str).str.strip()
            df_rm_bruto["mat_str"] = df_rm_bruto["mat"].astype(str).str.strip()
            
            colunas_vitais_rm = ["nome_solicitante", "rm", "mat", "desc_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str"]
            colunas_existentes_rm = [c for c in colunas_vitais_rm if c in df_rm_bruto.columns]
            df_rm_limpo = df_rm_bruto[colunas_existentes_rm].drop_duplicates().copy()
            
            if not df_vinculo.empty:
                df_vinculo["rm_str"] = df_vinculo["rm"].astype(str).str.strip()
                df_vinculo["pedido_str"] = df_vinculo["pedido"].astype(str).str.strip()
                
                df_consolidado = pd.merge(df_rm_limpo, df_vinculo[["rm_str", "pedido_str"]], on="rm_str", how="left")
                
                if not df_pc_bruto.empty:
                    df_pc_bruto["pedido_str"] = df_pc_bruto["pedido"].astype(str).str.strip()
                    df_pc_bruto["mat_str"] = df_pc_bruto["mat"].astype(str).str.strip()
                    
                    colunas_vitais_pc = ["pedido_str", "mat_str", "comprador", "entrega", "quantidade", "status_documento", "data_ocorrencia", "nome_aprovador"]
                    colunas_existentes_pc = [c for c in colunas_vitais_pc if c in df_pc_bruto.columns]
                    df_pc_limpo = df_pc_bruto[colunas_existentes_pc].drop_duplicates().copy()
                    
                    df_pc_limpo.rename(columns={
                        "status_documento": "status_pc",
                        "data_oficial_ocorrencia": "data_ocorrencia_pc",
                        "data_ocorrencia": "data_ocorrencia_pc",
                        "nome_aprovador": "nome_aprovador_pc",
                        "quantidade": "quantidade_comprada"
                    }, inplace=True, errors="ignore")
                    
                    # 💡 CORREÇÃO AQUI: Mudado de df_consolidated para df_consolidado (corrigindo a digitação)
                    if "mat" in df_consolidado.columns and "mat" in df_pc_limpo.columns:
                        df_final = pd.merge(df_consolidado, df_pc_limpo, on=["pedido_str", "mat_str"], how="left")
                    else:
                        df_final = pd.merge(df_consolidado, df_pc_limpo, on="pedido_str", how="left")
                else:
                    df_final = df_consolidado.copy()
                    for col in ["comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]:
                        df_final[col] = None
            else:
                df_final = df_rm_limpo.copy()
                df_final["pedido_str"] = None
                for col in ["comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]:
                    df_final[col] = None

            # Trava antiduplicidade final baseada em texto e número
            if "mat" in df_final.columns:
                df_final = df_final.drop_duplicates(subset=["rm", "mat"]).copy()
            else:
                df_final = df_final.drop_duplicates().copy()

            # Filtro secundário opcional de Intervalo de Datas via Pandas
            if len(filtro_periodo) == 2:
                data_inicio, data_fim = pd.to_datetime(filtro_periodo), pd.to_datetime(filtro_periodo)
                df_final["data_emissao_dt"] = pd.to_datetime(df_final["data_emissao"], errors="coerce")
                df_final = df_final[(df_final["data_emissao_dt"] >= data_inicio) & (df_final["data_emissao_dt"] <= data_fim)]
                if df_final.empty:
                    st.warning("⚠️ Nenhum registro corresponde ao intervalo de datas selecionado.")
                    st.stop()
            
                        # ==========================================================
            # 📊 7. MAPEAMENTO, TRADUÇÃO E FORMATAÇÃO VISUAL
            # ==========================================================
            # Dicionário de tradução das siglas de Status da RM e do PC
            mapa_status_extenso = {"A": "Aprovado", "E": "Em Aprovação", "R": "Reprovado", "---": "---"}
            
            if "status_documento" in df_final.columns:
                df_final["status_documento"] = df_final["status_documento"].astype(str).str.strip().map(lambda x: mapa_status_extenso.get(x.upper(), x))
            if "status_pc" in df_final.columns:
                df_final["status_pc"] = df_final["status_pc"].astype(str).str.strip().map(lambda x: mapa_status_extenso.get(x.upper(), x))

            # Limpa as casas decimais das colunas de quantidade do Mega (.000000 -> inteiro)
            if "qtd_solicitada" in df_final.columns:
                df_final["qtd_solicitada"] = pd.to_numeric(df_final["qtd_solicitada"], errors="coerce").fillna(0).astype(int)
            if "quantidade_comprada" in df_final.columns:
                df_final["quantidade_comprada"] = pd.to_numeric(df_final["quantidade_comprada"], errors="coerce").fillna(0).astype(int)

            # Formatação de datas comuns para o padrão brasileiro (DD/MM/AAAA)
            for col in ["data_emissao", "data_necessidade", "entrega"]:
                if col in df_final.columns:
                    df_final[col] = pd.to_datetime(df_final[col], errors="coerce").dt.strftime("%d/%m/%Y")
                    
            # Formatação de datas com hora para as ocorrências do Approvo
            for col in ["data_ocorrencia", "data_ocorrencia_pc"]:
                if col in df_final.columns:
                    df_final[col] = pd.to_datetime(df_final[col], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")

            df_final.fillna("---", inplace=True)
            df_final.replace("nan", "---", inplace=True)

            # Estrutura do Dicionário de MultiIndex (Super Cabeçalho Agrupado)
            colunas_multi_index = {
                "nome_solicitante":   ("REQUISICAO DE MATERIAL MEGA", "Requisitante"),
                "rm":                 ("REQUISICAO DE MATERIAL MEGA", "Nr. RM"),
                "mat":                ("REQUISICAO DE MATERIAL MEGA", "Nr. Material"),
                "desc_item":          ("REQUISICAO DE MATERIAL MEGA", "Descrição"),
                "qtd_solicitada":     ("REQUISICAO DE MATERIAL MEGA", "Qt. Sol."),
                "data_emissao":       ("REQUISICAO DE MATERIAL MEGA", "Data da Requisição"),
                "data_necessidade":   ("REQUISICAO DE MATERIAL MEGA", "Data da Nec."),
                
                "status_documento":   ("APPROVAL (RM)", "Status da Aprovação"),
                "data_ocorrencia":    ("APPROVAL (RM)", "Data da Aprovação"),
                "nome_aprovador":     ("APPROVAL (RM)", "Aprovador"),
                
                "comprador":          ("PEDIDO DE COMPRA MEGA", "Comprador"),
                "pedido_str":         ("PEDIDO DE COMPRA MEGA", "Nr. PC"),
                "entrega":            ("PEDIDO DE COMPRA MEGA", "Data de Entrega"),
                "quantidade_comprada":("PEDIDO DE COMPRA MEGA", "Qt. Compr."),
                
                "status_pc":          ("APPROVAL (PC)", "Status da Aprovação"),
                "data_ocorrencia_pc": ("APPROVAL (PC)", "Data da Aprovação"),
                "nome_aprovador_pc":  ("APPROVAL (PC)", "Aprovador")
            }

            colunas_existentes = [col for col in colunas_multi_index.keys() if col in df_final.columns]
            df_exibicao = df_final[colunas_existentes].copy()
            df_exibicao.columns = pd.MultiIndex.from_tuples([colunas_multi_index[c] for c in colunas_existentes])

            # ==========================================================
            # 🎨 8. LAYOUT CROMÁTICO (IDENTIDADE PASTEL)
            # ==========================================================
            def aplicar_cores_corpo(df):
                """Pinta as células com tons pastéis baseados no super cabeçalho pai"""
                estilos = pd.DataFrame('', index=df.index, columns=df.columns)
                for col in df.columns:
                    grupo = col
                    if grupo == "REQUISICAO DE MATERIAL MEGA":
                        estilos[col] = 'background-color: #f2f7f2; color: #000000;'
                    elif grupo == "APPROVAL (RM)":
                        estilos[col] = 'background-color: #e2f0d9; color: #000000;'
                    elif grupo == "PEDIDO DE COMPRA MEGA":
                        estilos[col] = 'background-color: #fbf2fa; color: #000000;'
                    elif grupo == "APPROVAL (PC)":
                        estilos[col] = 'background-color: #f3daf1; color: #000000;'
                return estilos

            # Injeta o código CSS para colorir os títulos superiores do Streamlit
            st.markdown("""
                <style>
                    th.col_heading.level0 { font-weight: bold !important; color: #000000 !important; text-align: center !important; }
                    th.col_heading.level0.id0_6 { background-color: #e2f0d9 !important; }
                    th.col_heading.level0.id7_9 { background-color: #a9d08e !important; }
                    th.col_heading.level0.id10_13 { background-color: #f2dcfa !important; }
                    th.col_heading.level0.id14_16 { background-color: #df9ff2 !important; }
                </style>
            """, unsafe_allow_html=True)

            # Renderiza a tabela finalizada na interface do Streamlit
            df_estilizado = df_exibicao.style.apply(aplicar_cores_corpo, axis=None)
            st.dataframe(df_estilizado, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"❌ Erro crítico ao consolidar as visões no Cenário D: {e}")
        