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

# Inicializa as variáveis de controle de fluxo de forma limpa na raiz
df_final = pd.DataFrame()
lista_entrega_dt_bruta = []
lista_necessidade_dt_bruta = []
indices_para_manter = []

# ==========================================================
# 🚀 6. CONSTRUÇÃO DA QUERY INTELIGENTE INDEPENDENTE GLOBO-CENTRAL
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
            s_rm_b = df_rm_bruto["rm"].iloc[:, 0] if isinstance(df_rm_bruto["rm"], pd.DataFrame) else df_rm_bruto["rm"]
            lista_rms_encontradas = [int(float(x)) for x in s_rm_b.unique() if pd.notna(x) and str(x).strip() not in ["", "---", "nan"]]

        query_vinculo = supabase.table("pedido_compra").select("rm", "pedido")
        if buscar_rm:
            query_vinculo = query_vinculo.eq("rm", int(buscar_rm) if str(buscar_rm).isdigit() else 0)
        elif lista_rms_encontradas:
            query_vinculo = query_vinculo.in_("rm", lista_rms_encontradas)
            
        res_vinculo = query_vinculo.execute()
        df_vinculo = pd.DataFrame(res_vinculo.data)

        lista_peds_vinculados = []
        if not df_vinculo.empty and "pedido" in df_vinculo.columns:
            s_ped_b = df_vinculo["pedido"].iloc[:, 0] if isinstance(df_vinculo["pedido"], pd.DataFrame) else df_vinculo["pedido"]
            lista_peds_vinculados = [str(int(float(x))) for x in s_ped_b.unique() if pd.notna(x) and str(x).strip() not in ["", "---", "nan"]]

        # C. Consulta na visão de Pedidos de Compra (PC)
        df_pc_bruto = pd.DataFrame()
        deve_buscar_pc = filtro_comp != "Todos" or filtro_status_pc != "Todos" or len(lista_peds_vinculados) > 0

        if deve_buscar_pc:
            query_pc = supabase.table("vw_approvo_pc").select("*")
            if filtro_comp != "Todos":
                query_pc = query_pc.eq("nome_solicitante", filtro_comp)
            if filtro_status_pc != "Todos":
                mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
                query_pc = query_pc.eq("status_documento", mapa_invertido[filtro_status_pc])
            elif lista_peds_vinculados:
                query_pc = query_pc.in_("pedido", lista_peds_vinculados)
                
            res_pc = query_pc.limit(500).execute()
            df_pc_bruto = pd.DataFrame(res_pc.data)

        if not df_pc_bruto.empty and "entregas_agendadas" in df_pc_bruto.columns:
            df_pc_bruto.drop(columns=["entregas_agendadas"], inplace=True)

        if df_rm_bruto.empty and buscar_rm:
            df_rm_bruto = pd.DataFrame([{"rm": int(buscar_rm)}])

        # 🚨 COLUNAS EXCLUSIVAS DE CADA VISÃO PARA IMPEDIR DUPLICIDADES NO OUTER JOIN
        cols_exclusivas_rm = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador"]
        cols_exclusivas_pc = ["pedido", "mat", "nome_solicitante", "entrega", "quantidade", "status_documento", "data_ocorrencia", "nome_aprovador"]

        if df_rm_bruto.empty: df_rm_bruto = pd.DataFrame(columns=cols_exclusivas_rm)
        if df_pc_bruto.empty: df_pc_bruto = pd.DataFrame(columns=cols_exclusivas_pc)

        # ==========================================================
        # 🔄 7. LOGÍSTICA DE UNIFICAÇÃO (FILTRO RIGIDO DE CHAVES)
        # ==========================================================
        # 1. Limpeza e isolamento estrito da tabela de RMs
        df_rm_limpo = pd.DataFrame(index=df_rm_bruto.index)
        for c in cols_exclusivas_rm:
            if c in df_rm_bruto.columns:
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
            # Faz o merge intermediário mantendo apenas o par de ligação
            df_rm_consolidada = pd.merge(df_rm_limpo, df_vinculo_limpo[["rm_str", "pedido_str"]], on="rm_str", how="outer")
        else:
            df_rm_consolidada = df_rm_limpo.copy()
            df_rm_consolidada["pedido_str"] = "---"

        # 3. Limpeza e isolamento estrito da tabela de Pedidos (PC)
        df_pc_limpo = pd.DataFrame(index=df_pc_bruto.index)
        for c in cols_exclusivas_pc:
            if c in df_pc_bruto.columns:
                s = df_pc_bruto[c].iloc[:, 0] if isinstance(df_pc_bruto[c], pd.DataFrame) else df_pc_bruto[c]
                df_pc_limpo[c] = s.fillna("").astype(str).str.replace('.0', '', regex=False).str.strip()
        
        df_pc_limpo["pedido_str"] = df_pc_limpo.get("pedido", "---")
        df_pc_limpo["mat_str"] = df_pc_limpo.get("mat", "---")
        
        # Faz os rebatizados cirúrgicos das colunas exclusivas do PC para não colidirem com a RM
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

        # Lista padrão final para sanear nulos corporativos
        todas_colunas_vitais = ["nome_solicitante", "rm", "mat", "desc_item", "sit_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str", "pedido_str", "comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]
        for col in todas_colunas_vitais:
            if col not in df_final.columns: df_final[col] = "---"

        # Converte em série de texto simples antes de aplicar os filtros pós-cruzamento
        s_final_rm = df_final["rm"].iloc[:, 0] if isinstance(df_final["rm"], pd.DataFrame) else df_final["rm"]
        s_final_mat = df_final["mat"].iloc[:, 0] if isinstance(df_final["mat"], pd.DataFrame) else df_final["mat"]
        df_final["rm"] = s_final_rm.fillna(df_final["rm_str"]).astype(str)
        df_final["mat"] = s_final_mat.fillna(df_final["mat_str"]).astype(str)

        if buscar_rm:
            df_final = df_final[df_final["rm_str"].astype(str).str.strip() == str(buscar_rm).strip()]
        if filtro_req != "Todos":
            df_final = df_final[df_final["nome_solicitante"].astype(str).str.strip() == str(filtro_req).strip()]
        if filtro_comp != "Todos":
            df_final = df_final[df_final["comprador"].astype(str).str.strip() == str(filtro_comp).strip()]
        if filtro_status_pc != "Todos":
            mapa_invertido = {"Aprovado": "A", "Em Aprovação": "E", "Reprovado": "R"}
            df_final = df_final[df_final["status_pc"].astype(str).str.strip().str.upper() == mapa_invertido[filtro_status_pc].upper()]

        df_final["rm_mat_key"] = df_final["rm"].astype(str) + "_" + df_final["mat"].astype(str)
        df_final = df_final.drop_duplicates(subset=["rm_mat_key"]).copy()



        # ==========================================================
        # 🚨 7.5 PROCESSAMENTO SEGURO DE DATAS E CÁLCULO DE ATRASO
        # ==========================================================
        lista_alertas_data = []
        lista_dt_emissao_puro = []
        data_inicio_filtro = filtro_periodo[0] if isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2 else None
        data_fim_filtro = filtro_periodo[1] if isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2 else None

        for idx in df_final.index:
            val_entrega = df_final.loc[idx, "entrega"]
            val_necessidade = df_final.loc[idx, "data_necessidade"]
            val_emissao = df_final.loc[idx, "data_emissao"]
            
            def converter_para_data_nativa(valor):
                if pd.isna(valor) or str(valor).strip() in ["", "---", "nan", "None", "NaT"]: return None
                try:
                    if hasattr(valor, "date"): return valor.date()
                    t_str = str(valor).strip().split(" ")
                    if "-" in t_str[0]: return datetime.datetime.strptime(t_str[0], "%Y-%m-%d").date()
                    elif "/" in t_str[0]: return datetime.datetime.strptime(t_str[0], "%d/%m/%Y").date()
                except Exception: pass
                return None

            dt_ent = converter_para_data_nativa(val_entrega)
            dt_nec = converter_para_data_nativa(val_necessidade)
            dt_emi = converter_para_data_nativa(val_emissao)

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
if df_final.empty:
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
            series_exibicao[c] = col_data.iloc[:, 0].fillna("---").astype(str)
        else:
            series_exibicao[c] = col_data.fillna("---").astype(str)
    else:
        series_exibicao[c] = pd.Series("---", index=df_final.index, dtype=str)

# 🔥 CONSTRUÇÃO DO PAINEL DIRETO POR DICIONÁRIO DE TUPLAS
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
