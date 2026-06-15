import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Inicializa o cliente do Supabase
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Erro: SUPABASE_URL ou SUPABASE_KEY não configurados no arquivo .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

#Recebe uma lista de dicionários e insere na tabela 'pedidos_materiais' do Supabase.
def salvar_itens_no_banco(lista_itens):
    if not lista_itens:
        return
    try:
        # Realiza o insert em lote (bulk insert) para maior performance
        resposta = supabase.table("pedido_compra").insert(lista_itens).execute()
        print(f"✔️ {len(lista_itens)} registros salvos com sucesso no Supabase!")
        return resposta
    except Exception as e:
        print(f"Erro ao salvar dados no Supabase: {e}")
