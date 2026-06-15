# pages/LePDF.py
import os
import shutil
import streamlit as st
import pandas as pd
from leituras.le_pdf_pedido import extrair_dados_pdf
from database.banco import salvar_itens_no_banco
from supabase import create_client

# 1. VALIDAÇÃO DE SEGURANÇA: Impede acesso direto pela URL sem login
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("🔒 Acesso restrito. Por favor, faça login na página principal.")
    if st.button("Ir para o Login"):
        st.switch_page("app.py")
    st.stop()

# 2. CONEXÃO COM O SUPABASE (Lê dos Secrets configurados na nuvem ou local)
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.header("🔄 Área Administrativa - Integrador de Pedidos")
st.write(f"👤 Conectado como: **{st.session_state.usuario_atual}**")
st.divider()

# 3. MAPEIA O CAMINHO LOCAL DO ONEDRIVE
home_usuario = os.path.expanduser("~")
caminho_pasta = os.path.join(
    home_usuario, 
    "OneDrive - ECOPARQUE BAIRROS INTEGRADOS LTDA", 
    "Suprimentos_Consolidado", 
    "pdf_pedido_compra"
)

if not os.path.exists(caminho_pasta):
    st.error(f"❌ Pasta não localizada no sistema. Execute o arquivo 'Criar_Pastas.bat' primeiro.\nCaminho esperado: {caminho_pasta}")
    st.stop()

# Lista os arquivos locais
arquivos = [f for f in os.listdir(caminho_pasta) if f.lower().endswith(".pdf")]

col1, col2 = st.columns(2)
with col1:
    st.info(f"📂 **Diretório ativo:** `{caminho_pasta}`")
with col2:
    st.metric(label="Novos PDFs pendentes", value=len(arquivos))

# Botão disparador da leitura
if st.button("🚀 Iniciar Processamento dos PDFs", use_container_width=True):
    if not arquivos:
        st.warning("Nenhum arquivo PDF novo foi encontrado na pasta de leitura.")
        st.stop()

    # Carrega o histórico para evitar duplicados
    with st.spinner("Consultando registros existentes para evitar duplicidade..."):
        try:
            resposta_existentes = supabase.table("pedido_compra").select("rm, pedido, mat").execute()
            registros_existentes = {(item["rm"], item["pedido"], item["mat"]) for item in resposta_existentes.data}
        except Exception as e:
            st.error(f"Erro ao consultar o histórico: {e}")
            st.stop()

    todos_os_registros = []
    arquivos_lidos_com_sucesso = []
    pasta_processados = os.path.join(caminho_pasta, "processados")
    
    progresso = st.progress(0, text="Analisando arquivos...")
     
    for idx, arquivo in enumerate(arquivos):
        caminho_completo = os.path.join(caminho_pasta, arquivo)
        progresso.progress((idx + 1) / len(arquivos), text=f"Lendo: {arquivo}")
        
        try:
            itens_pdf = extrair_dados_pdf(caminho_completo)
            if itens_pdf:
                primeiro_item = itens_pdf[0]
                chave_item = (primeiro_item.get("rm"), primeiro_item.get("pedido"), primeiro_item.get("mat"))
                
                if chave_item in registros_existentes:
                    if not os.path.exists(pasta_processados): 
                        os.makedirs(pasta_processados)
                    destino = os.path.join(pasta_processados, arquivo)
                    if os.path.exists(destino): 
                        os.remove(destino)
                    shutil.move(caminho_completo, destino)
                    continue

                todos_os_registros.extend(itens_pdf)
                arquivos_lidos_com_sucesso.append(arquivo)
        except:
            continue

    if todos_os_registros:
        with st.spinner(f"Enviando {len(todos_os_registros)} linhas para o Supabase..."):
            try:
                salvar_itens_no_banco(todos_os_registros)
                
                # Move os arquivos para processados
                if not os.path.exists(pasta_processados): 
                    os.makedirs(pasta_processados)
                for arquivo in arquivos_lidos_com_sucesso:
                    origem = os.path.join(caminho_pasta, arquivo)
                    destino = os.path.join(pasta_processados, arquivo)
                    if os.path.exists(destino): 
                        os.remove(destino)
                    shutil.move(origem, destino)
                    
                st.success(f"✔️ {len(todos_os_registros)} linhas importadas e arquivos organizados com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro crítico ao salvar no banco de dados: {e}")
    else:
        st.success("🎉 Todos os arquivos da pasta já tinham sido importados anteriormente! Pasta organizada.")
        st.rerun()
