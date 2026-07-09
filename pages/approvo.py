import streamlit as st
import pandas as pd
import os
from supabase import create_client

# ==========================================================
# 🔒 1. TRAVA DE SEGURANÇA E AUTO-LOGIN NATIVO (À PROVA DE F5)
# ==========================================================
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

# ==========================================================
# 📊 2. CONFIGURAÇÃO DA INTERFACE VISUAL
# ==========================================================
st.subheader("✅ Approvo Status")
st.write("Visão ponta a ponta independente: Filtre por qualquer campo para consultar a árvore logística.")
st.divider()

# ==========================================================
# 💾 3. INICIALIZAÇÃO SEGURA DO BANCO DE DADOS
# ==========================================================
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Credenciais do Supabase não configuradas no ambiente local.")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================================
# 🔍 3.5 COLETA DINÂMICA DE OPÇÕES DO BANCO (CARREGAMENTO DOS FILTROS)
# ==========================================================
try:
    res_nomes_req = supabase.table("vw_approvo_rm").select("nome_solicitante").execute()
    nomes_unicos_req = set()
    for linha in res_nomes_req.data:
        nome = linha.get("nome_solicitante")
        if nome and pd.notna(nome) and str(nome).strip() != "" and str(nome).lower() != "nan":
            nomes_unicos_req.add(str(nome).strip())
    opcoes_requisitas = ["Todos"] + sorted(list(nomes_unicos_req))
except Exception:
    opcoes_requisitas = ["Todos"]

try:
    res_nomes_comp = supabase.table("vw_approvo_pc").select("nome_solicitante").execute()
    compradores_unicos = set()
    for linha in res_nomes_comp.data:
        comp = linha.get("nome_solicitante")
        if comp and pd.notna(comp) and str(comp).strip() != "" and str(comp).lower() != "nan":
            compradores_unicos.add(str(comp).strip())
    opcoes_compradores = ["Todos"] + sorted(list(compradores_unicos))
except Exception:
    opcoes_compradores = ["Todos"]

# ==========================================================
# 🛠️ 4. INTERFACE GRÁFICA DOS FILTROS GLOBAIS INDEPENDENTES
# ==========================================================
st.markdown("#### 🔍 Painel de Filtros Globais")

col_f1, col_f2, col_f3 = st.columns(3)
col_f4, col_f5, col_f6 = st.columns(3)

with col_f1:
    buscar_rm = st.text_input("Filtrar por Número da RM:", "").strip()
with col_f2:
    filtro_req = st.selectbox("Filtrar por Nome do Requisitante:", opcoes_requisitas)
with col_f3:
    filtro_comp = st.selectbox("Filtrar por Nome do Comprador:", opcoes_compradores)
    
with col_f4:
    filtro_status_rm = st.selectbox("Status da RM:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"])
with col_f5:
    filtro_status_pc = st.selectbox("Status do PC:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"])
with col_f6:
    filtro_periodo = st.date_input("Intervalo (Data da Requisição):", value=[], format="DD/MM/YYYY")

# ==========================================================
# 🚀 5. TRAVA DE VALIDAÇÃO DE FILTROS SELECIONADOS
# ==========================================================
tem_filtro_ativo = buscar_rm or filtro_req != "Todos" or filtro_comp != "Todos" or filtro_status_rm != "Todos" or filtro_status_pc != "Todos" or len(filtro_periodo) == 2

if not tem_filtro_ativo:
    st.info("💡 Selecione qualquer filtro acima ou digite uma RM para carregar os dados consolidados.")
    st.stop()

