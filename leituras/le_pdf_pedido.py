import os
import re
from datetime import datetime
from pypdf import PdfReader


def converter_data(data_str):
    """
    Converte de dd/mm/yyyy para yyyy-mm-dd
    """
    try:
        data_limpa = data_str.strip()
        return datetime.strptime(data_limpa, "%d/%m/%Y").strftime("%Y-%m-%d")
    except:
        return None

def extrair_dados_pdf(caminho_do_arquivo):
    try:
        leitor = PdfReader(caminho_do_arquivo)
        texto_completo = ""

        for pagina in leitor.pages:
            texto = pagina.extract_text()
            if texto:
                texto_completo += texto + "\n"

        # Limpeza absoluta de caracteres invisíveis e nulos de controle de página
        texto_completo = texto_completo.replace("\x00", "").replace("\x0c", "").replace("", "")

        # 1. BUSCA PEDIDO
        pedido_resultado = None
        try:
            padrao_pedido = re.search(r"pedido:*(+)", texto_completo, re.IGNORECASE)
            if padrao_pedido:
                pedido_resultado = int(padrao_pedido.group(1))
        except:
            pedido_resultado = None

        # 2. BUSCA RM
        rm_resultado = None
        try:
            padrao_rm = re.search(r"(+)*[rR]*[mM]", texto_completo)
            if padrao_rm:
                rm_resultado = int(padrao_rm.group(1))
        except:
            rm_resultado = None

        # 3. BUSCA CNPJ
        cnpj = None
        try:
            padrao_cnpj = re.search(r"{2}\.{3}\.{3}/{4}-{2}", texto_completo)
            if padrao_cnpj:
                cnpj = padrao_cnpj.group(0)
        except:
            cnpj = None

        # 4. BUSCA DATAS
        emissao = None
        try:
            pos_emissao = texto_completo.lower().find("emiss")
            if pos_emissao != -1:
                trecho_data = texto_completo[pos_emissao:pos_emissao + 40]
                datas = re.findall(r"{2}/{2}/{4}", trecho_data)
                if datas:
                    emissao = converter_data(datas[0])
        except:
            emissao = None

        entrega = None
        try:
            pos_entrega = texto_completo.lower().find("entrega")
            if pos_entrega != -1:
                trecho_data = texto_completo[pos_entrega:pos_entrega + 40]
                datas = re.findall(r"{2}/{2}/{4}", trecho_data)
                if datas:
                    entrega = converter_data(datas[0])
        except:
            entrega = None

        # 5. BUSCA OBSERVAÇÃO
        observacao = None
        try:
            pos_obs = texto_completo.lower().find("observa")
            if pos_obs == -1:
                pos_obs = texto_completo.lower().find("complementar")
                
            if pos_obs != -1:
                linhas_texto = texto_completo[pos_obs:].split("\n")
                if linhas_texto:
                    observacao = linhas_texto[0].strip()
        except:
            observacao = None

        # 6. BUSCA ENTREGAS AGENDADAS
        entregas_agendadas = []
        try:
            for parte in texto_completo.split():
                if len(parte) == 10 and "/" in parte:
                    d_conv = converter_data(parte)
                    if d_conv and d_conv not in entregas_agendadas:
                        entregas_agendadas.append(d_conv)
        except:
            entregas_agendadas = []

        # 7. BUSCA ITENS DA TABELA
        linhas_extraidas = []
        linhas_do_pdf = texto_completo.split("\n")

        for linha in linhas_do_pdf:
            linha_limpa = linha.strip()
            if not linha_limpa:
                continue

            partes = [p for p in linha_limpa.split(" ") if p]
            
            if len(partes) >= 5:
                codigo_material = partes[0]
                
                if codigo_material.isdigit() and len(codigo_material) <= 9:
                    linhas_extraidas.append({
                        "rm": rm_resultado,
                        "pedido": pedido_resultado,
                        "mat": int(codigo_material),
                        "cnpj": str(cnpj) if cnpj else None,
                        "emissao": emissao,
                        "entrega": entrega,
                        "observacao": observacao,
                        "entregas_agendadas": entregas_agendadas
                    })

        return linhas_extraidas

    except Exception as e:
        print(f"Erro ao processar o arquivo {os.path.basename(caminho_do_arquivo)}: {e}")
        return []
