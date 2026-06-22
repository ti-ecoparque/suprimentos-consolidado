# database/banco.py
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


def salvar_itens_no_banco(lista_itens):
    """Recebe uma lista de dicionários e realiza o upsert seguro na tabela 'pedido_compra'."""
    if not lista_itens:
        return None
        
    try:
        # 🚀 MUDANÇA CRUCIAL: Trocado .insert() por .upsert() com travas físicas de duplicados
        resposta = (
            supabase
            .table("pedido_compra")
            .upsert(
                lista_itens,
                on_conflict="rm,pedido,mat",  # Nome das colunas da sua restrição UNIQUE do banco
                ignore_duplicates=True        # Diz ao Postgres para pular e não duplicar se já existir
            )
            .execute()
        )
        
        print(f"✔️ Processamento de lote concluído no Supabase!")
        return resposta
        
    except Exception as e:
        print(f"Erro ao salvar dados no Supabase: {e}")
        raise e  # Repassa o erro para que o frontend st.error consiga capturar o log técnico