# ==========================================================
# 🚀 6. CONSTRUÇÃO DA QUERY INTELIGENTE INDEPENDENTE (FULL COMPARTILHADO)
# ==========================================================
with st.spinner("Buscando e cruzando visões comerciais..."):
    try:
        # A. Consulta na visão de Requisições de Material (RM)
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

        # B. Consulta na tabela de vínculo físico pedido_compra
        lista_rms_encontradas = []
        if not df_rm_bruto.empty and "rm" in df_rm_bruto.columns:
            lista_rms_encontradas = [int(float(x)) for x in df_rm_bruto["rm"].unique() if pd.notna(x)]

        query_vinculo = supabase.table("pedido_compra").select("rm", "pedido")
        if buscar_rm:
            query_vinculo = query_vinculo.eq("rm", int(buscar_rm) if str(buscar_rm).isdigit() else 0)
        elif lista_rms_encontradas:
            query_vinculo = query_vinculo.in_("rm", lista_rms_encontradas)
            
        res_vinculo = query_vinculo.execute()
        df_vinculo = pd.DataFrame(res_vinculo.data)

        lista_peds_vinculados = []
        if not df_vinculo.empty and "pedido" in df_vinculo.columns:
            lista_peds_vinculados = [str(int(float(x))) for x in df_vinculo["pedido"].unique() if pd.notna(x)]

        # C. Consulta na visão de Pedidos de Compra (PC)
        query_pc = supabase.table("vw_approvo_pc").select("*")
        if filtro_comp != "Todos" or filtro_status_pc != "Todos":
            if filtro_comp != "Todos":
                query_pc = query_pc.eq("nome_solicitante", filtro_comp)
            if filtro_status_pc != "Todos":
                mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
                query_pc = query_pc.eq("status_documento", mapa_invertido[filtro_status_pc])
        elif lista_peds_vinculados:
            query_pc = query_pc.in_("pedido", lista_peds_vinculados)
        else:
            query_pc = query_pc.none()
            
        res_pc = query_pc.limit(500).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)

        if not df_pc_bruto.empty and "entregas_agendadas" in df_pc_bruto.columns:
            df_pc_bruto.drop(columns=["entregas_agendadas"], inplace=True)

        # Se o usuário digitou uma RM e ela não existe no Approvo, garante a estrutura
        if df_rm_bruto.empty and buscar_rm:
            df_rm_bruto = pd.DataFrame([{"rm": int(buscar_rm)}])

        if df_pc_bruto.empty and df_rm_bruto.empty:
            # Em vez de st.stop(), criamos uma variável de aviso para parar o código fora do spinner
            tabela_vazia_banco = True
        else:
            tabela_vazia_banco = False
                # ==========================================================
        # 🔄 7. LOGÍSTICA DE UNIFICAÇÃO (BLINDAGEM ESTRUTURAL DE COLUNAS)
        # ==========================================================
        # Lista padrão utilizada para inicializar estruturas vazias sem quebrar eixos
        todas_colunas_vitais = [
            "nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", 
            "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", 
            "nome_aprovador", "rm_str", "mat_str", "pedido_str", "comprador", "entrega", 
            "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"
        ]

        # 1. Tratamento e Isolamento da tabela de RMs
        if not df_rm_bruto.empty:
            for c in df_rm_bruto.columns:
                df_rm_bruto[c] = df_rm_bruto[c].astype(str).str.replace('.0', '', regex=False).str.strip()
            df_rm_bruto["rm_str"] = df_rm_bruto.get("rm", "---")
            df_rm_bruto["mat_str"] = df_rm_bruto.get("mat", "---")
            df_rm_limpo = df_rm_bruto.drop_duplicates().copy()
        else:
            df_rm_limpo = pd.DataFrame(columns=todas_colunas_vitais)

        if "rm_str" not in df_rm_limpo.columns: df_rm_limpo["rm_str"] = "---"
        if "mat_str" not in df_rm_limpo.columns: df_rm_limpo["mat_str"] = "---"

        # 2. Tratamento e Isolamento da tabela de Vínculos Intermediários
        if not df_vinculo.empty:
            for c in df_vinculo.columns:
                df_vinculo[c] = df_vinculo[c].astype(str).str.replace('.0', '', regex=False).str.strip()
            df_vinculo["rm_str"] = df_vinculo.get("rm", "---")
            df_vinculo["pedido_str"] = df_vinculo.get("pedido", "---")
            df_rm_consolidada = pd.merge(df_rm_limpo, df_vinculo[["rm_str", "pedido_str"]], on="rm_str", how="outer")
        else:
            df_rm_consolidada = df_rm_limpo.copy()
            df_rm_consolidada["pedido_str"] = "---"

        if "pedido_str" not in df_rm_consolidada.columns: df_rm_consolidada["pedido_str"] = "---"
        if "mat_str" not in df_rm_consolidada.columns: df_rm_consolidada["mat_str"] = "---"

        # 3. Tratamento e Isolamento da tabela de Pedidos (PC)
        if not df_pc_bruto.empty:
            for c in df_pc_bruto.columns:
                df_pc_bruto[c] = df_pc_bruto[c].astype(str).str.replace('.0', '', regex=False).str.strip()
            
            df_pc_bruto["pedido_str"] = df_pc_bruto.get("pedido", "---")
            df_pc_bruto["mat_str"] = df_pc_bruto.get("mat", "---")
            df_pc_limpo = df_pc_bruto.drop_duplicates().copy()
            
            # 🚨 CORREÇÃO DEFINITIVA DO RENAME: Traduz os campos um por um de forma segura
            # Sem mapear por posições fixas de eixos para eliminar o Length Mismatch
            mapa_colunas_pc = {
                "nome_solicitante": "comprador",
                "status_documento": "status_pc",
                "data_oficial_ocorrencia": "data_ocorrencia_pc",
                "data_ocorrencia": "data_ocorrencia_pc",
                "nome_aprovador": "nome_aprovador_pc",
                "quantidade": "quantidade_comprada"
            }
            #Filtra apenas as colunas que realmente existem na tabela antes de renomear
            mapa_existente = {k: v for k, v in mapa_colunas_pc.items() if k in df_pc_limpo.columns}
            df_pc_limpo.rename(columns=mapa_existente, inplace=True)
        else:
            df_pc_limpo = pd.DataFrame(columns=todas_colunas_vitais)

        if "pedido_str" not in df_pc_limpo.columns: df_pc_limpo["pedido_str"] = "---"
        if "mat_str" not in df_pc_limpo.columns: df_pc_limpo["mat_str"] = "---"

        # Força as chaves a virarem strings limpas antes da união
        df_rm_consolidada["pedido_str"] = df_rm_consolidada["pedido_str"].astype(str).str.strip()
        df_rm_consolidada["mat_str"] = df_rm_consolidada["mat_str"].astype(str).str.strip()
        df_pc_limpo["pedido_str"] = df_pc_limpo["pedido_str"].astype(str).str.strip()
        df_pc_limpo["mat_str"] = df_pc_limpo["mat_str"].astype(str).str.strip()

        # 🔥 OUTER JOIN COMPLETO INFALÍVEL SINCRO
        df_final = pd.merge(df_rm_consolidada, df_pc_limpo, on=["pedido_str", "mat_str"], how="outer")

        # Garante a existência de todas as colunas necessárias pós-merge para evitar quebras de dicionário
        for col in todas_colunas_vitais:
            if col not in df_final.columns:
                df_final[col] = "---"

        df_final["rm"] = df_final["rm"].fillna(df_final["rm_str"])
        df_final["mat"] = df_final["mat"].fillna(df_final["mat_str"])



                # ==========================================================
        # 🚨 7.5 PROCESSAMENTO SEGURO DE DATAS E CÁLCULO DE ATRASO
        # ==========================================================
        lista_alertas_data = []
        lista_entrega_dt_bruta = []
        lista_necessidade_dt_bruta = []
        lista_dt_emissao_puro = []
        indices_para_manter = []

        # Convertemos os filtros do calendário do Streamlit para objetos date nativos do Python
        data_inicio_filtro = None
        data_fim_filtro = None
        if isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2:
            if pd.notna(filtro_periodo[0]) and pd.notna(filtro_periodo[1]):
                data_inicio_filtro = filtro_periodo[0]
                data_fim_filtro = filtro_periodo[1]

        # Varre linha por linha usando objetos nativos independentes do Pandas
        for idx in df_final.index:
            val_entrega = df_final.loc[idx, "entrega"]
            val_necessidade = df_final.loc[idx, "data_necessidade"]
            val_emissao = df_final.loc[idx, "data_emissao"]
            
            dt_ent = None
            dt_nec = None
            dt_emi = None
            
            def converter_para_data_nativa(valor):
                if pd.isna(valor) or str(valor).strip() in ["", "---", "nan", "None", "NaT"]:
                    return None
                try:
                    if hasattr(valor, "date"):
                        return valor.date()
                    t_str = str(valor).strip().split(" ")[0]
                    if "-" in t_str:
                        return datetime.datetime.strptime(t_str, "%Y-%m-%d").date()
                    elif "/" in t_str:
                        return datetime.datetime.strptime(t_str, "%d/%m/%Y").date()
                except Exception:
                    pass
                return None

            dt_ent = converter_para_data_nativa(val_entrega)
            dt_nec = converter_para_data_nativa(val_necessidade)
            dt_emi = converter_para_data_nativa(val_emissao)

            # Aplica o filtro de Intervalo de Período de forma nativa e isolada
            if data_inicio_filtro and data_fim_filtro:
                if dt_emi is None or not (data_inicio_filtro <= dt_emi <= data_fim_filtro):
                    continue 

            indices_para_manter.append(idx)
            lista_entrega_dt_bruta.append(dt_ent)
            lista_necessidade_dt_bruta.append(dt_nec)
            lista_dt_emissao_puro.append(dt_emi)

            if dt_ent is None or dt_nec is None:
                lista_alertas_data.append("Data não informada")
            else:
                diferenca = (dt_ent - dt_nec).days
                if diferenca > 0:
                    lista_alertas_data.append(f"Atraso de {diferenca} dias")
                elif diferenca < 0:
                    lista_alertas_data.append(f"Adiantado {abs(diferenca)} dias")
                else:
                    lista_alertas_data.append("No prazo")

        # Filtra o DataFrame com base no fatiamento nativo
        df_final = df_final.loc[indices_para_manter].copy()
        df_final["alerta_data"] = lista_alertas_data
        
        # Converte as listas nativas em Series temporárias estáveis
        dt_emissao_puro = pd.Series(lista_dt_emissao_puro, index=df_final.index)
        dt_entrega_puro = pd.Series(lista_entrega_dt_bruta, index=df_final.index)
        dt_necessidade_puro = pd.Series(lista_necessidade_dt_bruta, index=df_final.index)

        # Guarda as séries em colunas de controle interno para o Layout Cromático (Etapa 9)
        df_final["entrega_original_dt"] = dt_entrega_puro
        df_final["necessidade_original_dt"] = dt_necessidade_puro

    except Exception as e:
        st.error(f"❌ Erro crítico ao consolidar as visões no Cenário D: {e}")
        st.stop()

