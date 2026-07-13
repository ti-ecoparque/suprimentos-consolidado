import streamlit as st
import os
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
    res_nomes_req = supabase.table("vw_approvo_rm").select("nome_solicitante").execute()
    opcoes_requisitas = ["Todos"] + sorted(list(set([str(l.get("nome_solicitante")).strip() for l in res_nomes_req.data if l.get("nome_solicitante")])))
    res_nomes_comp = supabase.table("vw_approvo_pc").select("nome_solicitante").execute()
    opcoes_compradores = ["Todos"] + sorted(list(set([str(l.get("nome_solicitante")).strip() for l in res_nomes_comp.data if l.get("nome_solicitante")])))
except Exception: pass

st.markdown("#### 🔍 Painel de Filtros Globais")

# ♻️ Função segura de reset nativo via Session State
def resetar_filtros_callback():
    for k in ["b_rm", "f_req", "f_comp", "f_st_rm", "f_st_pc", "f_per", "b_pc"]:
        if k in st.session_state:
            st.session_state[k] = [] if k == "f_per" else "" if "b_" in k else "Todos"

st.button("♻️ Limpar Filtros", on_click=resetar_filtros_callback, use_container_width=True)

# ==========================================================
# 🧱 GRID DE FILTROS ORGANIZADOS
# ==========================================================
col_f1, col_f2, col_f3 = st.columns(3)
col_f4, col_f5, col_f6 = st.columns(3)

with col_f1: 
    filtro_req = st.selectbox("Filtrar por Nome do Requisitante:", opcoes_requisitas, key="f_req")
with col_f2: 
    buscar_rm = st.text_input("Filtrar por Número da RM:", key="b_rm").strip()
with col_f3: 
    filtro_comp = st.selectbox("Filtrar por Nome do Comprador:", opcoes_compradores, key="f_comp")

with col_f4: 
    filtro_periodo = st.date_input("Intervalo (Data da Requisição):", value=[], format="DD/MM/YYYY", key="f_per")
with col_f5: 
    buscar_pc = st.text_input("Filtrar por Número do Pedido de Compra (Nr. PC):", key="b_pc").strip()
with col_f6: 
    filtro_status_rm = st.selectbox("Status da RM:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_rm")

filtro_status_pc = st.selectbox("Status do PC:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"], key="f_st_pc")

st.write("") 

# (O seu código de higienização de filtros continua normal acima...)
if not filtro_req: filtro_req = "Todos"
if not filtro_comp: filtro_comp = "Todos"
if not filtro_status_rm: filtro_status_rm = "Todos"
if not filtro_status_pc: filtro_status_pc = "Todos"

tem_filtro_ativo = buscar_rm or buscar_pc or filtro_req != "Todos" or filtro_comp != "Todos" or filtro_status_rm != "Todos" or filtro_status_pc != "Todos" or (isinstance(filtro_periodo, (list, tuple)) and len(filtro_periodo) == 2)
if not tem_filtro_ativo:
    st.info("💡 Selecione qualquer filtro acima para carregar o painel.")
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
# 🚨 NOVA RETRANCA DE LAYOUT: BOTÕES LADO A LADO NO TOPO DA TABELA
# ==========================================================
col_btn_esquerda, col_btn_direita = st.columns(2)

# 1. Desenha o botão de limpar perfeitamente encaixado no lado esquerdo
with col_btn_esquerda:
    # Função segura de reset nativo via Session State
    def resetar_filtros_callback():
        for k in ["b_rm", "f_req", "f_comp", "f_st_rm", "f_st_pc", "f_per", "b_pc"]:
            if k in st.session_state:
                st.session_state[k] = [] if k == "f_per" else "" if "b_" in k else "Todos"

    st.button("♻️ Limpar Filtros", on_click=resetar_filtros_callback, use_container_width=True)

# 2. Desenha a tabela em largura cheia e joga o botão de exportar para a col_btn_direita
renderizar_grid_multiindex_colorido(df_final, lista_ent, lista_nec, col_btn_direita)
