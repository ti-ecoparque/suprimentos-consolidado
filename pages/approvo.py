import streamlit as st
import pandas as pd
import os
import datetime
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
# 🔍 3.5 COLETA DINÂMICA DE OPÇÕES DO BANCO (FILTROS)
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

col_header_limpar, col_btn_limpar = st.columns([5, 1])
with col_btn_limpar:
    # Lógica que zera fisicamente os valores da memória do Streamlit antes do re-run
    if st.button("♻️ Limpar Filtros", use_container_width=True):
        chaves_para_limpar = ["b_rm", "f_req", "f_comp", "f_st_rm", "f_st_pc", "f_per", "b_pc"]
        for chave in chaves_para_limpar:
            if chave in st.session_state:
                # Retorna listas e strings para o estado padrão vazio
                st.session_state[chave] = [] if chave == "f_per" else "" if "b_" in chave else "Todos"
        st.rerun()

col_f1, col_f2, col_f3 = st.columns(3)
col_f4, col_f5, col_f6 = st.columns(3)

# Vinculamos chaves controladas (key) para cada input da tela
with col_f1: 
    buscar_rm = st.text_input("Filtrar por Número da RM:", key="b_rm").strip()
with col_f2: 
    filtro_req = st.selectbox("Filtrar por Nome do Requisitante:", opcoes_requisitas, key="f_req")
with col_f3: 
    filtro_comp = st.selectbox("Filtrar por Nome do Comprador:", opcoes_compradores, key="f_comp")
    
with col_f4: 
    filtro_status_rm = st.selectbox("Status da RM:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_rm")
with col_f5: 
    filtro_status_pc = st.selectbox("Status do PC:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_pc")
with col_f6: 
    filtro_periodo = st.date_input("Intervalo (Data da Requisição):", value=[], format="DD/MM/YYYY", key="f_per")

buscar_pc = st.text_input("Filtrar por Número do Pedido de Compra (Nr. PC):", key="b_pc").strip()

# ==========================================================
# 🚀 5. TRAVA DE VALIDAÇÃO DE FILTROS SELECIONADOS
# ==========================================================
# Atualizado para validar também se o campo do PC foi preenchido
# Tratamento de contingência caso o reset limpe o texto das selectboxes para vazio
if not filtro_req: filtro_req = "Todos"
if not filtro_comp: filtro_comp = "Todos"
if not filtro_status_rm: filtro_status_rm = "Todos"
if not filtro_status_pc: filtro_status_pc = "Todos"

tem_filtro_ativo = buscar_rm or buscar_pc or filtro_req != "Todos" or filtro_comp != "Todos" or filtro_status_rm != "Todos" or filtro_status_pc != "Todos" or len(filtro_periodo) == 2

if not tem_filtro_ativo:
    st.info("💡 Selecione qualquer filtro acima para carregar o painel consolidado.")
    st.stop()

# Inicializa as variáveis de controle de fluxo de forma limpa na raiz
df_final = pd.DataFrame()
lista_entrega_dt_bruta = []
lista_necessidade_dt_bruta = []
indices_para_manter = []

