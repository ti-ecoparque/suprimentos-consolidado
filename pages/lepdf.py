# pages/lepdf.py
import os
import re
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from database.banco import salvar_itens_no_banco
from supabase import create_client
from datetime import datetime

# 1. VALIDAÇÃO DE SEGURANÇA
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("🔒 Acesso restrito. Por favor, faça login na página principal.")
    if st.button("Ir para o Login"):
        st.switch_page("app.py")
    st.stop()

def converter_data(data_str):
    """Converte de dd/mm/yyyy para yyyy-mm-dd"""
    try:
        data_limpa = data_str.strip()
        return datetime.strptime(data_limpa, "%d/%m/%Y").strftime("%Y-%m-%d")
    except:
        return None

# 2. CONEXÃO COM O SUPABASE
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.header("🔄 Área Administrativa - Integrador de Pedidos")
st.write(f"👤 Conectado como: **{st.session_state.usuario_atual}**")
st.divider()

st.write("📌 **Instruções:** Selecione ou arraste um ou mais arquivos PDF de pedidos de compra diretamente para o campo abaixo para realizar a importação automática para o banco de dados.")

# 3. CAMPO DE UPLOAD NATIVO
arquivos_enviados = st.file_uploader(
    "Arraste os arquivos PDF aqui", 
    type=["pdf"], 
    accept_multiple_files=True,
    key="upload_pedidos_nuvem"
)

if arquivos_enviados:
    st.metric(label="PDFs carregados para processamento", value=len(arquivos_enviados))
    
    if st.button("🚀 Iniciar Processamento dos PDFs", use_container_width=True):
        # Carrega o histórico do Supabase para evitar duplicados
        with st.spinner("Consultando registros existentes no Supabase para evitar duplicidade..."):
            try:
                resposta_existentes = supabase.table("pedido_compra").select("rm, pedido, mat").execute()
                registros_existentes = {(item["rm"], item["pedido"], item["mat"]) for item in resposta_existentes.data}
            except Exception as e:
                st.error(f"Erro ao consultar o histórico do banco: {e}")
                st.stop()

        todos_os_registros = []
        resumo_processamento = []
        arquivos_ignorados = 0
        
        progresso = st.progress(0, text="Analisando arquivos...")
        
        for idx, arquivo_buffer in enumerate(arquivos_enviados):
            progresso.progress((idx + 1) / len(arquivos_enviados), text=f"Processando: {arquivo_buffer.name}")
            
            try:
                leitor = PdfReader(arquivo_buffer)
                texto_completo = ""
                for pagina in leitor.pages:
                    texto = pagina.extract_text()
                    if texto:
                        texto_completo += texto + "\n"

                texto_completo = texto_completo.replace("\x00", "").replace("\x0c", "").replace("\r", "")
                
                # --- EXTRAÇÃO DE CABEÇALHOS (RESTAURADA E CORRIGIDA) ---
                pedido_resultado = None
                padrao_pedido = re.search(r"pedido:\s*(\d+)", texto_completo, re.IGNORECASE)
                if padrao_pedido: pedido_resultado = int(padrao_pedido.group(1))

                rm_resultado = None
                padrao_rm = re.search(r"(\d+)\s*[rR]\s*[mM]", texto_completo)
                if padrao_rm: rm_resultado = int(padrao_rm.group(1))

                cnpj = None
                padrao_cnpj = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto_completo)
                if padrao_cnpj: cnpj = padrao_cnpj.group(0)

                # Captura de Datas (Emissão e Entrega)
                emissao = None
                padrao_emissao = re.search(r"emiss.*:\s*(\d{2}/\d{2}/\d{4})", texto_completo, re.IGNORECASE)
                if padrao_emissao: emissao = converter_data(padrao_emissao.group(1))

                entrega = None
                padrao_entrega = re.search(r"entrega.*:\s*(\d{2}/\d{2}/\d{4})", texto_completo, re.IGNORECASE)
                if padrao_entrega: entrega = converter_data(padrao_entrega.group(1))

                # Captura de Observação
                observacao = None
                pos_obs = texto_completo.lower().find("observa")
                if pos_obs == -1: pos_obs = texto_completo.lower().find("complementar")
                if pos_obs != -1:
                    linhas_texto = texto_completo[pos_obs:].split("\n")
                    if linhas_texto: observacao = linhas_texto[0].strip()

                # Captura de Entregas Agendadas
                entregas_agendadas = []
                for parte in texto_completo.split():
                    if len(parte) == 10 and "/" in parte:
                        d_conv = converter_data(parte)
                        if d_conv and d_conv not in entregas_agendadas:
                            entregas_agendadas.append(d_conv)

                # --- VARREDURA DE ITENS ---
                linhas_do_pdf = texto_completo.split("\n")
                itens_deste_pdf = []
                codigos_materiais = []
                
                for linha in linhas_do_pdf:
                    linha_limpa = linha.strip()
                    if not linha_limpa: continue
                    partes = [p for p in linha_limpa.split(" ") if p]
                    
                    if len(partes) >= 5:
                        codigo_material = partes[0]
                        if codigo_material.isdigit() and len(codigo_material) <= 9:
                            codigos_materiais.append(codigo_material)
                            itens_deste_pdf.append({
                                "rm": rm_resultado,
                                "pedido": pedido_resultado,
                                "mat": int(codigo_material),
                                "cnpj": str(cnpj) if cnpj else None,
                                "emissao": emissao,
                                "entrega": entrega,
                                "observacao": observacao,
                                "entregas_agendadas": entregas_agendadas
                            })

                if itens_deste_pdf:
                    primeiro_item = itens_deste_pdf[0]
                    chave_item = (primeiro_item["rm"], primeiro_item["pedido"], primeiro_item["mat"])
                    
                    # Se já existe no banco, ignora e pula pro próximo PDF
                    if chave_item in registros_existentes:
                        arquivos_ignorados += 1
                        continue
                    
                    todos_os_registros.extend(itens_deste_pdf)
                    
                    # Guarda os dados para a lista visual de sucesso na tela
                    resumo_processamento.append({
                        "Pedido": pedido_resultado if pedido_resultado else "N/A",
                        "RM": rm_resultado if rm_resultado else "N/A",
                        "Materiais": ", ".join(sorted(list(set(codigos_materiais)))),
                        "CNPJ Fornecedor": cnpj if cnpj else "N/A",
                        "Status": "Importado"
                    })
            except Exception as e:
                st.error(f"⚠️ Falha ao ler o arquivo {arquivo_buffer.name}: {e}")
                continue

        # Envio em bloco para o Supabase
        if todos_os_registros:
            with st.spinner(f"Enviando {len(todos_os_registros)} linhas para o Supabase..."):
                try:
                    salvar_itens_no_banco(todos_os_registros)
                    st.success(f"✔️ Sucesso! {len(todos_os_registros)} novos itens cadastrados no banco de dados!")
                    
                    if arquivos_ignorados > 0:
                        st.info(f"ℹ️ {arquivos_ignorados} arquivo(s) foram ignorados por já existirem no histórico.")
                    
                    # --- NOVO: EXIBIÇÃO EM TABELA DOS DADOS SUBIDOS ---
                    st.subheader("📋 Relatório de Arquivos Processados Nesta Rodada")
                    df_resumo = pd.DataFrame(resumo_processamento)
                    st.dataframe(df_resumo, use_container_width=True, hide_index=True)
                    
                except Exception as e:
                    st.error(f"Erro crítico ao salvar no banco de dados: {e}")
        else:
            st.success("🎉 Todos os arquivos enviados já haviam sido importados anteriormente no Supabase!")
