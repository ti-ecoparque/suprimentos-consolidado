# pages/lepdf.py
import os
import re
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from database.banco import salvar_itens_no_banco, supabase
from datetime import datetime

# 1. VALIDAÇÃO DE SEGURANÇA
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("🔒 Acesso restrito. Por favor, faça login na página principal.")
    if st.button("Ir para o Login", key="btn_redirect_login"):
        st.switch_page("app.py")
    st.stop()

def converter_data(data_str):
    """Converte de dd/mm/yyyy para yyyy-mm-dd"""
    try:
        data_limpa = data_str.strip()
        return datetime.strptime(data_limpa, "%d/%m/%Y").strftime("%Y-%m-%d")
    except:
        return None

# --- INICIALIZAÇÃO DE VARIÁVEIS DE SESSÃO PERSISTENTES ---
if "id_upload" not in st.session_state:
    st.session_state.id_upload = 0

if "mostrar_tabela_resumo" not in st.session_state:
    st.session_state.mostrar_tabela_resumo = False
    st.session_state.dados_resumo = []
    st.session_state.total_linhas_importadas = 0
    st.session_state.mensagem_tipo = ""

st.header("🔄 Área Administrativa - Integrador de Pedidos")
st.write(f"👤 Conectado como: **{st.session_state.usuario_atual}**")
st.divider()

st.write("📌 **Instruções:** Selecione ou arraste um ou mais arquivos PDF de pedidos de compra diretamente para o campo abaixo para realizar a importação automática para o banco de dados.")

# 3. CAMPO DE UPLOAD NATIVO
arquivos_enviados = st.file_uploader(
    "Arraste os arquivos PDF aqui", 
    type=["pdf"], 
    accept_multiple_files=True,
    key=f"upload_pedidos_nuvem_{st.session_state.id_upload}"
)

if arquivos_enviados:
    st.metric(label="PDFs carregados para processamento", value=len(arquivos_enviados))
    
    if st.button("🚀 Iniciar Processamento dos PDFs", use_container_width=True, key="btn_processar_pdfs"):
        
        todos_os_registros = []
        resumo_processamento = []
        
        progresso = st.progress(0, text="Analisando arquivos...")
        
        # --- LOOP ÚNICO DE EXTRAÇÃO EM MEMÓRIA ---
        for idx, arquivo_buffer in enumerate(arquivos_enviados):
            progresso.progress((idx + 1) / len(arquivos_enviados), text=f"Processando: {arquivo_buffer.name}")
            
            try:
                leitor = PdfReader(arquivo_buffer)
                texto_completo = ""
                for pagina in leitor.pages:
                    texto = pagina.extract_text()
                    if texto: texto_completo += texto + "\n"

                texto_completo = texto_completo.replace("\x00", "").replace("\x0c", "").replace("\r", "")
                
                # Regex de extração de cabeçalhos
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

                # Varredura das linhas de itens do arquivo atual
                linhas_do_pdf = texto_completo.split("\n")
                codigos_materiais_novos = []
                
                for linha in linhas_do_pdf:
                    linha_limpa = linha.strip()
                    if not linha_limpa: continue
                    partes = [p for p in linha_limpa.split(" ") if p]
                    
                    if len(partes) >= 5:
                        codigo_material = partes[0]
                        if codigo_material.isdigit() and len(codigo_material) <= 9:
                            mat_int = int(codigo_material)
                            
                            codigos_materiais_novos.append(codigo_material)
                            todos_os_registros.append({
                                "rm": rm_resultado,
                                "pedido": pedido_resultado,
                                "mat": mat_int,
                                "cnpj": str(cnpj) if cnpj else None,
                                "emissao": emissao,
                                "entrega": entrega,
                                "observacao": observacao,
                                "entregas_agendadas": entregas_agendadas
                            })

                # Monta a prévia da linha para a tabela mesmo antes do envio
                resumo_processamento.append({
                    "Pedido": pedido_resultado if pedido_resultado else "N/A",
                    "RM": rm_resultado if rm_resultado else "N/A",
                    "Materiais": ", ".join(sorted(list(set(codigos_materiais_novos)))),
                    "CNPJ Fornecedor": cnpj if cnpj else "N/A",
                    "Status": "Processado"
                })
                    
            except Exception as e:
                st.error(f"⚠️ Falha ao ler o arquivo {arquivo_buffer.name}: {e}")
                continue

        # --- DISPARO EM LOTE ÚNICO COM TRAVA DE RETORNO DO UPSERT ---
        if todos_os_registros:
            try:
                resposta = salvar_itens_no_banco(todos_os_registros)
                linhas_inseridas = len(resposta.data) if (resposta and resposta.data) else 0
                
                st.session_state.mostrar_tabela_resumo = True
                st.session_state.dados_resumo = resumo_processamento
                st.session_state.total_linhas_importadas = linhas_inseridas
                
                if linhas_inseridas > 0:
                    st.session_state.mensagem_tipo = "sucesso"
                else:
                    st.session_state.mensagem_tipo = "tudo_duplicado"
                    
            except Exception as error_banco:
                st.error(f"❌ Erro operacional com o Supabase: {error_banco}")
        else:
            st.warning("Nenhum dado pôde ser extraído dos arquivos anexados.")
            
        # ❌ REMOVIDO: st.rerun() daqui de dentro para não fazer a tela piscar e sumir os dados

# --- 4. EXIBIÇÃO HISTÓRICA DO RELATÓRIO ---
if st.session_state.get("mostrar_tabela_resumo"):
    st.divider()
    
    if st.session_state.mensagem_tipo == "sucesso":
        st.success(f"✔ Processamento concluído! **{st.session_state.total_linhas_importadas}** novos registros foram sincronizados com sucesso!")
    elif st.session_state.mensagem_tipo == "tudo_duplicado":
        st.warning("⚠ Operação concluída: Todos os pedidos enviados já existiam no banco e foram ignorados para evitar duplicidade.")

    st.subheader("📋 Relatório de Arquivos Processados Nesta Rodada")
    df_resumo = pd.DataFrame(st.session_state.dados_resumo)
    st.dataframe(df_resumo, use_container_width=True, hide_index=True)

    if st.button("🧹 Limpar Histórico do Terminal / Mensagens", key="btn_limpar_historico"):
        st.session_state.mostrar_tabela_resumo = False
        st.session_state.dados_resumo = []
        st.session_state.total_linhas_importadas = 0
        st.session_state.id_upload += 1  # Reseta o file_uploader da tela limpando os arquivos antigos
        st.rerun()