# ==========================================================
# 🚀 6. CONSTRUÇÃO DA QUERY INTELIGENTE INDEPENDENTE (FUNÇÃO ESPECIAL DIRECT-RM)
# ==========================================================
with st.spinner("Buscando e cruzando visões comerciais..."):
    try:
        # 🌟 FUNÇÃO ESPECIAL FAST-TRACK: Se o usuário digitou uma RM, isola a busca para não quebrar!
        if buscar_rm and str(buscar_rm).strip() != "":
            rm_alvo = str(buscar_rm).strip()
            
            # 🚨 FIX DEFINITIVO DE TIPAGEM: Se o alvo for número puro, envia como int, senão envia como string
            rm_parametro = int(rm_alvo) if rm_alvo.isdigit() else rm_alvo
            
            # 1. Busca direta na visão de RMs do Supabase com o parâmetro de tipo corrigido
            res_rm = supabase.table("vw_approvo_rm").select("*").eq("rm", rm_parametro).limit(500).execute()
            df_rm_bruto = pd.DataFrame(res_rm.data)
            
            # 2. Busca direta na tabela de amarrações para ver se existe algum pedido
            res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").eq("rm", int(rm_alvo) if rm_alvo.isdigit() else 0).execute()
            df_vinculo = pd.DataFrame(res_vinculo.data)
            
            # 3. Se houver pedido amarrado, puxa os dados dele, senão cria tabela vazia segura
            df_pc_bruto = pd.DataFrame()
            if not df_vinculo.empty and "pedido" in df_vinculo.columns:
                lista_peds_pontes = [str(int(float(x))) for x in df_vinculo["pedido"].unique() if pd.notna(x)]
                if lista_peds_pontes:
                    res_pc = supabase.table("vw_approvo_pc").select("*").in_("pedido", lista_peds_pontes).limit(500).execute()
                    df_pc_bruto = pd.DataFrame(res_pc.data)
                    
        # 📐 FLUXO COMPARTILHADO NORMAL: Só executa se o campo de buscar RM estiver em branco
        elif buscar_pc:
            query_pc = supabase.table("vw_approvo_pc").select("*").eq("pedido", str(buscar_pc).strip())
            res_pc = query_pc.limit(500).execute()
            df_pc_bruto = pd.DataFrame(res_pc.data)
            
            res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").eq("pedido", int(buscar_pc) if str(buscar_pc).isdigit() else 0).execute()
            df_vinculo = pd.DataFrame(res_vinculo.data)
            
            lista_rms_pontes = [int(float(x)) for x in df_vinculo["rm"].unique() if pd.notna(x)] if "rm" in df_vinculo.columns else []
            if lista_rms_pontes:
                res_rm = supabase.table("vw_approvo_rm").select("*").in_("rm", lista_rms_pontes).execute()
                df_rm_bruto = pd.DataFrame(res_rm.data)
            else:
                df_rm_bruto = pd.DataFrame()
            
        else:
            # Fluxo padrão de filtros suspensos por nome/status/calendário
            query_rm = supabase.table("vw_approvo_rm").select("*")
            if filtro_req != "Todos": 
                query_rm = query_rm.eq("nome_solicitante", filtro_req)
            if filtro_status_rm != "Todos":
                query_rm = query_rm.eq("status_documento", {"Aprovado":"A","Em Aprovação":"E","Reprovado":"R"}[filtro_status_rm])
                
            res_rm = query_rm.limit(500).execute()
            df_rm_bruto = pd.DataFrame(res_rm.data)

            lista_rms_encontradas = [int(float(x)) for x in df_rm_bruto["rm"].unique() if pd.notna(x)] if "rm" in df_rm_bruto.columns else []
            query_vinculo = supabase.table("pedido_compra").select("rm", "pedido")
            if lista_rms_encontradas: 
                query_vinculo = query_vinculo.in_("rm", lista_rms_encontradas)
            res_vinculo = query_vinculo.execute()
            df_vinculo = pd.DataFrame(res_vinculo.data)

            lista_peds_vinculados = [str(int(float(x))) for x in df_vinculo["pedido"].unique() if pd.notna(x)] if "pedido" in df_vinculo.columns else []
            df_pc_bruto = pd.DataFrame()
            deve_buscar_pc = filtro_comp != "Todos" or filtro_status_pc != "Todos" or len(lista_peds_vinculados) > 0

            if deve_buscar_pc:
                query_pc = supabase.table("vw_approvo_pc").select("*")
                if filtro_comp != "Todos": query_pc = query_pc.eq("nome_solicitante", filtro_comp)
                if filtro_status_pc != "Todos": query_pc = query_pc.eq("status_documento", {"Aprovado":"A","Em Aprovação":"E","Reprovado":"R"}[filtro_status_pc])
                elif lista_peds_vinculados: query_pc = query_pc.in_("pedido", lista_peds_vinculados)
                res_pc = query_pc.limit(500).execute()
                df_pc_bruto = pd.DataFrame(res_pc.data)

        # Remove colunas técnicas e limpa instâncias nulas
        if not df_pc_bruto.empty and "entregas_agendadas" in df_pc_bruto.columns:
            df_pc_bruto.drop(columns=["entregas_agendadas"], inplace=True)

        # MATRIZ DE PRESERVAÇÃO DE CHAVES INTACTA (Margem Segura de 8 espaços)
        cols_exclusivas_rm = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str", "seq_item"]
        cols_exclusivas_pc = ["pedido", "mat", "nome_solicitante", "entrega", "quantidade", "status_documento", "data_ocorrencia", "nome_aprovador", "pedido_str", "mat_str"]

        if df_rm_bruto.empty: 
            df_rm_bruto = pd.DataFrame(columns=cols_exclusivas_rm, dtype=str)
        if df_pc_bruto.empty: 
            df_pc_bruto = pd.DataFrame(columns=cols_exclusivas_pc, dtype=str)
        
        # ==========================================================
        # 🔄 7. LOGÍSTICA DE UNIFICAÇÃO (FILTRO RIGIDO DE CHAVES)
        # ==========================================================
        # 1. Limpeza e isolamento estrito da tabela de RMs
        df_rm_limpo = pd.DataFrame(index=df_rm_bruto.index)
        for c in df_rm_bruto.columns:
            if c in cols_exclusivas_rm:
                s = df_rm_bruto[c].iloc[:, 0] if isinstance(df_rm_bruto[c], pd.DataFrame) else df_rm_bruto[c]
                df_rm_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
        
        df_rm_limpo["rm_str"] = df_rm_limpo.get("rm", "---")
        df_rm_limpo["mat_str"] = df_rm_limpo.get("mat", "---")
        df_rm_limpo = df_rm_limpo.drop_duplicates().copy()

        # 2. Limpeza e isolamento estrito da tabela de Vínculos
        if not df_vinculo.empty:
            df_vinculo_limpo = pd.DataFrame(index=df_vinculo.index)
            for c in ["rm", "pedido"]:
                if c in df_vinculo.columns:
                    s = df_vinculo[c].iloc[:, 0] if isinstance(df_vinculo[c], pd.DataFrame) else df_vinculo[c]
                    df_vinculo_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
            
            df_vinculo_limpo["rm_str"] = df_vinculo_limpo.get("rm", "---")
            df_vinculo_limpo["pedido_str"] = df_vinculo_limpo.get("pedido", "---")
            df_rm_consolidada = pd.merge(df_rm_limpo, df_vinculo_limpo[["rm_str", "pedido_str"]], on="rm_str", how="outer")
        else:
            df_rm_consolidada = df_rm_limpo.copy()
            df_rm_consolidada["pedido_str"] = "---"

        # 3. Limpeza e isolamento estrito da tabela de Pedidos (PC)
        df_pc_limpo = pd.DataFrame(index=df_pc_bruto.index)
        
        # 🚨 FIX CIRÚRGICO 2: Injetamos as variáveis temporárias de string antes do loop de exclusão
        df_pc_bruto["pedido_str"] = df_pc_bruto.get("pedido", "---")
        df_pc_bruto["mat_str"] = df_pc_bruto.get("mat", "---")

        for c in df_pc_bruto.columns:
            if c in cols_exclusivas_pc:
                s = df_pc_bruto[c].iloc[:, 0] if isinstance(df_pc_bruto[c], pd.DataFrame) else df_pc_bruto[c]
                df_pc_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
        
        # Faz os rebatizados cirúrgicos das colunas exclusivas do PC
        df_pc_limpo.rename(columns={
            "mat": "mat",
            "nome_solicitante": "comprador",
            "status_documento": "status_pc",
            "data_oficial_ocorrencia": "data_ocorrencia_pc",
            "data_ocorrencia": "data_ocorrencia_pc",
            "nome_aprovador": "nome_aprovador_pc",
            "quantidade": "quantidade_comprada"
        }, inplace=True, errors="ignore")
        df_pc_limpo = df_pc_limpo.drop_duplicates().copy()

        # Garante a existência física única e limpa das chaves de acoplamento
        for col_chave in ["pedido_str", "mat_str", "rm_str"]:
            if col_chave not in df_rm_consolidada.columns: df_rm_consolidada[col_chave] = "---"
            if col_chave not in df_pc_limpo.columns: df_pc_limpo[col_chave] = "---"
            
            if isinstance(df_rm_consolidada[col_chave], pd.DataFrame): df_rm_consolidada[col_chave] = df_rm_consolidada[col_chave].iloc[:, 0]
            if isinstance(df_pc_limpo[col_chave], pd.DataFrame): df_pc_limpo[col_chave] = df_pc_limpo[col_chave].iloc[:, 0]

            df_rm_consolidada[col_chave] = df_rm_consolidada[col_chave].astype(str).str.strip()
            df_pc_limpo[col_chave] = df_pc_limpo[col_chave].astype(str).str.strip()

        # 🔥 FIM DO KEYERROR E DO DATAFRAME ERROR: O outer join opera sobre colunas 100% limpas e mapeadas
        df_final = pd.merge(df_rm_consolidada, df_pc_limpo, on=["pedido_str", "mat_str"], how="outer")

         # Ajusta os nomes das colunas de pedidos para manter a compatibilidade com o resto do script
        if "pedido_str_y" in df_final.columns:
            df_final["pedido_str"] = df_final["pedido_str_y"].fillna(df_final.get("pedido_str_x", "---"))
        elif "pedido_str_x" in df_final.columns:
            df_final["pedido_str"] = df_final["pedido_str_x"]

        # Lista padrão final para sanear nulos corporativos
        todas_colunas_vitais = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str", "pedido_str", "comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]
        for col in todas_colunas_vitais:
            if col not in df_final.columns: df_final[col] = "---"

        # Converte em série de texto simples antes de aplicar os filtros pós-cruzamento
        # Converte em série de texto simples antes de aplicar os filtros pós-cruzamento
        s_final_rm = df_final["rm"].iloc[:, 0] if isinstance(df_final["rm"], pd.DataFrame) else df_final["rm"]
        s_final_mat = df_final["mat"].iloc[:, 0] if isinstance(df_final["mat"], pd.DataFrame) else df_final["mat"]
        
        # Saneia nulos estruturais forçando a tipagem para String nas colunas oficiais
        df_final["rm"] = s_final_rm.fillna(df_final.get("rm_str", "---")).astype(str).str.strip()
        df_final["mat"] = s_final_mat.fillna(df_final.get("mat_str", "---")).astype(str).str.strip()
        
        df_final["pedido_str"] = df_final["pedido_str"].fillna("---").astype(str).str.strip()
        df_final["nome_solicitante"] = df_final["nome_solicitante"].fillna("---").astype(str).str.strip()
        df_final["comprador"] = df_final["comprador"].fillna("---").astype(str).str.strip()

        # 🔥 BUSCA FLEXÍVEL OPERACIONAL: Filtra usando as colunas oficiais 'rm' e 'pedido_str'
        if buscar_rm and str(buscar_rm).strip() != "":
            v_rm_busca = str(buscar_rm).strip()
            df_final = df_final[df_final["rm"].str.contains(v_rm_busca, na=False, regex=False)]
            
        if filtro_req != "Todos":
            df_final = df_final[df_final["nome_solicitante"] == str(filtro_req).strip()]
            
        if filtro_comp != "Todos":
            df_final = df_final[df_final["comprador"] == str(filtro_comp).strip()]
            
        if buscar_pc and str(buscar_pc).strip() not in ["", "---", "nan", "None"]:
            v_pc_busca = str(buscar_pc).strip()
            df_final = df_final[df_final["pedido_str"].str.contains(v_pc_busca, na=False, regex=False)]
            
        if filtro_status_pc != "Todos":
            mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
            df_final = df_final[df_final["status_pc"].astype(str).str.strip().str.upper() == mapa_invertido[filtro_status_pc].upper()]
        
        # Se por flutuação o seq_item vier vazio em compras diretas, assume "---"
        df_final["seq_item"] = df_final.get("seq_item", pd.Series(dtype=str, index=df_final.index)).fillna("---").astype(str)

        # A chave junta RM + Material + Sequencial (1 a 9) listando as 9 linhas do parafuso intactas
        df_final["rm_mat_seq_key"] = df_final["rm"].astype(str) + "_" + df_final["mat"].astype(str) + "_" + df_final["seq_item"]
        df_final = df_final.drop_duplicates(subset=["rm_mat_seq_key"]).copy()


                # ==========================================================
        # 🚨 7.5 PROCESSAMENTO SEGURO DE DATAS E CÁLCULO DE ATRASO
        # ==========================================================
        

        lista_alertas_data = []
        lista_entrega_dt_bruta = []
        lista_necessidade_dt_bruta = []
        lista_dt_emissao_puro = []
        indices_para_manter = []

        # Só ativa o filtro de calendário se o usuário NÃO digitou uma RM ou PC direto na caixa
        ignorar_calendario = (buscar_rm and str(buscar_rm).strip() != "") or (buscar_pc and str(buscar_pc).strip() != "")

        data_inicio_filtro = filtro_periodo[0] if isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2 else None
        data_fim_filtro = filtro_periodo[1] if isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2 else None

        for idx in df_final.index:
            val_entrega = df_final.loc[idx, "entrega"]
            val_necessidade = df_final.loc[idx, "data_necessidade"]
            val_emissao = df_final.loc[idx, "data_emissao"]
            
            def converter_para_data_nativa(valor):
                if pd.isna(valor) or str(valor).strip() in ["", "---", "nan", "None", "NaT"]: 
                    return None
                try:
                    if hasattr(valor, "date"): return valor.date()
                    t_str = str(valor).strip().split(" ")[0].split("T")[0]
                    if "-" in t_str: return datetime.datetime.strptime(t_str, "%Y-%m-%d").date()
                    elif "/" in t_str: return datetime.datetime.strptime(t_str, "%d/%m/%Y").date()
                except Exception: pass
                return None

            dt_ent = converter_para_data_nativa(val_entrega)
            dt_nec = converter_para_data_nativa(val_necessidade)
            dt_emi = converter_para_data_nativa(val_emissao)

            # 🌟 BLINDAGEM MÁXIMA: Se buscou por RM ou PC, ignora o corte do calendário!
            if not ignorar_calendario:
                if data_inicio_filtro and data_fim_filtro:
                    if dt_emi is None or not (data_inicio_filtro <= dt_emi <= data_fim_filtro): 
                        continue

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
            
    except Exception as e:
        st.error(f"❌ Erro crítico ao consolidar as visões no Cenário D: {e}")
        st.stop()