# ==========================================================
# 🚨 VALIDAÇÃO ADICIONAL DE LINHAS (FORA DO RECUO DO SPINNER)
# ==========================================================
# Ao rodar aqui na margem zero, o indicador azul desliga antes de parar a tela!
if df_final.empty:
    st.warning("⚠️ Nenhum registro corresponde aos critérios selecionados no período filtrado.")
    st.stop()


        # ==========================================================
        # 📊 8. MAPEAMENTO, TRADUÇÃO E PROCESSAMENTO COMPLETO DE STRINGS Visuais
        # ==========================================================
        mapa_status_extenso = {"A": "Aprovado", "E": "Em Aprovação", "R": "Reprovado", "---": "---"}
        
        if "status_documento" in df_final.columns:
            df_final["status_documento"] = df_final["status_documento"].map(
                lambda x: mapa_status_extenso.get(str(x).strip().upper(), "---") if pd.notna(x) and str(x) not in ["nan", "None", "---"] else "---"
            )
        if "status_pc" in df_final.columns:
            df_final["status_pc"] = df_final["status_pc"].map(
                lambda x: mapa_status_extenso.get(str(x).strip().upper(), "---") if pd.notna(x) and str(x) not in ["nan", "None", "---"] else "---"
            )

        df_final["qtd_solicitada"] = pd.to_numeric(df_final["qtd_solicitada"], errors="coerce").fillna(0).astype(int)
        df_final["quantidade_comprada"] = pd.to_numeric(df_final["quantidade_comprada"], errors="coerce").fillna(0).astype(int)

        # Formatação visual das datas limpando a memória do Pandas para Strings normais (tipo 'object')
        def formatar_visual_seguro(valor, incluir_hora=False):
            if pd.isna(valor) or str(valor).strip() in ["", "---", "nan", "None", "NaT"]:
                return "Data não informada"
            try:
                if hasattr(valor, "strftime"):
                    return valor.strftime("%d/%m/%Y %H:%M" if incluir_hora else "%d/%m/%Y")
                t_str = str(valor).strip()
                if "T" in t_str: t_str = t_str.split("T")[0]
                elif " " in t_str: t_str = t_str.split(" ")[0]
                
                if "-" in t_str:
                    dt = datetime.datetime.strptime(t_str, "%Y-%m-%d")
                    return dt.strftime("%d/%m/%Y")
                elif "/" in t_str:
                    return t_str
            except Exception:
                pass
            return "Data não informada"

        for col in ["data_emissao", "data_necessidade", "entrega"]:
            if col in df_final.columns:
                df_final[col] = df_final[col].apply(lambda x: formatar_visual_seguro(x, incluir_hora=False))
                
        for col in ["data_ocorrencia", "data_ocorrencia_pc"]:
            if col in df_final.columns:
                df_final[col] = df_final[col].apply(lambda x: formatar_visual_seguro(x, incluir_hora=True))

        df_final["nome_solicitante"] = df_final["nome_solicitante"].fillna("RM Sem Fluxo Approvo").astype(str)
        df_final["desc_item"] = df_final["desc_item"].fillna("Direto p/ Compras").astype(str)

        df_final.fillna("---", inplace=True)
        df_final.replace("nan", "---", inplace=True)
        df_final.replace("None", "---", inplace=True)

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
            "nome_aprovador_pc":  ("APPROVAL (PC)", "Aprovador"),
            
            "sit_item":           ("SITUAÇÃO DO ITEM", "Situação"),
            "alerta_data":        ("ALERTA DE DATA", "Alerta de Entrega")
        }

        colunas_existentes = [col for col in colunas_multi_index.keys() if col in df_final.columns]
        df_exibicao = df_final[colunas_existentes].copy()
        df_exibicao.columns = pd.MultiIndex.from_tuples([colunas_multi_index[c] for c in colunas_existentes])
        
                # ==========================================================
        # 🎨 9. LAYOUT CROMÁTICO (PALETA PASTEL COMPLETA)
        # ==========================================================
        def aplicar_cores_corpo(df):
            estilos = pd.DataFrame('', index=df.index, columns=df.columns)
            mapa_indices = {orig_idx: pos for pos, orig_idx in enumerate(indices_para_manter) if orig_idx in df.index}
            
            for col in df.columns:
                grupo = col
                for i in df.index:
                    pos_lista = mapa_indices.get(i)
                    if pos_lista is not None:
                        dt_ent_nativo = lista_entrega_dt_bruta[pos_lista]
                        dt_nec_nativo = lista_necessidade_dt_bruta[pos_lista]
                        tem_atraso = dt_ent_nativo is not None and dt_nec_nativo is not None and (dt_ent_nativo > dt_nec_nativo)
                    else:
                        tem_atraso = False
                    
                    if tem_atraso:
                        estilos.at[i, col] = 'background-color: #fce4d6; color: #000000;'
                    else:
                        if grupo == "REQUISICAO DE MATERIAL MEGA":
                            estilos.at[i, col] = 'background-color: #f2f7f2; color: #000000;'
                        elif grupo == "APPROVAL (RM)":
                            estilos.at[i, col] = 'background-color: #e2f0d9; color: #000000;'
                        elif grupo == "PEDIDO DE COMPRA MEGA":
                            estilos.at[i, col] = 'background-color: #fbf2fa; color: #000000;'
                        elif grupo == "APPROVAL (PC)":
                            estilos.at[i, col] = 'background-color: #f3daf1; color: #000000;'
                            
                    if not tem_atraso:
                        if grupo == "SITUAÇÃO DO ITEM":
                            estilos.at[i, col] = 'background-color: #a9d08e; color: #000000; font-weight: bold; text-align: center;'
                        elif grupo == "ALERTA DE DATA":
                            estilos.at[i, col] = 'background-color: #fff2cc; color: #000000; text-align: center;'
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

    except Exception as e:
        st.error(f"❌ Erro crítico ao consolidar as visões no Cenário D: {e}")


