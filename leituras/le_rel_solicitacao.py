import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Configurações SUPABASE_URL ou SUPABASE_KEY não encontradas no arquivo .env")

# 2. Inicializa o cliente de conexão com o Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def localizar_arquivo_excel(pasta):
    """Varre a pasta e retorna o caminho do primeiro arquivo Excel (.xls ou .xlsx) encontrado."""
    if not os.path.exists(pasta):
        print(f"Pasta não encontrada: {pasta}")
        return None

    arquivos = [f for f in os.listdir(pasta) if f.lower().endswith(('.xlsx', '.xls'))]
    
    if not arquivos:
        print(f"Nenhum arquivo Excel (.xls ou .xlsx) foi achado na pasta: {pasta}")
        return None
    return os.path.join(pasta, arquivos[0])

def processar_e_salvar_dados():
    # Caminho dinâmico para a pasta na raiz do projeto
    diretorio_atual = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
    pasta_origem = os.path.join(diretorio_atual, "xls_solicitacao")
    caminho_excel = localizar_arquivo_excel(pasta_origem)
    if not caminho_excel:
        return
    print(f"📖 Lendo arquivo: {os.path.basename(caminho_excel)}...")
    try:
        df_bruto = pd.read_excel(caminho_excel)
        # MAP Excel | Apenas as Colunas Novas do Banco de Dados
        mapeamento_colunas = {
            "Filial": "filial",
            "Nr. RM": "rm",
            "Nome Filial": "nome_filial",
            "Código da solicitação" : "cod_solicitacao",
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
        # Valida se todas as colunas mapeadas existem no arquivo Excel bruto
        colunas_faltantes = [col for col in mapeamento_colunas.keys() if col not in df_bruto.columns]
        if colunas_faltantes:
            print(f"Erro crítico: As seguintes colunas não foram localizadas no Excel: {colunas_faltantes}")
            print(f"Colunas reais disponíveis no arquivo: {df_bruto.columns.tolist()}")
            return
        print("Isolando, renomeando e tratando as colunas selecionadas...")
        # 1. Filtra mantendo apenas as colunas mapeadas
        df_filtrado = df_bruto[list(mapeamento_colunas.keys())].copy()
        # 2. Aplica os aliases definidos para corresponder ao banco
        df_filtrado = df_filtrado.rename(columns=mapeamento_colunas)
        # 3 ??? 
        # 4. Trata e limpa o texto de todas as colunas
        colunas_texto = [
            "filial",
            "rm",
            "nome_filial",
            "cod_solicitacao",
            "sit_item",
            "mat",
            "desc_item",
            "unidade_medida",
            "usuario_solicitante",
            "status_necessidade",
            "cod_cotacao"
        ]
        for coluna in colunas_texto:
            df_filtrado[coluna] = (
                df_filtrado[coluna]
                .fillna("")
                .astype(str)
                .str.strip()
            )
        # Número inteiro
        df_filtrado["seq_item"] = pd.to_numeric(
            df_filtrado["seq_item"],
            errors="coerce"
        )
        # Decimal
        df_filtrado["qtd_solicitada"] = pd.to_numeric(
            df_filtrado["qtd_solicitada"],
            errors="coerce"
        )
        # Data
        df_filtrado["data_emissao"] = pd.to_datetime(
            df_filtrado["data_emissao"],
            errors="coerce"
        ).dt.strftime("%Y-%m-%d")

        # 5. Remoção de duplicadas local na memória
        total_antes = len(df_filtrado)
        df_filtrado = df_filtrado.drop_duplicates()
        total_depois = len(df_filtrado)
        
        if total_antes != total_depois:
            print(f"🧹 Remoção local: {total_antes - total_depois} linhas duplicadas foram descartadas do Excel.")

        # Transforma o DataFrame estruturado em uma lista de dicionários para o Supabase
        dados_formatados = df_filtrado.to_dict(orient="records")

        if not dados_formatados:
            print("Nenhum dado útil sobrou após o processo de limpeza.")
            return
        print(f"Enviando {len(dados_formatados)} linhas para a tabela 'rel_solicitacao_compra' no Supabase...")
        
        # Executa o insert em lote (bulk insert)
        
        resposta = supabase.table("rel_solicitacao_compras").upsert(
            dados_formatados,
            on_conflict="rm,seq_item,mat"
        ).execute()
        print(resposta)
        print("✔️ Integração concluída! Dados salvos com sucesso.")    
        
    except Exception as e:
        print(f"Ocorreu um erro durante o processamento: {e}")

if __name__ == "__main__":
    processar_e_salvar_dados()