# ==========================================================
# 🚨 TRAVAS DE SEGURANÇA E MULTIINDEX GLOBAIS (MARGEM ZERO)
# ==========================================================
if len(df_rm_bruto) == 0 and len(df_pc_bruto) == 0:
    st.warning("⚠️ Nenhum registro corresponde aos critérios selecionados no período filtrado.")
    st.stop()

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

df_final["qtd_solicitada"] = pd.to_numeric(df_final["qtd_solicitada"], errors="coerce").fillna(0).astype(int)
df_final["quantidade_comprada"] = pd.to_numeric(df_final["quantidade_comprada"], errors="coerce").fillna(0).astype(int)

def formatar_visual_seguro(valor, incluir_hora=False):
    if pd.isna(valor) or str(valor).strip() in ["", "---", "nan", "None", "NaT"]: 
        return "Data não informada"
    try:
        if hasattr(valor, "strftime"): 
            return valor.strftime("%d/%m/%Y %H:%M" if incluir_hora else "%d/%m/%Y")
        t_str = str(valor).strip().split(" ")
        if "-" in t_str[0]:
            dt = datetime.datetime.strptime(t_str[0], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        return valor
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

        # 🌟 FIX MATEMÁTICO: Se a coluna 'mat' original falhar ou vier com traço,
        # puxa o código numérico real guardado na nossa chave de texto 'mat_str'
df_final["mat"] = df_final["mat"].replace("---", None).fillna(df_final["mat_str"]).astype(str)

        # Tratamento final de nulos genéricos de texto
df_final.fillna("---", inplace=True)

df_final.replace("nan", "---", inplace=True)
df_final.replace("None", "---", inplace=True)

# LISTA DE ORDEM EXATA DOS EIXOS GLOBAIS (19 COLUNAS OFICIAIS)
ordem_colunas_exibicao = [
    "nome_solicitante", "rm", "mat", "desc_item", "qtd_solicitada", "data_emissao", "data_necessidade",
    "status_documento", "data_ocorrencia", "nome_aprovador",
    "comprador", "pedido_str", "entrega", "quantidade_comprada",
    "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc",
    "sit_item", "alerta_data"
]

# DICIONÁRIO DE TUPLAS DO MULTIINDEX (19 ELEMENTOS MATEMÁTICOS DE COMBINAÇÃO)
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

# Dicionário de séries temporárias isoladas para limpar duplicidades ocultas
series_exibicao = {}
for c in ordem_colunas_exibicao:
    if c in df_final.columns:
        col_data = df_final[c]
        if isinstance(col_data, pd.DataFrame):
            # 🚨 FIX DEFINITIVO: Forçamos o dtype para 'object' (Texto)
            series_exibicao[c] = col_data.iloc[:, 0].fillna("---").astype(object)
        else:
            # 🚨 FIX DEFINITIVO: Forçamos o dtype para 'object' (Texto)
            series_exibicao[c] = col_data.fillna("---").astype(object)
    else:
        # Se a coluna sumir do banco, cria ela em branco com tipo de texto puro garantido
        series_exibicao[c] = pd.Series("---", index=df_final.index, dtype=object)

# 🔥 A montagem do painel agora receberá tipos definidos e não vai mais explodir o ChunkedArray!
df_exibicao = pd.DataFrame({
    colunas_multi_index[c]: series_exibicao[c] for c in ordem_colunas_exibicao
})

# ==========================================================
# 🎨 9. LAYOUT CROMÁTICO (PALETA PASTEL COMPLETA)
# ==========================================================
def aplicar_cores_corpo(df):
    estilos = pd.DataFrame('', index=df.index, columns=df.columns)
    mapa_indices = {orig_idx: pos for pos, orig_idx in enumerate(indices_para_manter) if orig_idx in df.index}
    
    for col in df.columns:
        grupo = col[0] # Nível 0 do MultiIndex
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
