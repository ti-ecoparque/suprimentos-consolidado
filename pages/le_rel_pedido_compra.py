import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

# 1. CONFIGURAÇÃO E INTERFACE STREAMLIT
st.set_page_config(page_title="Upload de Pedidos", layout="wide")
st.title("📥 Upload de Pedidos de Compra (Supabase)")
st.write("Arraste e solte o relatório em formato Excel para realizar o tratamento e envio em lote.")

# 2. CONEXÃO COM O SUPABASE (Puxando dos Secrets do Streamlit ou .env)
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Erro: Credenciais do Supabase não configuradas.")
    st.stop()

# Inicializa o cliente do Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.divider()

# 3. ÁREA DE ARRASTAR E SOLTAR (DRAG AND DROP)
arquivo_postado = st.file_uploader(
    label="Arraste o arquivo Excel (.xlsx ou .xls) aqui", 
    type=["xlsx", "xls"],
    help="Selecione o relatório extraído com as colunas de pedidos."
)

# 4. PROCESSAMENTO DOS DADOS (Dispara assim que o arquivo é solto na tela)
if arquivo_postado is not None:
    st.info(f"📖 Arquivo detectado: **{arquivo_postado.name}**")
    
    with st.spinner("Lendo e tratando os dados do Excel..."):
        try:
            # O Pandas lê o arquivo direto da memória do Streamlit
            df_bruto = pd.read_excel(arquivo_postado)
            
            # MAP Excel | Mapeamento exato das colunas do seu arquivo
            mapeamento_colunas = {
                "Número do pedido": "pedido",
                "Nome Filial": "nome_filial",
                "Cód. Item": "mat",
                "Nr.Processo": "nr_processos",
                "Situação do Item": "situacao_pedido",
                "Nome Fantasia": "nome_fantasia",
                "Total Pedido Compra": "total_pedido",
                "Item Pedido": "item_pedido",
                "Descrição do Item": "desc_item",
                "Quantidade": "quantidade"
            }

            # Valida se todas as colunas mapeadas existem no arquivo Excel bruto
            colunas_faltantes = [col for col in mapeamento_colunas.keys() if col not in df_bruto.columns]
            
            if colunas_faltantes:
                st.error(f"❌ **Erro crítico:** As seguintes colunas não foram localizadas no Excel: `{colunas_faltantes}`")
                st.warning(f"Colunas encontradas no arquivo original: {df_bruto.columns.tolist()}")
                st.stop()

            # 1. Filtra mantendo apenas as colunas mapeadas
            df_filtrado = df_bruto[list(mapeamento_colunas.keys())].copy()

            # 2. Aplica os aliases definidos para corresponder ao banco
            df_filtrado = df_filtrado.rename(columns=mapeamento_colunas)

            # 3. Limpa linhas nulas nas chaves que compõem o UNIQUE (Regra de Negócio)
            # Alterado para 'any' para evitar que chaves vazias quebrem a constraint do banco
            df_filtrado = df_filtrado.dropna(subset=["pedido", "item_pedido", "mat"], how="any")

            # 4. Tratamento individual por tipo de dado (ALINHADO COM OS TIPOS DO BANCO)
            
            # Tratamento de TEXTO (Evita strings vazias ou nulas gerarem falhas)
            colunas_texto = ["nome_filial", "nr_processos", "situacao_pedido", "nome_fantasia", "desc_item"]
            for col in colunas_texto:
                df_filtrado[col] = df_filtrado[col].fillna("").astype(str).str.strip()

            # Tratamento de INTEIROS (Garante a compatibilidade com o tipo 'int4' do banco)
            # O campo 'mat' foi movido para cá para ser tratado corretamente como número inteiro
            colunas_inteiras = ["pedido", "item_pedido", "mat"]
            for col in colunas_inteiras:
                df_filtrado[col] = pd.to_numeric(df_filtrado[col], errors="coerce").fillna(0).astype(int)

            # Tratamento de DECIMAIS (Valores e quantidades float)
            df_filtrado["quantidade"] = pd.to_numeric(df_filtrado["quantidade"], errors="coerce").fillna(0.0).astype(float)
            df_filtrado["total_pedido"] = pd.to_numeric(df_filtrado["total_pedido"], errors="coerce").fillna(0.0).astype(float)

            # 5. Remoção de duplicadas local na memória
            total_antes = len(df_filtrado)
            df_filtrado = df_filtrado.drop_duplicates()
            total_depois = len(df_filtrado)
            
            if total_antes != total_depois:
                st.warning(f"🧹 **Remoção local:** {total_antes - total_depois} linhas duplicadas descartadas antes do envio.")

            # Transforma o DataFrame estruturado em uma lista de dicionários (JSON) para o Supabase
            dados_formatados = df_filtrado.to_dict(orient="records")

            if not dados_formatados:
                st.error("⚠️ Nenhum dado útil sobrou após o processo de limpeza (Dataframe Vazio).")
                st.stop()

            # Exibe uma prévia estruturada para validação visual do operador
            st.subheader("👀 Prévia dos Dados Tratados")
            st.dataframe(df_filtrado.head(10), use_container_width=True, hide_index=True)

            # 5. BOTÃO DE ENVIO E ATUALIZAÇÃO (UPSERT COMPATÍVEL COM A CONSTRAINT UNIQUE)
            if st.button("⚡ Enviar e Sincronizar com o Supabase", type="primary", use_container_width=True):
                with st.spinner(f"Processando upsert de {len(dados_formatados)} linhas na tabela..."):
                    
                    # O on_conflict aponta para a sua constraint 'unique_pedido_item_mat' do print
                    resposta = supabase.table("rel_pedido_compra").upsert(
                        dados_formatados,
                        on_conflict="pedido,item_pedido,mat"
                    ).execute()
                    
                    st.success(f"✔️ **Integração concluída!** {len(dados_formatados)} registros inseridos ou atualizados com sucesso.")
                    st.balloons()

        except Exception as e:
            st.error(f"❌ Ocorreu um erro durante o processamento do arquivo: {e}")
