import os
import re
import streamlit as st
import pandas as pd
from pypdf import PdfReader
from database.banco import salvar_itens_no_banco, supabase
from datetime import datetime

# ==============================================================================
# 1. VALIDAÇÃO DE SEGURANÇA E ACESSO
# ==============================================================================
if "logado" not in st.session_state or not st.session_state.logado:
    st.warning("🔒 Acesso restrito. Por favor, faça login na página principal.")
    if st.button("Ir para o Login", key="btn_redirect_login"):
        st.switch_page("app.py")
    st.stop()


# ==============================================================================
# 2. FUNÇÕES UTILIÁRIAS E DE EXTRAÇÃO (REFATORADO)
# ==============================================================================
def converter_data(data_str):
    """Converte datas de dd/mm/yyyy para yyyy-mm-dd para o banco de dados."""
    try:
        data_limpa = data_str.strip()
        return datetime.strptime(data_limpa, "%d/%m/%Y").strftime("%Y-%m-%d")
    except:
        return None


def extrair_texto_pdf(arquivo_buffer) -> str:
    """Lê as páginas do PDF e limpa caracteres de controle nulos e quebras brutas."""
    leitor = PdfReader(arquivo_buffer)
    texto_completo = ""
    for pagina in leitor.pages:
        texto = pagina.extract_text()
        if texto:
            texto_completo += texto + "\n"
    
    # Limpeza de caracteres nulos e quebras do leitor de PDF
    return texto_completo.replace("\x00", "").replace("\x0c", "").replace("\r", "")


def extrair_dados_cabecalho_e_metadados(texto_completo: str) -> dict:
    """Aplica padrões Regex para coletar metadados estruturais do pedido."""
    metadados = {}

    # 1. Extração do Pedido
    padrao_pedido = re.search(r"pedido:\s*(\d+)", texto_completo, re.IGNORECASE)
    metadados["pedido"] = int(padrao_pedido.group(1)) if padrao_pedido else None

    # 2. Extração de Múltiplas RMs (Procura especificamente no bloco final do documento)
    lista_rms = []
    padrao_bloco_rm = re.search(r"RMs?:\s*([\d\s,;-]+)", texto_completo, re.IGNORECASE)
    if padrao_bloco_rm:
        lista_rms = [int(rm) for rm in re.findall(r"\d+", padrao_bloco_rm.group(1))]
    
    if not lista_rms:
        padrao_rm_antigo = re.search(r"(\d+)\s*[rR]\s*[mM]", texto_completo)
        if padrao_rm_antigo: 
            lista_rms = [int(padrao_rm_antigo.group(1))]
        else:
            lista_rms = [None]
    metadados["lista_rms"] = lista_rms

    # 3. Extração de CNPJ, Comprador e Observações
    padrao_cnpj = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto_completo)
    metadados["cnpj"] = padrao_cnpj.group(0) if padrao_cnpj else None

    padrao_comprador = re.search(r"Comprador:\s*(.+)", texto_completo, re.IGNORECASE)
    metadados["comprador"] = padrao_comprador.group(1).strip() if padrao_comprador else None

    observacao = None
    pos_obs = texto_completo.lower().find("observa")
    if pos_obs == -1: 
        pos_obs = texto_completo.lower().find("complementar")
    if pos_obs != -1:
        linhas_texto = texto_completo[pos_obs:].split("\n")
        if linhas_texto: 
            observacao = linhas_texto[0].strip()
    metadados["observacao"] = observacao

    # 4. Extração de Datas
    padrao_dt_entrega = re.search(r"Dt\.\s*Entrega\s*:\s*(\d{2}/\d{2}/\d{4})", texto_completo, re.IGNORECASE)
    metadados["dt_entrega_cabecalho"] = converter_data(padrao_dt_entrega.group(1)) if padrao_dt_entrega else None

    padrao_emissao = re.search(r"emiss.*:\s*(\d{2}/\d{2}/\d{4})", texto_completo, re.IGNORECASE)
    metadados["emissao"] = converter_data(padrao_emissao.group(1)) if padrao_emissao else None

    padrao_entrega = re.search(r"entrega.*:\s*(\d{2}/\d{2}/\d{4})", texto_completo, re.IGNORECASE)
    metadados["entrega"] = converter_data(padrao_entrega.group(1)) if padrao_entrega else None

    entregas_agendadas = []
    datas_encontradas = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", texto_completo)
    for data_str in datas_encontradas:
        d_conv = converter_data(data_str)
        if d_conv and d_conv not in entregas_agendadas: 
            entregas_agendadas.append(d_conv)
    metadados["entregas_agendadas"] = entregas_agendadas

    return metadados


