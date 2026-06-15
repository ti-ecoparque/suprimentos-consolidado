import pandas as pd
import requests
import time

ARQUIVO_ENTRADA = "endereco.xlsx"
ARQUIVO_SAIDA = "enderecos_com_cep.xlsx"

def buscar_endereco(rua, cidade, uf):
    try:
        url = (
            f"https://viacep.com.br/ws/"
            f"{uf}/{cidade}/{rua}/json/"
        )
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            dados = response.json()
            if isinstance(dados, list) and len(dados) > 0:
                item = dados[0]
                endereco = item.get("logradouro", "")
                bairro = item.get("bairro", "")
                cidade = item.get("localidade", "")
                estado = item.get("uf", "")
                cep = item.get("cep", "")

                return {
                    "endereco": endereco,
                    "bairro": bairro,
                    "cidade": cidade,
                    "uf": estado,
                    "cep": cep
                }
    except Exception as e:
        print(f"❌ Erro ao consultar {rua}")
        print(e)
    return None
# LEITURA DA PLANILHA
df = pd.read_excel(
    ARQUIVO_ENTRADA,
    engine="openpyxl",
    header=None
)
df.columns = [
    "ENDERECO",
    "BAIRRO",
    "CEP",
    "CIDADE",
    "UF"
]
# Remove cabeçalho duplicado
df = df.iloc[1:].reset_index(drop=True)
# Remove NaN
df = df.fillna("")
# PROCESSAMENTO
TOTAL = len(df)
print(" INICIANDO CONSULTA DE CEPs ")
for i, row in df.iterrows():
    endereco_completo = str(row["ENDERECO"]).strip()
    # Remove número
    rua = endereco_completo.split(",")[0].strip()
    cidade = str(row["CIDADE"]).strip()
    uf = str(row["UF"]).strip()
    print(f"\n[{i+1}/{TOTAL}] Consultando:")
    print(f"Rua: {rua}")
    print(f"Cidade: {cidade}")
    print(f"UF: {uf}")
    resultado = buscar_endereco(
        rua,
        cidade,
        uf
    )
    if resultado:
        df.at[i, "BAIRRO"] = resultado["bairro"]
        df.at[i, "CEP"] = resultado["cep"]
        print("✅ ENCONTRADO")
        print(f"Endereço : {resultado['endereco']}")
        print(f"Bairro   : {resultado['bairro']}")
        print(f"Cidade   : {resultado['cidade']}")
        print(f"UF       : {resultado['uf']}")
        print(f"CEP      : {resultado['cep']}")
    else:
        print("❌ NÃO ENCONTRADO")
    # Evita bloqueio da API
    time.sleep(1)
# SALVAR PLANILHA
df.to_excel(
    ARQUIVO_SAIDA,
    index=False,
    engine="openpyxl"
)
print(" PLANILHA GERADA COM SUCESSO ")
