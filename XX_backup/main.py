import os
from database.banco import salvar_itens_no_banco
from Leituras.le_pdf_pedido import extrair_dados_pdf

def processar_pasta_pdf():
    """Localiza a pasta do OneDrive dinamicamente e processa todos os PDFs."""
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

    # Lista todos os arquivos .pdf da pasta
    arquivos = [f for f in os.listdir(caminho_pasta) if f.lower().endswith(".pdf")]
    
    if not arquivos:
        print(f"A pasta está vazia ou não contém arquivos PDF.")
        return

    print(f"Iniciando processamento de {len(arquivos)} arquivos PDF...\n")

    todos_os_registros = []
    
    for arquivo in arquivos:
        caminho_completo = os.path.join(caminho_pasta, arquivo)
        print(f"Lendo: {arquivo}...")
        
        # Chama a função importada do outro arquivo
        itens_pdf = extrair_dados_pdf(caminho_completo)
        if itens_pdf:
            todos_os_registros.extend(itens_pdf)

    # Envia todos os dados coletados para o módulo do banco
    if todos_os_registros:
        print(f"\nEnviando {len(todos_os_registros)} linhas para o Supabase...")
        salvar_itens_no_banco(todos_os_registros)
    else:
        print("\n[Aviso]: Nenhum dado válido foi extraído dos arquivos PDF.")

if __name__ == "__main__":
    processar_pasta_pdf()