def extrair_itens_materiais(texto_completo: str, meta: dict, todos_registros_lista: list, mapa_materiais_controle: dict):
    """Varre as linhas de tabela do PDF e vincula os itens a cada RM encontrada."""
    linhas_do_pdf = texto_completo.split("\n")
    pedido = meta["pedido"]

    if pedido not in mapa_materiais_controle:
        mapa_materiais_controle[pedido] = set()

    for linha in linhas_do_pdf:
        linha_limpa = linha.strip()
        if not linha_limpa: 
            continue
        partes = [p for p in linha_limpa.split(" ") if p]
        
        if len(partes) >= 5:
            # ✔ CORREÇÃO: Adicionado o índice [0] para pegar estritamente a primeira coluna de texto
            codigo_material = partes[0]
            
            if codigo_material.isdigit() and len(codigo_material) <= 9:
                mat_int = int(codigo_material)
                mapa_materiais_controle[pedido].add(str(mat_int))
                
                for rm_atual in meta["lista_rms"]:
                    todos_registros_lista.append({
                        "rm": rm_atual,
                        "pedido": pedido,
                        "mat": mat_int,
                        "cnpj": str(meta["cnpj"]) if meta["cnpj"] else None,
                        "emissao": meta["emissao"],
                        "entrega": meta["entrega"],
                        "entrega_cabecalho": meta["dt_entrega_cabecalho"],    
                        "comprador": meta["comprador"],                       
                        "observacao": meta["observacao"],
                        "entregas_agendadas": meta["entregas_agendadas"]
                    })

# ==============================================================================
# 3. ESTADOS DE SESSÃO PERSISTENTES DO STREAMLIT
# ==============================================================================
if "id_upload" not in st.session_state:
    st.session_state.id_upload = 0

if "mostrar_tabela_resumo" not in st.session_state:
    st.session_state.mostrar_tabela_resumo = False
    st.session_state.dados_validos = []
    st.session_state.dados_ignorados = []
    st.session_state.total_linhas_importadas = 0
    st.session_state.mensagem_tipo = ""


# ==============================================================================
# 4. INTERFACE GRÁFICA DO USUÁRIO (UI)
# ==============================================================================
st.header("🔄 Área Administrativa - Integrador de Pedidos")
st.write(f"👤 Conectado como: **{st.session_state.usuario_atual}**")
st.divider()

st.write("📌 **Instruções:** Selecione ou arraste um ou mais arquivos PDF de pedidos de compra diretamente para o campo abaixo para realizar a importação automática para o banco de dados.")

arquivos_enviados = st.file_uploader(
    "Arraste os arquivos PDF aqui", 
    type=["pdf"], 
    accept_multiple_files=True,
    key=f"upload_pedidos_nuvem_{st.session_state.id_upload}"
)


