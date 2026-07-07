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
    st.session_state.dados_validos = []
    st.session_state.dados_ignorados = []
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
        mapa_cnpjs = {}
        todos_os_pedidos_lidos = set()
        mapa_pedido_rm = {}
        mapa_pedido_materiais = {}
        
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

                if pedido_resultado:
                    todos_os_pedidos_lidos.add(pedido_resultado)
                    if cnpj: mapa_cnpjs[pedido_resultado] = cnpj
                    if rm_resultado: mapa_pedido_rm[pedido_resultado] = rm_resultado

                # Captura o Comprador (Pega tudo após 'Comprador:' até o final da linha)
                comprador = None
                padrao_comprador = re.search(r"Comprador:\s*(.+)", texto_completo, re.IGNORECASE)
                if padrao_comprador: 
                    comprador = padrao_comprador.group(1).strip()

                # Captura estrita da Dt. Entrega que fica no cabeçalho do Fornecedor
                dt_entrega_cabecalho = None
                padrao_dt_entrega = re.search(r"Dt\.\s*Entrega\s*:\s*(\d{2}/\d{2}/\d{4})", texto_completo, re.IGNORECASE)
                if padrao_dt_entrega: 
                    dt_entrega_cabecalho = converter_data(padrao_dt_entrega.group(1))
                
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
                
                if pedido_resultado not in mapa_pedido_materiais:
                    mapa_pedido_materiais[pedido_resultado] = set()

                for linha in linhas_do_pdf:
                    linha_limpa = linha.strip()
                    if not linha_limpa: continue
                    partes = [p for p in linha_limpa.split(" ") if p]
                    
                    if len(partes) >= 5:
                        codigo_material = partes[0]
                        if codigo_material.isdigit() and len(codigo_material) <= 9:
                            mat_int = int(codigo_material)
                            mapa_pedido_materiais[pedido_resultado].add(str(mat_int))
                            
                            todos_os_registros.append({
                                "rm": rm_resultado,
                                "pedido": pedido_resultado,
                                "mat": mat_int,
                                "cnpj": str(cnpj) if cnpj else None,
                                "emissao": emissao,
                                "entrega": entrega,
                                "entrega_cabecalho": dt_entrega_cabecalho,    
                                "comprador": comprador,                       
                                "observacao": observacao,
                                "entregas_agendadas": entregas_agendadas
                            })
                    
            except Exception as e:
                st.error(f"⚠️ Falha ao ler o arquivo {arquivo_buffer.name}: {e}")
                continue

        # --- DISPARO EM LOTE ÚNICO E SEPARAÇÃO DE VÁLIDOS VS IGNORADOS ---
        if todos_os_registros:
            try:
                resposta = salvar_itens_no_banco(todos_os_registros)
                dados_inseridos_reais = resposta.data if (resposta and resposta.data) else []
                linhas_inseridas = len(dados_inseridos_reais)
                
                st.session_state.mostrar_tabela_resumo = True
                st.session_state.total_linhas_importadas = linhas_inseridas
                
                # Identifica quais pedidos foram aceitos pelo banco de dados
                pedidos_inseridos_reais = set()
                resumo_validos = []
                
                if linhas_inseridas > 0:
                    st.session_state.mensagem_tipo = "sucesso"
                    df_retorno = pd.DataFrame(dados_inseridos_reais)
                    
                    # Agrupa o retorno real do banco por pedido e RM
                    for (ped, rm_num), sub_df in df_retorno.groupby(["pedido", "rm"]):
                        ped_int = int(ped)
                        pedidos_inseridos_reais.add(ped_int)
                        materiais_lista = sorted(list(set(sub_df["mat"].astype(str).tolist())))
                        
                        resumo_validos.append({
                            "Pedido": ped_int,
                            "RM": int(rm_num),
                            "Materiais": ", ".join(materiais_lista), # ✔ Corrigido!
                            "CNPJ Fornecedor": mapa_cnpjs.get(ped_int, "N/A"),
                            "Status": "Processado e Salvo"
                        })
                else:
                    st.session_state.mensagem_tipo = "tudo_duplicado"
                
                # Descobre quais pedidos foram completamente ignorados (estavam lidos mas não foram inseridos)
                pedidos_ignorados_reais = todos_os_pedidos_lidos - pedidos_inseridos_reais
                resumo_ignorados = []
                
                for ped_img in pedidos_ignorados_reais:
                    materiais_rejeitados = sorted(list(mapa_pedido_materiais.get(ped_img, ["N/A"])))
                    resumo_ignorados.append({
                        "Pedido": ped_img,
                        "RM": mapa_pedido_rm.get(ped_img, "N/A"),
                        "Materiais Rejeitados": ", ".join(materiais_rejeitados),
                        "CNPJ Fornecedor": mapa_cnpjs.get(ped_img, "N/A"),
                        "Status": "Ignorado (Já Existe)"
                    })
                
                st.session_state.dados_validos = resumo_validos
                st.session_state.dados_ignorados = resumo_ignorados
                    
            except Exception as error_banco:
                st.error(f"❌ Erro operacional com o Supabase: {error_banco}")
        else:
            st.warning("Nenhum data pôde ser extraído dos arquivos anexados.")

# --- 4. EXIBIÇÃO DETALHADA DOS DOIS RELATÓRIOS FIXADOS NA TELA ---
if st.session_state.get("mostrar_tabela_resumo"):
    st.divider()
    
    # Exibe o alerta principal de status do lote
    if st.session_state.mensagem_tipo == "sucesso":
        st.success(f"✔ Processamento concluído! **{st.session_state.total_linhas_importadas}** novos registros de materiais foram sincronizados!")
    elif st.session_state.mensagem_tipo == "tudo_duplicado":
        st.warning("⚠ Operação concluída: Todos os pedidos enviados já existiam no banco de dados.")

    # 🟢 TABELA 1: EXIBE OS VALIDOS DESTA RODADA
    if st.session_state.get("dados_validos"):
        st.subheader("📋 Relatório de Arquivos Processados Nesta Rodada (Válidos)")
        df_validos = pd.DataFrame(st.session_state.dados_validos)
        st.dataframe(df_validos, use_container_width=True, hide_index=True)

    # 🟡 TABELA 2: EXIBE OS IGNORADOS DA RODADA (DUPLICADOS)
    if st.session_state.get("dados_ignorados"):
        st.subheader("🚨 Relatório de Pedidos Bloqueados (Já Existentes / Ignorados)")
        df_ignorados = pd.DataFrame(st.session_state.dados_ignorados)
        st.dataframe(df_ignorados, use_container_width=True, hide_index=True)

    # Botão de reset para limpar a tela e liberar para o próximo lote
    if st.button("🧹 Limpar Histórico do Terminal / Mensagens", key="btn_limpar_historico"):
        st.session_state.mostrar_tabela_resumo = False
        st.session_state.dados_validos = []
        st.session_state.dados_ignorados = []
        st.session_state.total_linhas_importadas = 0
        st.session_state.id_upload += 1  # Reseta o campo file_uploader limpando a caixa cinza
        st.rerun()

