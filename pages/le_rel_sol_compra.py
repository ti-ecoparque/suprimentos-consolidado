import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

# 1. CONFIGURAÇÃO E INTERFACE STREAMLIT
st.title("📥 Upload de Solicitações de Compra (Supabase)")
st.write("Arraste e solte o relatório de Solicitação de Material para realizar o tratamento e sincronização.")

# 2. CONEXÃO COM O SUPABASE (Compatível com .env local ou Secrets do Streamlit Cloud)
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Erro: Credenciais do Supabase não configuradas corretamente.")
    st.stop()

# Inicializa o cliente do Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.divider()

# 3. ÁREA DE ARRASTAR E SOLTAR (DRAG AND DROP)
arquivo_postado = st.file_uploader(
    label="Arraste o arquivo Excel (.xlsx ou .xls) da Solicitação aqui", 
    type=["xlsx", "xls"],
    help="Selecione o relatório extraído com as colunas de solicitações/RM."
)

# 4. PROCESSAMENTO DOS DADOS (Ativado ao soltar o arquivo na tela)
if arquivo_postado is not None:
    st.info(f"📖 Arquivo detectado: **{arquivo_postado.name}**")
    
    with st.spinner("Processando e higienizando os dados da planilha..."):
        try:
            # O Pandas lê a planilha direto do buffer de memória do Streamlit
            df_bruto = pd.read_excel(arquivo_postado)
            
            # MAP Excel | Vinculação exata do seu modelo original
            mapeamento_colunas = {
                "Filial": "filial",
                "Nr. RM": "rm",
                "Nome Filial": "nome_filial",
                "Código da solicitação": "cod_solicitacao",
                "Sequencial do item": "seq_item",
                "Data de emissão": "data_emissao",
                "Situação do Item": "sit_item",
                "Código do item": "mat",
                "Descrição do item": "desc_item",
                "Quantidade solicitada": "qtd_solicitada",
                "Unidade": "unidade_medida",
                "Usuário solicitante": "usuario_solicitante",
                "Status da necessidade": "status_necessidade",
                "Código da cotação": "cod_cotacao"
            }

            # Valida se todas as colunas mapeadas existem no arquivo carregado
            colunas_faltantes = [col for col in mapeamento_colunas.keys() if col not in df_bruto.columns]
            if colunas_faltantes:
                st.error(f"❌ **Erro crítico:** Colunas obrigatórias ausentes no Excel: `{colunas_faltantes}`")
                st.warning(f"Estrutura identificada na planilha: {df_bruto.columns.tolist()}")
                st.stop()

            # 1. Isolamento das colunas necessárias
            df_filtrado = df_bruto[list(mapeamento_colunas.keys())].copy()

            # 2. Aplicação de aliases (Renomeação para o Banco)
            df_filtrado = df_filtrado.rename(columns=mapeamento_colunas)

            # 3. Limpeza de nulos nos campos que compõem a restrição de conflito (Chaves Únicas)
            df_filtrado = df_filtrado.dropna(subset=["rm", "seq_item", "mat"], how="any")

            # 4. Tratamento e padronização dos tipos de dados
            colunas_texto = [
                "filial", "rm", "nome_filial", "cod_solicitacao", 
                "sit_item", "mat", "desc_item", "unidade_medida", 
                "usuario_solicitante", "status_necessidade", "cod_cotacao"
            ]
            for coluna in colunas_texto:
                df_filtrado[coluna] = df_filtrado[coluna].fillna("").astype(str).str.strip()

            # Número Inteiro (Sequencial)
            df_filtrado["seq_item"] = pd.to_numeric(df_filtrado["seq_item"], errors="coerce").fillna(0).astype(int)
            
            # Decimal (Quantidade)
            df_filtrado["qtd_solicitada"] = pd.to_numeric(df_filtrado["qtd_solicitada"], errors="coerce").fillna(0.0).astype(float)
            
            # Formatação de Data Nativa para o Formato ISO do PostgreSQL (YYYY-MM-DD)
            df_filtrado["data_emissao"] = pd.to_datetime(df_filtrado["data_emissao"], errors="coerce").dt.strftime("%Y-%m-%d")

            # 5. Descarte de duplicidades idênticas em memória
            total_antes = len(df_filtrado)
            df_filtrado = df_filtrado.drop_duplicates()
            total_depois = len(df_filtrado)
            
            if total_antes != total_depois:
                st.warning(f"🧹 **Remoção local:** {total_antes - total_depois} registros duplicados foram ignorados.")

            # Converte a matriz tratada em dicionário estruturado JSON
            dados_formatados = df_filtrado.to_dict(orient="records")

            if not dados_formatados:
                st.error("⚠️ O processo de higienização resultou em zero linhas válidas.")
                st.stop()

            # Exibição do Grid de conferência para validação visual do operador
            st.subheader("👀 Visualização Prévia dos Dados Tratados")
            st.dataframe(df_filtrado.head(15), use_container_width=True)

            # 5. BOTÃO DE CONFIRMAÇÃO DE GRAVAÇÃO (Evita disparos acidentais)
            # Alinhado com a tabela 'rel_solicitacao_compras' e sua respectiva constraint de chave do banco
            if st.button("⚡ Sincronizar Solicitações no Supabase", type="primary", use_container_width=True):
                with st.spinner(f"Executando Upsert de {len(dados_formatados)} itens em lote..."):
                    
                    resposta = supabase.table("rel_solicitacao_compras").upsert(
                        dados_formatados,
                        on_conflict="rm,seq_item,mat"
                    ).execute()
                    
                    st.success(f"✔️ **Integração efetuada com sucesso!** {len(dados_formatados)} linhas adicionadas/atualizadas.")
                    st.balloons()
                    
                    # Opcional: exibe o log de resposta bruta do banco em modo oculto
                    with st.expander("Ver log técnico de resposta"):
                        st.write(resposta)

        except Exception as e:
            st.error(f"❌ Falha operacional durante a execução da rotina: {e}")
