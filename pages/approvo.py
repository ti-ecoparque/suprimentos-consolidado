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

st.markdown("#### 🔍 Painel de Filtros Globais")

# ==========================================================
# 🧱 GRID DE FILTROS TOTALMENTE BASEADOS EM DIGITAÇÃO LIVRE
# ==========================================================
col_esquerda, col_centro, col_direita = st.columns(3)

with col_esquerda:
    filtro_periodo = st.date_input("Intervalo (Data da Requisição):", value=[], format="DD/MM/YYYY", key="f_per")
    filtro_req = st.text_input("Filtrar por Nome do Requisitante (Ex: Edinelson, Karolina):", key="f_req").strip()
    filtro_status_rm = st.selectbox("Status da RM:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_rm")

with col_centro:
    buscar_rm = st.text_input("Filtrar por Número da RM:", key="b_rm").strip()
    buscar_pc = st.text_input("Filtrar por Número do Pedido de Compra (Nr. PC):", key="b_pc").strip()

with col_direita:
    filtro_status_pc = st.selectbox("Status do PC:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_pc")
    # 🌟 A EVOLUÇÃO: Comprador agora também é entrada por texto livre inteligente!
    filtro_comp = st.text_input("Filtrar por Nome do Comprador (Ex: Junior, Thais):", key="f_comp").strip()

st.write("") 

# Higienização segura de inputs textuais
if not filtro_req or str(filtro_req).strip() == "": filtro_req = "Todos"
if not filtro_comp or str(filtro_comp).strip() == "": filtro_comp = "Todos"
if not filtro_status_rm: filtro_status_rm = "Todos"
if not filtro_status_pc: filtro_status_pc = "Todos"

tem_filtro_ativo = buscar_rm or buscar_pc or filtro_req != "Todos" or filtro_comp != "Todos" or filtro_status_rm != "Todos" or filtro_status_pc != "Todos" or (isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2)
if not tem_filtro_ativo:
    st.info("💡 Selecione ou digite qualquer critério acima para carregar o painel.")
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

col_btn_esquerda, col_btn_direita = st.columns(2)

with col_btn_esquerda:
    def resetar_filtros_callback():
        for k in ["b_rm", "f_req", "f_comp", "f_st_rm", "f_st_pc", "f_per", "b_pc"]:
            if k in st.session_state:
                st.session_state[k] = [] if k == "f_per" else "" if ("b_" in k or "f_req" in k or "f_comp" in k) else "Todos"

    st.button("♻️ Limpar Filtros", on_click=resetar_filtros_callback, use_container_width=True, key="btn_limpar_exclusivo")

renderizar_grid_multiindex_colorido(df_final, lista_ent, lista_nec, col_btn_direita)
