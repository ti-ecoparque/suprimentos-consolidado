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

try:
    # Busca apenas a coluna de nomes de forma leve
    res_nomes_req = supabase.table("vw_approvo_rm").select("nome_solicitante").execute()
    
    # Extrai os nomes eliminando duplicados e ignorando valores Nulos/Vazios
    nomes_unicos = set()
    for linha in res_nomes_req.data:
        nome = linha.get("nome_solicitante")
        if nome and pd.notna(nome) and str(nome).strip() != "" and str(nome).lower() != "nan":
            nomes_unicos.add(str(nome).strip())
            
    opcoes_requisitas = ["Todos"] + sorted(list(nomes_unicos))
except Exception:
    opcoes_requisitas = ["Todos"]

try:
    # Busca apenas a coluna comprador da view de pedidos
    res_nomes_comp = supabase.table("vw_approvo_pc").select("nome_solicitante").execute()
    
    compradores_unicos = set()
    for linha in res_nomes_comp.data:
        comp = linha.get("nome_solicitante")
        # Se for nulo, nan ou vazio, ignora para não poluir o selectbox
        if comp and pd.notna(comp) and str(comp).strip() != "" and str(comp).lower() != "nan":
            compradores_unicos.add(str(comp).strip())
            
    opcoes_compradores = ["Todos"] + sorted(list(compradores_unicos))
except Exception:
    opcoes_compradores = ["Todos"]

# ==========================================================
# 🛠️ 4. INTERFACE GRÁFICA DOS FILTROS INDEPENDENTES (NOMES SINCRONIZADOS)
# ==========================================================
st.markdown("#### 🔍 Painel de Filtros Globais")

col_f1, col_f2, col_f3 = st.columns(3)
col_f4, col_f5, col_f6 = st.columns(3)

with col_f1:
    buscar_rm = st.text_input("Filtrar por Número da RM:", "").strip()
with col_f2:
    # 🔥 MUDADO DE TEXT_INPUT PARA SELECTBOX: Lista os nomes reais salvos no Supabase
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
# 🚨 SUBSTITUA A LINHA DA TRAVA POR ESTA:
# 🚨 COLOQUE A TRAVA EXATAMENTE ASSIM:
tem_filtro_ativo = buscar_rm or filtro_req != "Todos" or filtro_comp != "Todos" or filtro_status_rm != "Todos" or filtro_status_pc != "Todos" or len(filtro_periodo) == 2


if not tem_filtro_ativo:
    st.info("💡 Selecione qualquer filtro acima ou digite uma RM para carregar os dados consolidados.")
    st.stop()

