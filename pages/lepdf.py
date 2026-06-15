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
    
# Verificação do st.session_state.logado:
if "id_upload" not in st.session_state:
    st.session_state.id_upload = 0

if "mostrar_tabela_resumo" not in st.session_state:
    st.session_state.mostrar_tabela_resumo = False
    st.session_state.dados_resumo = []
    
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

# 3. CAMPO DE UPLOAD NATIVO (Atualizado com chave dinâmica para reset)
arquivos_enviados = st.file_uploader(
    "Arraste os arquivos PDF aqui", 
    type=["pdf"], 
    accept_multiple_files=True,
    key=f"upload_pedidos_nuvem_{st.session_state.id_upload}"
)

if arquivos_enviados:
    st.metric(label="PDFs carregados para processamento", value=len(arquivos_enviados))
    
    if st.button("🚀 Iniciar Processamento dos PDFs", use_container_width=True):
        # Consulta de histórico no Supabase
        with st.spinner("Consultando registros existentes no Supabase..."):
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
                    if texto: texto_completo += texto + "\n"

                texto_completo = texto_completo.replace("\x00", "").replace("\x0c", "").replace("\r", "")
                
                # Regex de extração de metadados
                pedido_resultado = None
                padrao_pedido = re.search(r"pedido:\s*(\d+)", texto_completo, re.IGNORECASE)
                if padrao_pedido: pedido_resultado = int(padrao_pedido.group(1))

                rm_resultado = None
                padrao_rm = re.search(r"(\d+)\s*[rR]\s*[mM]", texto_completo)
                if padrao_rm: rm_resultado = int(padrao_rm.group(1))

                cnpj = None
                padrao_cnpj = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto_completo)
                if padrao_cnpj: cnpj = padrao_cnpj.group(0)

                emissao = None
                padrao_emissao = re.search(r"emiss.*:\s*(\d{2}/\d{2}/\d{4})", texto_completo, re.IGNORECASE)
                if padrao_emissao: emissao = converter_data(padrao_emissao.group(1))

                entrega = None
                padrao_entrega = re.search(r"entrega.*:\s*(\d{2}/\d{2}/\d{4})", texto_completo, re.IGNORECASE)
                if padrao_entrega: entrega = converter_data(padrao_entrega.group(1))

                observacao = None
                pos_obs = texto_completo.lower().find("observa")
                if pos_obs == -1: pos_obs = texto_completo.lower().find("complementar")
                if pos_obs != -1:
                    linhas_texto = texto_completo[pos_obs:].split("\n")
                    if linhas_texto: observacao = linhas_texto[0].strip()

                entregas_agendadas = []
                for parte in texto_completo.split():
                    if len(parte) == 10 and "/" in parte:
                        d_conv = converter_data(parte)
                        if d_conv and d_conv not in entregas_agendadas: entregas_agendadas.append(d_conv)

                # Varredura de itens da tabela
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
                    primeiro_item = itens_deste_pdf
                    chave_item = (primeiro_item["rm"], primeiro_item["pedido"], primeiro_item["mat"])
                    
                    if chave_item in registros_existentes:
                        arquivos_ignorados += 1
                        continue
                    
                    todos_os_registros.extend(itens_deste_pdf)
                    
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

        # Processamento do envio em bloco
        if todos_os_registros:
            try:
                salvar_itens_no_banco(todos_os_registros)
                
                # Guarda as informações do relatório na sessão antes de resetar a página
                st.session_state.mostrar_tabela_resumo = True
                st.session_state.dados_resumo = resumo_processamento
                st.session_state.total_linhas_importadas = len(todos_os_registros)
                st.session_state.total_arquivos_ignorados = arquivos_ignorados
                
                # --- TRAVA MÁGICA DE RESET ---
                # Incrementa o ID para forçar o Streamlit a recriar a caixa de upload vazia
                st.session_state.id_upload += 1
                st.rerun()
                
            except Exception as e:
                st.error(f"Erro crítico ao salvar no banco de dados: {e}")
        else:
            st.success("🎉 Todos os arquivos enviados já haviam sido importados anteriormente!")
            st.session_state.id_upload += 1
            st.rerun()

# --- EXIBIÇÃO PERSISTENTE DA TABELA DE RELATÓRIO PÓS-RESET ---
if st.session_state.mostrar_tabela_resumo:
    st.success(f"✔️ Sucesso! {st.session_state.total_linhas_importadas} novos itens cadastrados no banco de dados!")
    if st.session_state.total_arquivos_ignorados > 0:
        st.info(f"ℹ️ {st.session_state.total_arquivos_ignorados} arquivo(s) foram ignorados por já existirem no histórico.")
        
    st.subheader("📋 Relatório de Arquivos Processados Nesta Rodada")
    df_resumo = pd.DataFrame(st.session_state.dados_resumo)
    st.dataframe(df_resumo, use_container_width=True, hide_index=True)
    
    # Cria um botão opcional para limpar o histórico visual do relatório quando o usuário quiser
    if st.button("🧹 Limpar Relatório da Tela"):
        st.session_state.mostrar_tabela_resumo = False
        st.session_state.dados_resumo = []
        st.rerun()
