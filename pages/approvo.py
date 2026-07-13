import streamlit as st
import os
import datetime
from supabase import create_client

# Importação dos sub-módulos utilitários da pasta utils
from utils.queries import executar_consultas_supabase
from utils.processing import processar_e_unificar_dados
from utils.styles import renderizar_grid_multiindex_colorido

if "logado" not in st.session_state or not st.session_state.logado:
    usuario_url = st.query_params.get("u")
    if usuario_url:
        st.session_state.logado = True
        st.session_state.usuario_atual = usuario_url
    else:
        st.warning("⚠️ Acesso restrito. Faça login na tela inicial.")
        if st.button("Ir para a Tela de Login"): st.switch_page("app.py")
        st.stop()

st.subheader("✅ Approvo Status")
st.write("Visão unificada modularizada de alta performance.")
st.divider()

SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

opcoes_requisitas = ["Todos"]
opcoes_compradores = ["Todos"]
try:
    # 🌟 VASCULHAMENTO: Puxa o lote bruto de nomes direto da tabela física
    res_nomes_req = supabase.table("rel_solicitacao_compras").select("usuario_solicitante").execute()
    
    nomes_tratados_req = []
    if res_nomes_req.data:
        for registro in res_nomes_req.data:
            nome_cru = registro.get("usuario_solicitante")
            if nome_cru and str(nome_cru).strip() not in ["", "nan", "None", "---"]:
                nome_limpo = str(nome_cru).strip()
                
                # ✂️ SEPARAÇÃO INTELIGENTE: Só fatia o texto se o ponto realmente existir no nome!
                if "." in nome_limpo:
                    partes = nome_limpo.split(".", 1)
                    if len(partes) > 1:
                        nome_limpo = partes[1].strip()
                
                # Formata com iniciais maiúsculas e salva na lista
                nomes_tratados_req.append(nome_limpo.title())
                
    # O set() elimina duplicidades de forma automática na memória RAM
    opcoes_requisitas = ["Todos"] + sorted(list(set(nomes_tratados_req)))

    # Puxa os compradores reais sem colisão
    res_nomes_comp = supabase.table("vw_approvo_pc").select("nome_aprovador").execute()
    nomes_tratados_comp = []
    if res_nomes_comp.data:
        for registro in res_nomes_comp.data:
            comp_cru = registro.get("nome_aprovador")
            if comp_cru and str(comp_cru).strip() not in ["", "nan", "None", "---"]:
                comp_limpo = str(comp_cru).strip()
                
                # Aplica a mesma proteção para a lista de compradores
                if "." in comp_limpo:
                    partes = comp_limpo.split(".", 1)
                    if len(partes) > 1:
                        comp_limpo = partes[1].strip()
                    
                nomes_tratados_comp.append(comp_limpo.title())
            
    opcoes_compradores = ["Todos"] + sorted(list(set(nomes_放tados_comp)))

except Exception as e:
    pass

st.markdown("#### 🔍 Painel de Filtros Globais")

# ==========================================================
# 🧱 GRID DE FILTROS REORGANIZADOS (3 COLUNAS VERTICAIS)
# ==========================================================
col_esquerda, col_centro, col_direita = st.columns(3)

# 📐 COLUNA DA ESQUERDA (DATA, REQUISITANTE E STATUS RM)
with col_esquerda:
    filtro_periodo = st.date_input("Intervalo (Data da Requisição):", value=[], format="DD/MM/YYYY", key="f_per")
    filtro_req = st.selectbox("Filtrar por Nome do Requisitante:", opcoes_requisitas, key="f_req")
    filtro_status_rm = st.selectbox("Status da RM:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_rm")

# 📐 COLUNA DO CENTRO (NÚMEROS DIGITADOS)
with col_centro:
    buscar_rm = st.text_input("Filtrar por Número da RM:", key="b_rm").strip()
    buscar_pc = st.text_input("Filtrar por Número do Pedido de Compra (Nr. PC):", key="b_pc").strip()

# 📐 COLUNA DA DIREITA (STATUS PC E COMPRADOR)
with col_direita:
    filtro_status_pc = st.selectbox("Status do PC:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_pc")
    filtro_comp = st.selectbox("Filtrar por Nome do Comprador:", opcoes_compradores, key="f_comp")

st.write("") 

if not filtro_req: filtro_req = "Todos"
if not filtro_comp: filtro_comp = "Todos"
if not filtro_status_rm: filtro_status_rm = "Todos"
if not filtro_status_pc: filtro_status_pc = "Todos"

tem_filtro_ativo = buscar_rm or buscar_pc or filtro_req != "Todos" or filtro_comp != "Todos" or filtro_status_rm != "Todos" or filtro_status_pc != "Todos" or (isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2)
if not tem_filtro_ativo:
    st.info("💡 Selecione qualquer filtro acima para carregar o painel consolidado.")
    st.stop()

with st.spinner("Processando árvore de suprimentos..."):
    df_rm, df_pc, df_vinculo = executar_consultas_supabase(supabase, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_rm, filtro_status_pc)

if df_rm.empty and df_pc.empty:
    st.warning("⚠️ Nenhum registro correspondente aos critérios foi localizado no banco de dados.")
    st.stop()

df_final, lista_ent, lista_nec = processar_e_unificar_dados(df_rm, df_pc, df_vinculo, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_pc, filtro_periodo)

if df_final.empty:
    st.warning("⚠️ Nenhum registro localizado para o período filtrado.")
    st.stop()

# ==========================================================
# 🚨 RETRANCA DE LAYOUT: BOTÕES UNIFICADOS LADO A LADO
# ==========================================================
col_btn_esquerda, col_btn_direita = st.columns(2)

with col_btn_esquerda:
    def resetar_filtros_callback():
        for k in ["b_rm", "f_req", "f_comp", "f_st_rm", "f_st_pc", "f_per", "b_pc"]:
            if k in st.session_state:
                st.session_state[k] = [] if k == "f_per" else "" if "b_" in k else "Todos"

    st.button("♻️ Limpar Filtros", on_click=resetar_filtros_callback, use_container_width=True, key="btn_limpar_exclusivo")

renderizar_grid_multiindex_colorido(df_final, lista_ent, lista_nec, col_btn_direita)