# ==========================================================
# 🚀 6. CONSTRUÇÃO DA QUERY INTELIGENTE E INDEPENDENTE
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

        if df_rm_bruto.empty:
            st.warning("⚠️ Nenhum registro de RM localizado para os filtros aplicados.")
            st.stop()

        # Extrai a lista de RMs localizadas de forma limpa e segura
        lista_rms_encontradas = []
        if "rm" in df_rm_bruto.columns:
            for r in df_rm_bruto["rm"].unique():
                if pd.notna(r) and str(r).replace('.0', '').isdigit():
                    lista_rms_encontradas.append(int(float(r)))

        df_vinculo = pd.DataFrame()
        df_pc_bruto = pd.DataFrame()

        # B. Consulta na tabela de vínculo físico pedido_compra
        if lista_rms_encontradas:
            res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").in_("rm", lista_rms_encontradas).execute()
            df_vinculo = pd.DataFrame(res_vinculo.data)

        # C. Consulta na visão de Pedidos de Compra (PC)
        if not df_vinculo.empty:
            lista_pedidos = []
            for p in df_vinculo["pedido"].unique():
                if pd.notna(p) and str(p).replace('.0', '').isdigit():
                    lista_pedidos.append(str(int(float(p))))
            
            if lista_pedidos:
                query_pc = supabase.table("vw_approvo_pc").select("*").in_("pedido", lista_pedidos)
                
                if filtro_comp != "Todos":
                    query_pc = query_pc.eq("nome_solicitante", filtro_comp)
                    
                res_pc = query_pc.execute()
                df_pc_bruto = pd.DataFrame(res_pc.data)
                
                if "entregas_agendadas" in df_pc_bruto.columns:
                    df_pc_bruto.drop(columns=["entregas_agendadas"], inplace=True)

        # ==========================================================
        # 🔄 7. LOGÍSTICA DE UNIFICAÇÃO (MERGE) E TRATAMENTO DE TEXTO (SEGURO)
        # ==========================================================
        if "rm" in df_rm_bruto.columns:
            df_rm_bruto["rm_str"] = df_rm_bruto["rm"].fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
        else:
            df_rm_bruto["rm_str"] = ""

        if "mat" in df_rm_bruto.columns:
            df_rm_bruto["mat_str"] = df_rm_bruto["mat"].fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
        else:
            df_rm_bruto["mat_str"] = ""
            
        colunas_vitais_rm = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str"]
        colunas_existentes_rm = [c for c in colunas_vitais_rm if c in df_rm_bruto.columns]
        df_rm_limpo = df_rm_bruto[colunas_existentes_rm].drop_duplicates().copy()
        
        if not df_vinculo.empty:
            df_vinculo["rm_str"] = df_vinculo["rm"].fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
            df_vinculo["pedido_str"] = df_vinculo["pedido"].fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
            
            df_consolidado = pd.merge(df_rm_limpo, df_vinculo[["rm_str", "pedido_str"]], on="rm_str", how="left")
            
            if not df_pc_bruto.empty:
                df_pc_bruto["pedido_str"] = df_pc_bruto["pedido"].fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
                df_pc_bruto["mat_str"] = df_pc_bruto["mat"].fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
                
                colunas_vitais_pc = ["pedido_str", "mat_str", "nome_solicitante", "entrega", "quantidade", "status_documento", "data_ocorrencia", "nome_aprovador"]
                colunas_existentes_pc = [c for c in colunas_vitais_pc if c in df_pc_bruto.columns]
                df_pc_limpo = df_pc_bruto[colunas_existentes_pc].drop_duplicates().copy()
                
                df_pc_limpo.rename(columns={
                    "nome_solicitante": "comprador",
                    "status_documento": "status_pc",
                    "data_oficial_ocorrencia": "data_ocorrencia_pc",
                    "data_ocorrencia": "data_ocorrencia_pc",
                    "nome_aprovador": "nome_aprovador_pc",
                    "quantidade": "quantidade_comprada"
                }, inplace=True, errors="ignore")
                
                df_consolidado["pedido_str"] = df_consolidado["pedido_str"].astype(str).str.strip()
                df_consolidado["mat_str"] = df_consolidado["mat_str"].astype(str).str.strip()
                df_pc_limpo["pedido_str"] = df_pc_limpo["pedido_str"].astype(str).str.strip()
                df_pc_limpo["mat_str"] = df_pc_limpo["mat_str"].astype(str).str.strip()
                
                df_final = pd.merge(df_consolidado, df_pc_limpo, on=["pedido_str", "mat_str"], how="left")
                
                if filtro_comp != "Todos":
                    df_final = df_final[df_final["comprador"].astype(str).str.strip() == str(filtro_comp).strip()]
                
                if filtro_status_pc != "Todos":
                    mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
                    sigla_procurada = mapa_invertido[filtro_status_pc]
                    df_final = df_final[df_final["status_pc"].astype(str).str.strip().str.upper() == sigla_procurada.upper()]
            else:
                df_final = df_consolidado.copy()
                for col in ["comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]:
                    df_final[col] = None
                
                if filtro_comp != "Todos" or filtro_status_pc != "Todos":
                    df_final = pd.DataFrame(columns=df_final.columns)
        else:
            df_final = df_rm_limpo.copy()
            df_final["pedido_str"] = None
            for col in ["comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]:
                df_final[col] = None
                
            if filtro_comp != "Todos" or filtro_status_pc != "Todos":
                df_final = pd.DataFrame(columns=df_final.columns)

        if "mat" in df_final.columns and "rm" in df_final.columns:
            df_final = df_final.drop_duplicates(subset=["rm", "mat"]).copy()
        else:
            df_final = df_final.drop_duplicates().copy()

                # ==========================================================
        # 🚨 7.5 PROCESSAMENTO SEGURO DE DATAS E CÁLCULO DE ATRASO (BLINDAGEM DA RAIZ)
        # ==========================================================
        # 🔥 FIX DEFINITIVO: Forçamos o 'errors="coerce"' IMEDIATAMENTE na criação das variáveis de cálculo.
        # Qualquer traço '---' ou 'Data não informada' do banco vira nulo matemático (NaT) e não quebra o sistema!
        dt_entrega_puro = pd.to_datetime(df_final["entrega"], errors="coerce")
        dt_necessidade_puro = pd.to_datetime(df_final["data_necessidade"], errors="coerce")
        dt_emissao_puro = pd.to_datetime(df_final["data_emissao"], errors="coerce")

        def calcular_atraso_seguro(idx):
            dt_ent = dt_entrega_puro.loc[idx]
            dt_nec = dt_necessidade_puro.loc[idx]
            
            # Se faltar qualquer uma das duas datas, responde com o texto padrão do negócio
            if pd.isna(dt_ent) or pd.isna(dt_nec):
                return "Data não informada"
                
            try:
                diferenca = (dt_ent - dt_nec).days
                if diferenca > 0:
                    return f"Atraso de {diferenca} dias"
                return "No prazo"
            except Exception:
                return "Data não informada"

        # Executa o mapeamento de atrasos com base nos vetores limpos da memória
        df_final["alerta_data"] = df_final.index.map(calcular_atraso_seguro)

        # Filtro de intervalo de período operando de forma 100% isolada e matemática
        if isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2:
            data_inicio = pd.to_datetime(filtro_periodo[0])
            data_fim = pd.to_datetime(filtro_periodo[1])
            
            indices_validos = df_final.index[(dt_emissao_puro >= data_inicio) & (dt_emissao_puro <= data_fim)]
            df_final = df_final.loc[indices_validos].copy()

        if df_final.empty:
            st.warning("⚠️ Nenhum registro corresponde aos critérios selecionados.")
            st.stop()

        # Guardamos cópias estáveis dos vetores datetime puros para a pintura de linhas na Etapa 9
        df_final["entrega_original_dt"] = pd.to_datetime(df_final["entrega"], errors="coerce")
        df_final["necessidade_original_dt"] = pd.to_datetime(df_final["data_necessidade"], errors="coerce")

        # ==========================================================
        # 📊 8. MAPEAMENTO, TRADUÇÃO E TEXTOS AMIGÁVEIS NAS COLUNAS
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

        # Formatação visual das datas na interface do usuário (Garante texto amigável se nulo)
        def formatar_data_segura(serie, incluir_hora=False):
            formato = "%d/%m/%Y %H:%M" if incluir_hora else "%d/%m/%Y"
            convertido = pd.to_datetime(serie, errors="coerce")
            return convertido.dt.strftime(formato).fillna("Data não informada")

        if "data_emissao" in df_final.columns:
            df_final["data_emissao"] = formatar_data_segura(df_final["data_emissao"])
        if "data_necessidade" in df_final.columns:
            df_final["data_necessidade"] = formatar_data_segura(df_final["data_necessidade"])
        if "entrega" in df_final.columns:
            df_final["entrega"] = formatar_data_segura(df_final["entrega"])
            
        if "data_ocorrencia" in df_final.columns:
            df_final["data_ocorrencia"] = formatar_data_segura(df_final["data_ocorrencia"], incluir_hora=True)
        if "data_ocorrencia_pc" in df_final.columns:
            df_final["data_ocorrencia_pc"] = formatar_data_segura(df_final["data_ocorrencia_pc"], incluir_hora=True)

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
        # 🎨 9. LAYOUT CROMÁTICO (PALETA PASTEL COMPLETA)
        # ==========================================================
        def aplicar_cores_corpo(df):
            estilos = pd.DataFrame('', index=df.index, columns=df.columns)
            for col in df.columns:
                grupo = col[0] # Nível 0 do MultiIndex (Super Cabeçalho)
                
                # Resgata a checagem de atraso calculada na etapa 7.5 de forma segura
                idx = estilos.index
                for i in idx:
                    alerta = str(df_final.loc[i, "alerta_data"]).lower()
                    tem_atraso = "atraso" in alerta
                    
                    if tem_atraso:
                        estilos.at[i, col] = 'background-color: #fce4d6; color: #000000;' # Vermelho claro para atrasos
                    else:
                        if grupo == "REQUISICAO DE MATERIAL MEGA":
                            estilos.at[i, col] = 'background-color: #f2f7f2; color: #000000;'
                        elif grupo == "APPROVAL (RM)":
                            estilos.at[i, col] = 'background-color: #e2f0d9; color: #000000;'
                        elif grupo == "PEDIDO DE COMPRA MEGA":
                            estilos.at[i, col] = 'background-color: #fbf2fa; color: #000000;'
                        elif grupo == "APPROVAL (PC)":
                            estilos.at[i, col] = 'background-color: #f3daf1; color: #000000;'
                            
                    # Aplica a cor das novas colunas operacionais se não houver atraso na linha
                    if not tem_atraso:
                        if grupo == "SITUAÇÃO DO ITEM":
                            estilos.at[i, col] = 'background-color: #70ad47; color: #ffffff; font-weight: bold;'
                        elif grupo == "ALERTA DE DATA":
                            estilos.at[i, col] = 'background-color: #fff2cc; color: #000000;'
            return estilos

        st.markdown("""
            <style>
                th.col_heading.level0 { font-weight: bold !important; color: #000000 !important; text-align: center !important; }
                th.col_heading.level0.id0_6 { background-color: #e2f0d9 !important; }
                th.col_heading.level0.id7_9 { background-color: #a9d08e !important; }
                th.col_heading.level0.id10_13 { background-color: #f2dcfa !important; }
                th.col_heading.level0.id14_16 { background-color: #df9ff2 !important; }
                th.col_heading.level0.id17 { background-color: #548235 !important; color: #ffffff !important; }
                th.col_heading.level0.id18 { background-color: #ffe599 !important; }
            </style>
        """, unsafe_allow_html=True)

        df_estilizado = df_exibicao.style.apply(aplicar_cores_corpo, axis=None)
        st.dataframe(df_estilizado, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"❌ Erro crítico ao consolidar as visões no Cenário D: {e}")