# ==============================================================================
# 5. FLUXO DE EXECUÇÃO PRINCIPAL
# ==============================================================================
if arquivos_enviados:
    st.metric(label="PDFs carregados para processamento", value=len(arquivos_enviados))
    
    if st.button("🚀 Iniciar Processamento dos PDFs", use_container_width=True, key="btn_processar_pdfs"):
        
        todos_os_registros = []
        mapa_cnpjs = {}
        todos_os_pedidos_lidos = set()
        mapa_pedido_rm = {}
        mapa_pedido_materiais = {}
        
        progresso = st.progress(0, text="Analisando arquivos...")
        
        # --- ETAPA 1: FLUXO DE EXTRAÇÃO EM MEMÓRIA ---
        for idx, arquivo_buffer in enumerate(arquivos_enviados):
            progresso.progress((idx + 1) / len(arquivos_enviados), text=f"Processando: {arquivo_buffer.name}")
            
            try:
                # Executa as funções modulares isoladas
                texto_extraido = extrair_texto_pdf(arquivo_buffer)
                metadados_pdf = extrair_dados_cabecalho_e_metadados(texto_extraido)
                
                pedido_id = metadados_pdf["pedido"]
                if pedido_id:
                    todos_os_pedidos_lidos.add(pedido_id)
                    if metadados_pdf["cnpj"]: 
                        mapa_cnpjs[pedido_id] = metadados_pdf["cnpj"]
                    mapa_pedido_rm[pedido_id] = metadados_pdf["lista_rms"]

                # Processa e gera as linhas estruturadas de materiais vinculados
                extrair_itens_materiais(texto_extraido, metadados_pdf, todos_os_registros, mapa_pedido_materiais)
                    
            except Exception as e:
                st.error(f"⚠️ Falha ao ler os dados do arquivo {arquivo_buffer.name}: {e}")
                continue
        # --- ETAPA 2: DISPARO EM LOTE ÚNICO E SEPARAÇÃO DE VÁLIDOS VS IGNORADOS ---
        if todos_os_registros:
            try:
                resposta = salvar_itens_no_banco(todos_os_registros)
                dados_inseridos_reais = resposta.data if (resposta and resposta.data) else []
                linhas_inseridas = len(dados_inseridos_reais)
                
                st.session_state.mostrar_tabela_resumo = True
                st.session_state.total_linhas_importadas = linhas_inseridas
                
                combinacoes_inseridas_reais = set()
                resumo_validos = []
                
                if linhas_inseridas > 0:
                    st.session_state.mensagem_tipo = "sucesso"
                    df_retorno = pd.DataFrame(dados_inseridos_reais)
                    
                    # dropna=False assegura que chaves com RMs nulas não sejam excluídas pelo Pandas [1]
                    for (ped, rm_num), sub_df in df_retorno.groupby(["pedido", "rm"], dropna=False):
                        ped_int = int(ped)
                        rm_int = int(rm_num) if pd.notnull(rm_num) else None
                        
                        combinacoes_inseridas_reais.add((ped_int, rm_int))
                        
                        materiais_lista = sorted(list(set(sub_df["mat"].astype(str).tolist())))
                        rm_exibicao = rm_int if rm_int is not None else "N/A"
                        
                        resumo_validos.append({
                            "Pedido": ped_int,
                            "RM": rm_exibicao,
                            "Materiais": ", ".join(materiais_lista),
                            "CNPJ Fornecedor": mapa_cnpjs.get(ped_int, "N/A"),
                            "Status": "Processado e Salvo"
                        })
                else:
                    st.session_state.mensagem_tipo = "tudo_duplicado"
                
                # Valida individualmente se cada combinação gerada no lote foi salva ou rejeitada pelo banco
                resumo_ignorados = []
                for ped_lido in todos_os_pedidos_lidos:
                    rms_deste_pedido = mapa_pedido_rm.get(ped_lido, [None])
                    
                    for rm_lida in rms_deste_pedido:
                        if (ped_lido, rm_lida) not in combinacoes_inseridas_reais:
                            materiais_rejeitados = sorted(list(mapa_pedido_materiais.get(ped_lido, set())))
                            if not materiais_rejeitados: 
                                materiais_rejeitados = ["N/A"]
                                
                            rm_exibicao = rm_lida if rm_lida is not None else "N/A"
                            
                            resumo_ignorados.append({
                                "Pedido": ped_lido,
                                "RM": rm_exibicao,
                                "Materiais Rejeitados": ", ".join(materiais_rejeitados),
                                "CNPJ Fornecedor": mapa_cnpjs.get(ped_lido, "N/A"),
                                "Status": "Ignorado (Já Existe)"
                            })
                
                st.session_state.dados_validos = resumo_validos
                st.session_state.dados_ignorados = resumo_ignorados
                    
            except Exception as error_banco:
                st.error(f"❌ Erro operacional com o Supabase: {error_banco}")
        else:
            st.warning("Nenhum dado pôde ser extraído dos arquivos anexados.")


# ==============================================================================
# 6. EXIBIÇÃO DETALHADA DOS RELATÓRIOS NA TELA (UI INFERIOR)
# ==============================================================================
if st.session_state.get("mostrar_tabela_resumo"):
    st.divider()
    
    if st.session_state.mensagem_tipo == "sucesso":
        st.success(f"✔ Processamento concluído! **{st.session_state.total_linhas_importadas}** novos registros de materiais foram sincronizados!")
    elif st.session_state.mensagem_tipo == "tudo_duplicado":
        st.warning("⚠ Operação concluída: Todos os pedidos enviados já existiam no banco de dados.")

    # 🟢 TABELA 1: VÁLIDOS
    if st.session_state.get("dados_validos"):
        st.subheader("📋 Relatório de Arquivos Processados Nesta Rodada (Válidos)")
        df_validos = pd.DataFrame(st.session_state.dados_validos)
        st.dataframe(df_validos, use_container_width=True, hide_index=True)

    # 🟡 TABELA 2: IGNORADOS (DUPLICADOS)
    if st.session_state.get("dados_ignorados"):
        st.subheader("🚨 Relatório de Pedidos Bloqueados (Já Existentes / Ignorados)")
        df_ignorados = pd.DataFrame(st.session_state.dados_ignorados)
        st.dataframe(df_ignorados, use_container_width=True, hide_index=True)

    # Botão de reset completo da visualização
    if st.button("🧹 Limpar Histórico do Terminal / Mensagens", key="btn_limpar_historico"):
        st.session_state.mostrar_tabela_resumo = False
        st.session_state.dados_validos = []
        st.session_state.dados_ignorados = []
        st.session_state.total_linhas_importadas = 0
        st.session_state.id_upload += 1  
        st.rerun()