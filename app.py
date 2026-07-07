# app.py
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

# 1. CONFIGURAÇÃO DA PÁGINA (OBRIGATORIAMENTE O PRIMEIRO COMANDO)
st.set_page_config(
    page_title="Consolidado Pedidos/RM",
    layout="wide"
)

# --- FUNÇÃO DO CONTEÚDO DA HOME (PROTEGIDA) ---
def renderizar_painel_principal():
    """Toda a lógica e busca que antes ficava solta no app.py agora fica protegida aqui dentro"""
    from cenarios.cenario_a import renderizar_cenario_a
    from cenarios.cenario_b import renderizar_cenario_b
    from cenarios.cenario_c import renderizar_cenario_c
    from cenarios.cenario_d import renderizar_cenario_d

    load_dotenv()

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    st.header("Consulta de Pedidos e RMs")
    st.divider()

    if "pedido" not in st.session_state: st.session_state.pedido = ""
    if "rm" not in st.session_state: st.session_state.rm = ""
    if "periodo" not in st.session_state: st.session_state.periodo = []
    if "filtro_status_cenario_c" not in st.session_state: st.session_state.filtro_status_cenario_c = ["NAO ATENDIDO", "PARCIAL"]

    def limpar_filtros():
        st.session_state.pedido = ""
        st.session_state.rm = ""
        st.session_state.periodo = []
        st.session_state.filtro_status_cenario_c = ["NAO ATENDIDO", "PARCIAL"]

    def Skinner_status(valor):
        if valor in ['ATENDIDO', 'Pedido Atendido']:
            return 'background-color: #e6f4ea; color: #137333; font-weight: bold;'
        elif valor == 'ATENDIDO COM EXCEDENTE':
            return 'background-color: #e8f0fe; color: #1a73e8; font-weight: bold;'
        elif valor == 'PARCIAL':
            return 'background-color: #fef7e0; color: #b06000; font-weight: bold;'
        elif valor in ['NAO ATENDIDO', 'Cancelado']:
            return 'background-color: #fce8e6; color: #c5221f; font-weight: bold;'
        return ''

    if os.path.exists("style.css"):
        with open("style.css", "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    with st.form("formulario_busca"):
        col1, col2, col3 = st.columns(3)
        with col1:
            pedido = st.text_input("Número do Pedido", key="pedido")
        with col2:
            rm = st.text_input("Número da RM", key="rm")
        with col3:
            periodo = st.date_input("RMs por Período (Opcional)", value=[], key="periodo", format="DD/MM/YYYY")
        
        status_selecionados = st.multiselect(
            "Filtrar Status da RM (Apenas para busca por período)",
            options=["NAO ATENDIDO", "PARCIAL", "ATENDIDO", "ATENDIDO COM EXCEDENTE"],
            default=["NAO ATENDIDO", "PARCIAL"],
            key="filtro_status_cenario_c"
        )
        buscar = st.form_submit_button("🔍 Executar Busca")

    st.button("🧹 Limpar Filtros", on_click=limpar_filtros)

    if buscar:
        if not rm and not pedido and not periodo:
            st.warning("Informe um Pedido, uma RM ou selecione um Período.")
            st.stop()
            
        pedidos = []
        rm_para_conferencia = ""
        
        if rm:
            try:
                rm_int = int(rm)
                rm_para_conferencia = str(rm_int)
            except ValueError:
                st.error("RM inválida.")
                st.stop()

            resposta_pedido = supabase.table("pedido_compra").select("pedido").eq("rm", rm_int).execute()
            dados_pedido = resposta_pedido.data
            if dados_pedido:
                pedidos = list(set([item.get("pedido") for item in dados_pedido if item.get("pedido") is not None]))
            else:
                st.warning("Requisição de Material não gerou pedido de compra.")
                st.stop()

        if pedido:
            try:
                pedido_int = int(pedido)
                if pedido_int not in pedidos:
                    pedidos.append(pedido_int)
                
                if not rm_para_conferencia:
                    resposta_rm_pedido = supabase.table("pedido_compra").select("rm").eq("pedido", pedido_int).limit(1).execute()
                    if resposta_rm_pedido.data and len(resposta_rm_pedido.data) > 0:
                        rm_para_conferencia = str(resposta_rm_pedido.data[0].get("rm", ""))
            except ValueError:
                st.error("Pedido inválido.")
                st.stop()
            
        pedidos = list(set(pedidos))

        if pedido and pedidos:
            renderizar_cenario_a(pedido, pedidos, rm_para_conferencia, supabase, Skinner_status)
        elif rm_para_conferencia:
            renderizar_cenario_b(rm_para_conferencia, pedidos, supabase, Skinner_status)
        elif periodo:
            renderizar_cenario_c(periodo, status_selecionados, supabase, Skinner_status)
        else:
            renderizar_cenario_d()    


# --- 2. CONFIGURAÇÃO DE NAVEGAÇÃO E SUCESSO DO MENU ---
pagina_painel = st.Page(renderizar_painel_principal, title="Painel Principal", icon="📊", default=True)
pagina_pedido = st.Page("pages/le_rel_pedido_compra.py", title="Pedidos de Compra", icon="📦")
pagina_solicitacao = st.Page("pages/le_rel_sol_compra.py", title="Solicitações de Compra", icon="📥")
pagina_lepdf = st.Page("pages/lepdf.py", title="Integrador LePDF", icon="📂")
pagina_approvo = st.Page("cenarios/cenario_d.py", title="Approvo Status", icon="✅")

pg = st.navigation([pagina_painel, pagina_pedido, pagina_solicitacao, pagina_lepdf, pagina_approvo])


# --- 3. SISTEMA DE AUTO-LOGIN SEGURO NATIVO (À PROVA DE F5) ---
if "logado" not in st.session_state:
    st.session_state.logado = False

# O Streamlit guarda parâmetros nativamente na URL da aba ativa. 
# Se der F5, o Python lê essa chave e loga sozinho, sem quebrar ou dar delay!
if not st.session_state.logado:
    usuario_salvo = st.query_params.get("u") # Lê o parâmetro 'u' da URL
    if usuario_salvo:
        lista_usuarios = st.secrets["usuarios"]
        if usuario_salvo in lista_usuarios:
            st.session_state.logado = True
            st.session_state.usuario_atual = usuario_salvo
            st.rerun()

def realizar_login(email_input, senha_input, lembrar_usuario):
    lista_usuarios = st.secrets["usuarios"]
    if email_input in lista_usuarios and lista_usuarios[email_input] == senha_input:
        st.session_state.logado = True
        st.session_state.usuario_atual = email_input
        
        if lembrar_usuario:
            # Grava na URL de forma estável. Resiste a F5 e atualizações!
            st.query_params["u"] = email_input
            
        st.rerun()
    else:
        st.error("E-mail ou senha incorretos. Tente novamente.")

# Bloqueio de Acesso Restrito
if not st.session_state.logado:
    st.markdown("<h2 style='text-align: center;'>🔒 Acesso Restrito - Suprimentos</h2>", unsafe_allow_html=True)
    with st.form("form_login", clear_on_submit=False):
        st.write("Insira suas credenciais corporativas para acessar o painel:")
        email_usuario = st.text_input("E-mail")
        senha_usuario = st.text_input("Senha", type="password")
        lembrar = st.checkbox("Manter-me conectado neste computador (Salvar sessão)")
        botao_entrar = st.form_submit_button("Entrar no Painel")
        if botao_entrar:
            realizar_login(email_usuario, senha_usuario, lembrar)
            
    st.stop()


# --- 4. BARRA LATERAL E LOGOUT ---
with st.sidebar:
    st.write(f"👤 Conectado como: **{st.session_state.usuario_atual}**")
    st.divider()
    if st.button("🚪 Sair do Sistema", use_container_width=True, key="btn_logout_sidebar_definitivo"):
        st.session_state.logado = False
        st.query_params.clear() # Deleta a chave da URL ao deslogar por segurança
        st.rerun()

# Executa as páginas normais do sistema de forma limpa
pg.run()
