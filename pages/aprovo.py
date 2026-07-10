import streamlit as st
import os
from supabase import create_client

# Importações dos módulos customizados que criamos acima
from utils.queries import executar_consultas_supabase
from utils.processing import processar_e_unificar_dados
from utils.styles import renderizar_grid_multiindex_colorido

# ==========================================================
# 🔒 1. TRAVA DE SEGURANÇA E AUTO-LOGIN NATIVO
# ==========================================================
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

# Conexão banco
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Filtros Suspensos
opcoes_requisitas = ["Todos"]
opcoes_compradores = ["Todos"]
try:
    res_nomes_req = supabase.table("vw_approvo_rm").select("nome_solicitante").execute()
    opcoes_requisitas = ["Todos"] + sorted(list(set([str(l.get("nome_solicitante")).strip() for l in res_nomes_req.data if l.get("nome_solicitante")])))
    res_nomes_comp = supabase.table("vw_approvo_pc").select("nome_solicitante").execute()
    opcoes_compradores = ["Todos"] + sorted(list(set([str(l.get("nome_solicitante")).strip() for l in res_nomes_comp.data if l.get("nome_solicitante")])))
except Exception: pass

st.markdown("#### 🔍 Painel de Filtros Globais")

# 🔥 CORREÇÃO DO BOTÃO: Remove o st.columns() que causava a falha de leitura do arquivo
if st.button("♻️ Limpar Filtros", use_container_width=True):
    for k in ["b_rm", "f_req", "f_comp", "f_st_rm", "f_st_pc", "f_per", "b_pc"]:
        if k in st.session_state: 
            st.session_state[k] = [] if k == "f_per" else "" if "b_" in k else "Todos"
    st.rerun()

col_f1, col_f2, col_f3 = st.columns(3)
col_f4, col_f5, col_f6 = st.columns(3)

with col_f1: buscar_rm = st.text_input("Filtrar por Número da RM:", key="b_rm").strip()
with col_f2: filtro_req = st.selectbox("Filtrar por Nome do Requisitante:", opcoes_requisitas, key="f_req")
with col_f3: filtro_comp = st.selectbox("Filtrar por Nome do Comprador:", opcoes_compradores, key="f_comp")
with col_f4: filtro_status_rm = st.selectbox("Status da RM:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_rm")
with col_f5: filtro_status_pc = st.selectbox("Status do PC:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_pc")
with col_f6: filtro_periodo = st.date_input("Intervalo (Data da Requisição):", value=[], format="DD/MM/YYYY", key="f_per")
buscar_pc = st.text_input("Filtrar por Número do Pedido de Compra (Nr. PC):", key="b_pc").strip()

tem_filtro_ativo = buscar_rm or buscar_pc or filtro_req != "Todos" or filtro_comp != "Todos" or filtro_status_rm != "Todos" or filtro_status_pc != "Todos" or (isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2)
if not tem_filtro_ativo:
    st.info("💡 Selecione qualquer filtro acima para carregar o painel.")
    st.stop()

# 🔥 OPERAÇÃO MODULARIZADA SEGURA E À PROVA DE CHUNKEDARRAY
with st.spinner("Processando árvore de suprimentos..."):
    df_rm, df_pc, df_vinculo = executar_consultas_supabase(supabase, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_rm, filtro_status_pc)

# 🚨 Trava Antecipada Máxima: Se o banco voltou vazio, para a execução antes de gerar o ChunkedArray!
if df_rm.empty and df_pc.empty:
    st.warning("⚠️ Nenhum registro correspondente aos critérios foi localizado no banco de dados.")
    st.stop()

# Executa as unificações lógicas
df_final, lista_ent, lista_nec = processar_e_unificar_dados(df_rm, df_pc, df_vinculo, buscar_rm, buscar_pc, filtro_req, filtro_comp, filtro_status_pc, filtro_periodo)

# Segunda trava caso os filtros de calendário esvaziem a tabela
if df_final.empty:
    st.warning("⚠️ Nenhum registro localizado para o período filtrado.")
    st.stop()

# Renderiza as cores e o MultiIndex de forma limpa e isolada
renderizar_grid_multiindex_colorido(df_final, lista_ent, lista_nec)
