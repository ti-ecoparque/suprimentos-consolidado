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
# 🚀 6. CONSTRUÇÃO DA QUERY INTELIGENTE GLOBO-CENTRAL (PC FIRST)
# ==========================================================
with st.spinner("Buscando e cruzando visões comerciais..."):
    try:
        query_pc = supabase.table("vw_approvo_pc").select("*")
        
        if filtro_comp != "Todos":
            query_pc = query_pc.eq("nome_solicitante", filtro_comp)
        if filtro_status_pc != "Todos":
            mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
            query_pc = query_pc.eq("status_documento", mapa_invertido[filtro_status_pc])
            
        res_pc = query_pc.limit(500).execute()
        df_pc_bruto = pd.DataFrame(res_pc.data)

        lista_pedidos_encontrados = []
        if not df_pc_bruto.empty and "pedido" in df_pc_bruto.columns:
            for p in df_pc_bruto["pedido"].unique():
                if pd.notna(p) and str(p).strip() not in ["", "---", "nan", "None"]:
                    lista_pedidos_encontrados.append(str(int(float(p))))
                    
            if "entregas_agendadas" in df_pc_bruto.columns:
                df_pc_bruto.drop(columns=["entregas_agendadas"], inplace=True)

        df_vinculo = pd.DataFrame()
        lista_rms_ponte = []
        if lista_pedidos_encontrados:
            res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").in_("pedido", lista_pedidos_encontrados).execute()
            df_vinculo = pd.DataFrame(res_vinculo.data)
            
            if not df_vinculo.empty and "rm" in df_vinculo.columns:
                lista_rms_ponte = list(set([int(float(x)) for x in df_vinculo["rm"] if pd.notna(x)]))

        df_rm_bruto = pd.DataFrame()
        query_rm = supabase.table("vw_approvo_rm").select("*")
        
        if buscar_rm:
            query_rm = query_rm.eq("rm", str(buscar_rm))
        elif lista_rms_ponte:
            query_rm = query_rm.in_("rm", lista_rms_ponte)
        
        if filtro_req != "Todos":
            query_rm = query_rm.eq("nome_solicitante", filtro_req)
        if filtro_status_rm != "Todos":
            mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
            query_rm = query_rm.eq("status_documento", mapa_invertido[filtro_status_rm])
            
        res_rm = query_rm.execute()
        df_rm_bruto = pd.DataFrame(res_rm.data)

        if df_rm_bruto.empty and buscar_rm:
            df_rm_bruto = pd.DataFrame([{"rm": int(buscar_rm)}])

        if df_pc_bruto.empty and df_rm_bruto.empty:
            st.warning("⚠️ Nenhum registro localizado para os critérios selecionados.")
            st.stop()

            # ==========================================================
            # 🔄 7. LOGÍSTICA DE UNIFICAÇÃO (MERGE INVERSO: PC COMO BASE)
            # ==========================================================
            # 1. Prepara e limpa a tabela base de Pedidos de Compra (PC)
            if not df_pc_bruto.empty:
                df_pc_bruto["pedido_str"] = df_pc_bruto["pedido"].fillna("").astype(str).str.split('.').str[0].str.strip()
                df_pc_bruto["mat_str"] = df_pc_bruto["mat"].fillna("").astype(str).str.split('.').str[0].str.strip()
                
                colunas_vitais_pc = ["pedido_str", "mat_str", "nome_solicitante", "entrega", "quantidade", "status_documento", "data_ocorrencia", "nome_aprovador"]
                colunas_existentes_pc = [c for c in colunas_vitais_pc if c in df_pc_bruto.columns]
                
                df_pc_base = df_pc_bruto[colunas_existentes_pc].drop_duplicates().copy()
                df_pc_base.rename(columns={
                    "nome_solicitante": "comprador",
                    "status_documento": "status_pc",
                    "data_oficial_ocorrencia": "data_ocorrencia_pc",
                    "data_ocorrencia": "data_ocorrencia_pc",
                    "nome_aprovador": "nome_aprovador_pc",
                    "quantidade": "quantidade_comprada"
                }, inplace=True, errors="ignore")
            else:
                df_pc_base = pd.DataFrame(columns=["pedido_str", "mat_str", "comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"])

            # 2. Prepara e limpa a tabela de vínculo intermediária
            if not df_vinculo.empty:
                df_vinculo["rm_str"] = df_vinculo["rm"].fillna("").astype(str).str.split('.').str[0].str.strip()
                df_vinculo["pedido_str"] = df_vinculo["pedido"].fillna("").astype(str).str.split('.').str[0].str.strip()
                
                # Junta o Pedido Base com o número da RM que ele gerou
                df_pc_consolidado = pd.merge(df_pc_base, df_vinculo[["pedido_str", "rm_str"]], on="pedido_str", how="left")
            else:
                df_pc_consolidado = df_pc_base.copy()
                df_pc_consolidado["rm_str"] = ""

            # 3. Prepara a tabela de RMs da vw_approvo_rm
            if not df_rm_bruto.empty:
                df_rm_bruto["rm_str"] = df_rm_bruto["rm"].fillna("").astype(str).str.split('.').str[0].str.strip()
                df_rm_bruto["mat_str"] = df_rm_bruto["mat"].fillna("").astype(str).str.split('.').str[0].str.strip()
                
                colunas_vitais_rm = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str"]
                colunas_existentes_rm = [c for c in colunas_vitais_rm if c in df_rm_bruto.columns]
                df_rm_limpo = df_rm_bruto[colunas_existentes_rm].drop_duplicates().copy()
                
                # 🚨 CRUZAMENTO SEGURO INVERSO: Acopla os dados da RM ao lado do Pedido de Compra
                df_final = pd.merge(df_pc_consolidado, df_rm_limpo, on=["rm_str", "mat_str"], how="left")
            else:
                df_final = df_pc_consolidado.copy()
                for col in ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador"]:
                    df_final[col] = None

            # 🚨 TRAVA DE TRATAMENTO EXTRA: Se o pedido existe mas a RM pulou o Approvo, preenche colunas verdes de forma amigável
            df_final["rm"] = df_final["rm"].fillna(df_final["rm_str"])
            df_final["mat"] = df_final["mat"].fillna(df_final["mat_str"])
            df_final["nome_solicitante"] = df_final["nome_solicitante"].fillna("RM Sem Fluxo Approvo")
            df_final["desc_item"] = df_final["desc_item"].fillna("Direto p/ Compras")

            # Aplica as travas secundárias de filtros combinados rígidos na tela
            if buscar_rm:
                df_final = df_final[df_final["rm_str"] == str(buscar_rm).strip()]
            if filtro_req != "Todos":
                df_final = df_final[df_final["nome_solicitante"].astype(str).str.strip() == str(filtro_req).strip()]
            if filtro_status_rm != "Todos":
                mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
                df_final = df_final[df_final["status_documento"].astype(str).str.strip() == mapa_invertido[filtro_status_rm]]

            # Remove linhas duplicadas geradas pelo histórico final
            if "mat" in df_final.columns and "rm" in df_final.columns:
                df_final = df_final.drop_duplicates(subset=["rm", "mat"]).copy()
            else:
                df_final = df_final.drop_duplicates().copy()
        # ==========================================================
        # 🚨 7.5 PROCESSAMENTO SEGURO DE DATAS E CÁLCULO DE ATRASO
        # ==========================================================
        # Criamos vetores isolados em formato datetime puro forçando NaT em qualquer string inválida
        dt_entrega_puro = pd.to_datetime(df_final["entrega"], errors="coerce")
        dt_necessidade_puro = pd.to_datetime(df_final["data_necessidade"], errors="coerce")
        dt_emissao_puro = pd.to_datetime(df_final["data_emissao"], errors="coerce")

        def calcular_atraso_seguro(idx):
            dt_ent = dt_entrega_puro.loc[idx]
            dt_nec = dt_necessidade_puro.loc[idx]
            
            if pd.isna(dt_ent) or pd.isna(dt_nec):
                return "Data não informada"
                
            try:
                diferenca = (dt_ent - dt_nec).days
                if diferenca > 0:
                    return f"Atraso de {diferenca} dias"
                return "No prazo"
            except Exception:
                return "Data não informada"

        # Executa o cálculo usando os índices mapeados das séries isoladas
        df_final["alerta_data"] = df_final.index.map(calcular_atraso_seguro)

        # Filtro de intervalo de período operando de forma 100% isolada e matemática pelos índices
        if isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2:
            # 🔍 FIX DEFINITIVO: Extrai os dois valores e valida se não são nulos antes de rodar o merge horizontal
            d_ini = filtro_periodo[0]
            d_fim = filtro_periodo[1]
            
            if pd.notna(d_ini) and pd.notna(d_fim):
                data_inicio = pd.to_datetime(d_ini)
                data_fim = pd.to_datetime(d_fim)
                
                # Aplica o filtro de intervalo usando os índices estáveis do vetor isolado na memória
                indices_validos = df_final.index[(dt_emissao_puro >= data_inicio) & (dt_emissao_puro <= data_fim)]
                df_final = df_final.loc[indices_validos].copy()

        if df_final.empty:
            st.warning("⚠️ Nenhum registro corresponde aos critérios selecionados.")
            st.stop()
        # Guardamos cópias estáveis dos vetores datetime puros para a pintura de linhas na Etapa 9
        #df_final["entrega_original_dt"] = pd.to_datetime(df_final["entrega"], errors="coerce")
        #df_final["necessidade_original_dt"] = pd.to_datetime(df_final["data_necessidade"], errors="coerce")

        # ==========================================================
        # 📊 8. MAPEAMENTO, TRADUÇÃO E PROCESSAMENTO COMPLETO DE STRINGS
        # ==========================================================
        mapa_status_extenso = {"A": "Aprovado", "E": "Em Aprovação", "R": "Reprovado", "---": "---"}
        
        if "status_documento" in df_final.columns:
            df_final["status_documento"] = df_final["status_documento"].map(
                lambda x: mapa_status_extenso.get(str(x).strip().upper(), "---") if pd.notna(x) else "---"
            )
        if "status_pc" in df_final.columns:
            df_final["status_pc"] = df_final["status_pc"].map(
                lambda x: mapa_status_extenso.get(str(x).strip().upper(), "---") if pd.notna(x) else "---"
            )

        if "qtd_solicitada" in df_final.columns:
            df_final["qtd_solicitada"] = pd.to_numeric(df_final["qtd_solicitada"], errors="coerce").fillna(0).astype(int)
        if "quantidade_comprada" in df_final.columns:
            df_final["quantidade_comprada"] = pd.to_numeric(df_final["quantidade_comprada"], errors="coerce").fillna(0).astype(int)

        # 🚨 SOLUÇÃO REAL CONTRA O ERRO DE DTYPE:
        # Antes de injetar textos amigáveis, forçamos as colunas de data a virarem strings comuns (tipo 'object').
        # Isso remove a tipagem datetime64 nativa e impede o Pandas de lançar exceções.
        colunas_de_data = ["data_emissao", "data_necessidade", "entrega", "data_ocorrencia", "data_ocorrencia_pc"]
        for col in colunas_de_data:
            if col in df_final.columns:
                # Converte os valores brutos para data e depois gera a string formatada de forma segura
                convertido = pd.to_datetime(df_final[col], errors="coerce")
                
                if col in ["data_ocorrencia", "data_ocorrencia_pc"]:
                    df_final[col] = convertido.dt.strftime("%d/%m/%Y %H:%M").fillna("Data não informada").astype(str)
                else:
                    df_final[col] = convertido.dt.strftime("%d/%m/%Y").fillna("Data não informada").astype(str)

        # Tratamento final de nulos genéricos para as demais colunas de texto (Apenas no final!)
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
            "nome_aprovador_pc":  ("APPROVAL (PC)", "Aprovador"),
            
            "sit_item":           ("SITUAÇÃO DO ITEM", "Situação"),
            "alerta_data":        ("ALERTA DE DATA", "Alerta de Entrega")
        }

        colunas_existentes = [col for col in colunas_multi_index.keys() if col in df_final.columns]
        df_exibicao = df_final[colunas_existentes].copy()
        df_exibicao.columns = pd.MultiIndex.from_tuples([colunas_multi_index[c] for c in colunas_existentes])

                # ==========================================================
        # 🎨 9. LAYOUT CROMÁTICO (PALETA PASTEL COMPLETA ATUALIZADA)
        # ==========================================================
        def aplicar_cores_corpo(df):
            estilos = pd.DataFrame('', index=df.index, columns=df.columns)
            for col in df.columns:
                grupo = col[0] # Nível 0 do MultiIndex (Super Cabeçalho)
                
                for i in df.index:
                    alerta = str(df_final.loc[i, "alerta_data"]).lower()
                    tem_atraso = "atraso" in alerta
                    
                    if tem_atraso:
                        # Se houver atraso, aplica o Vermelho Pastel Suave na linha
                        estilos.at[i, col] = 'background-color: #fce4d6; color: #000000;'
                    else:
                        # Se estiver no prazo, segue a identidade cromática do Excel
                        if grupo == "REQUISICAO DE MATERIAL MEGA":
                            estilos.at[i, col] = 'background-color: #f2f7f2; color: #000000;'
                        elif grupo == "APPROVAL (RM)":
                            estilos.at[i, col] = 'background-color: #e2f0d9; color: #000000;'
                        elif grupo == "PEDIDO DE COMPRA MEGA":
                            estilos.at[i, col] = 'background-color: #fbf2fa; color: #000000;'
                        elif grupo == "APPROVAL (PC)":
                            st_pc = str(df_final.loc[i, "status_pc"]).upper().strip()
                            if st_pc in ["A", "APROVADO"]:
                                estilos.at[i, col] = 'background-color: #f3daf1; color: #000000;'
                            else:
                                estilos.at[i, col] = 'background-color: #fbf2fa; color: #000000;'
                            
                    # Regras fixas de destaque se a linha não estiver em atraso
                    if not tem_atraso:
                        if grupo == "SITUAÇÃO DO ITEM":
                            estilos.at[i, col] = 'background-color: #c6e0b4; color: #000000; font-weight: bold; text-align: center;'
                        elif grupo == "ALERTA DE DATA":
                            estilos.at[i, col] = 'background-color: #fff2cc; color: #000000; text-align: center;'
            return estilos

        # Injeta o CSS bruto mapeando a contagem real das colunas na tela (0 a 18)
        st.markdown("""
            <style>
                th.col_heading.level0 { font-weight: bold !important; color: #000000 !important; text-align: center !important; }
                
                /* Mapeamento milimétrico das larguras das seções coloridas superiores */
                th.col_heading.level0.id0_6 { background-color: #e2f0d9 !important; }   /* REQUISICAO DE MATERIAL MEGA (7 colunas) */
                th.col_heading.level0.id7_9 { background-color: #a9d08e !important; }   /* APPROVAL (RM) (3 colunas) */
                th.col_heading.level0.id10_13 { background-color: #f2dcfa !important; } /* PEDIDO DE COMPRA MEGA (4 colunas) */
                th.col_heading.level0.id14_16 { background-color: #df9ff2 !important; } /* APPROVAL (PC) (3 colunas) */
                
                /* Novas colunas operacionais no final */
                th.col_heading.level0.id17 { background-color: #548235 !important; color: #ffffff !important; } /* SITUAÇÃO DO ITEM */
                th.col_heading.level0.id18 { background-color: #ffe599 !important; }   /* ALERTA DE DATA */
                
                /* Centraliza os títulos da linha inferior para acompanhar o Excel */
                th.col_heading.level1 { text-align: center !important; }
            </style>
        """, unsafe_allow_html=True)

        # Renderiza a tabela definitiva perfeitamente estilizada
        df_estilizado = df_exibicao.style.apply(aplicar_cores_corpo, axis=None)
        st.dataframe(df_estilizado, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"❌ Erro crítico ao consolidar as visões no Cenário D: {e}")

