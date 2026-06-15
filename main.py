# main.py
import os
import shutil
from database.banco import salvar_itens_no_banco
from leituras.le_pdf_pedido import extrair_dados_pdf

# Importe o cliente do supabase configurado no seu projeto para fazermos a checagem rápida
# Se a sua conexão estiver em outro arquivo (ex: de app.py ou database/conexao.py), importe de lá
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def processar_pasta_pdf():
    """Localiza os PDFs, valida contra duplicados no Supabase e move para processados."""
    home_usuario = os.path.expanduser("~")
    
    caminho_pasta = os.path.join(
        home_usuario, 
        "OneDrive - ECOPARQUE BAIRROS INTEGRADOS LTDA", 
        "Suprimentos_Consolidado", 
        "pdf_pedido_compra"
    )

    if not os.path.exists(caminho_pasta):
        print(f"Pasta não encontrada no sistema: {caminho_pasta}")
        return

    # OBRIGATÓRIO (PASSO 1): Lê os arquivos locais ANTES de fazer qualquer print ou consulta
    arquivos = [f for f in os.listdir(caminho_pasta) if f.lower().endswith(".pdf")]
    
    if not arquivos:
        print(f"A pasta está vazia ou não contém novos arquivos PDF para processar.")
        return

    # PASSO 2: Agora que a variável 'arquivos' existe, faz a consulta de duplicidade
    print("Consultando registros já existentes no Supabase para evitar duplicidade...")
    try:
        # Tabela corrigida para 'pedido_compra'
        resposta_existentes = supabase.table("pedido_compra").select("rm, pedido, mat").execute()
        registros_existentes = {
            (item["rm"], item["pedido"], item["mat"]) 
            for item in resposta_existentes.data
        }
    except Exception as e:
        print(f"⚠️ Não foi possível consultar o histórico do banco de dados: {e}")
        registros_existentes = set()

    # PASSO 3: Executa o print informando a quantidade encontrada locais
    print(f"Iniciando processamento de {len(arquivos)} arquivos PDF...\n")

    todos_os_registros = []
    arquivos_lidos_com_sucesso = []
    pasta_processados = os.path.join(caminho_pasta, "processados")
    
    for arquivo in arquivos:
        caminho_completo = os.path.join(caminho_pasta, arquivo)
        
        try:
            itens_pdf = extrair_dados_pdf(caminho_completo)
            
            if itens_pdf:
                primeiro_item = itens_pdf[0]
                chave_item = (primeiro_item.get("rm"), primeiro_item.get("pedido"), primeiro_item.get("mat"))
                
                if chave_item in registros_existentes:
                    print(f"   ℹ️ [Ignorado]: Pedido {primeiro_item.get('pedido')} - RM {primeiro_item.get('rm')} já foi extraído anteriormente. Movendo arquivo...")
                    
                    if not os.path.exists(pasta_processados):
                        os.makedirs(pasta_processados)
                    destino = os.path.join(pasta_processados, arquivo)
                    if os.path.exists(destino):
                        os.remove(destino)
                    shutil.move(caminho_completo, destino)
                    continue

                todos_os_registros.extend(itens_pdf)
                arquivos_lidos_com_sucesso.append(arquivo)
                
                num_pedido = primeiro_item.get("pedido") if primeiro_item.get("pedido") else "N/A"
                num_rm = primeiro_item.get("rm") if primeiro_item.get("rm") else "N/A"
                cnpj_fornecedor = primeiro_item.get("cnpj") if primeiro_item.get("cnpj") else "N/A"
                codigos_materiais = sorted(list(set([str(item["mat"]) for item in itens_pdf])))
                lista_materiais = ", ".join(codigos_materiais)
                
                print(f"Pedido: {num_pedido} - RM {num_rm} - MAT {lista_materiais} - CNPJ: {cnpj_fornecedor}")
            else:
                print(f"   ⚠️ [Aviso]: Nenhum dado estruturado extraído de '{arquivo}'.")
                
        except Exception as e:
            print(f"   ❌ [Erro]: Falha ao interpretar '{arquivo}': {e}")
            continue

    if todos_os_registros:
        print(f"\nEnviando {len(todos_os_registros)} novas linhas para o Supabase...")
        try:
            salvar_itens_no_banco(todos_os_registros)
            print("✔️ Registros novos salvos com sucesso no Supabase!")
            
            if not os.path.exists(pasta_processados):
                os.makedirs(pasta_processados)
                
            print("\nOrganizando e movendo novos arquivos processados...")
            for arquivo in arquivos_lidos_com_sucesso:
                origem = os.path.join(caminho_pasta, arquivo)
                destino = os.path.join(pasta_processados, arquivo)
                if os.path.exists(destino):
                    os.remove(destino)
                shutil.move(origem, destino)
                
            print("\n🚀 Concluído! Pasta de leitura limpa com sucesso.")
            
        except Exception as erro_banco:
            print(f"❌ Erro crítico ao salvar dados no Supabase: {erro_banco}")
    else:
        print("\n[Aviso]: Nenhum arquivo novo para importar nesta rodada. Pasta limpa!")


if __name__ == "__main__":
    processar_pasta_pdf()
