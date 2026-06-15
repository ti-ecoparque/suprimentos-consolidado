import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Consolidado Pedidos/RM",
    layout="wide"
)
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

st.header("Consulta de Pedidos e RMs")
st.divider()

def limpar_filtros():
    st.session_state.pedido = ""
    st.session_state.rm = ""
    st.session_state.periodo = []
    st.session_state.filtro_status_cenario_c = ["NAO ATENDIDO", "PARCIAL"]

# FUNÇÃO DE COR SUTIL PARA O STATUS
def Skinner_status(valor):
    if valor in ['ATENDIDO', 'Pedido Atendido']:
        return 'background-color: #e6f4ea; color: #137333; font-weight: bold;'
    elif valor == 'ATENDIDO COM EXCEDENTE':
        return 'background-color: #e8f0fe; color: #1a73e8; font-weight: bold;'
    elif valor == 'PARCIAL':
        return 'background-color: #fef7e0; color: #b06000; font-weight: bold;'
    elif valor in ['NAO ATENDIDO', 'Cancelado']:
        return 'background-color: #fce8e6; color: #c5221f; font-weight: bold;'
    return ''

def carregar_css(caminho_arquivo):
    if os.path.exists(caminho_arquivo):
        with open(caminho_arquivo, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
carregar_css("style.css")

#FORMULÁRIO DE FILTROS (CORRIGIDO: Contém o botão de submit obrigatório)
with st.form("formulario_busca"):
    col1, col2, col3 = st.columns(3)

    with col1:
        pedido = st.text_input("Número do Pedido", key="pedido")

    with col2:
        rm = st.text_input("Número da RM", key="rm")

    with col3:
        # CORRIGIDO: Removido o parâmetro 'shortcuts' incompatível
        periodo = st.date_input(
            "RMs por Período (Opcional)", 
            value=[], 
            key="periodo",
            format="DD/MM/YYYY"
        )

    status_selecionados = st.multiselect(
        "Filtrar Status da RM (Apenas para busca por período)",
        options=["NAO ATENDIDO", "PARCIAL", "ATENDIDO", "ATENDIDO COM EXCEDENTE"],
        default=["NAO ATENDIDO", "PARCIAL"],
        key="filtro_status_cenario_c"
    )

    # GARANTIDO: Botão de envio fixado obrigatoriamente dentro do escopo do formulário
    buscar = st.form_submit_button("🔍 Executar Busca")

# Botão de limpar isolado abaixo
st.button("🧹 Limpar Filtros", on_click=limpar_filtros)

# PROCESSAMENTO DA CONSULTA PRINCIPAL
if buscar:

    if not rm and not pedido and not periodo:
        st.warning("Informe um Pedido, uma RM ou selecione um Período.")
        st.stop()
        
    pedidos = []
    rm_para_conferencia = ""
    
    # 1. MAPEAMENTO DE RELACIONAMENTOS
    if rm:
        try:
            rm_int = int(rm)
            rm_para_conferencia = str(rm_int)
        except ValueError:
            st.error("RM inválida.")
            st.stop()

        resposta_pedido = (
            supabase
            .table("pedido_compra")
            .select("pedido")
            .eq("rm", rm_int)
            .execute()
        )
        dados_pedido = resposta_pedido.data
        if dados_pedido:
            pedidos = list(set([item.get("pedido") for item in dados_pedido if item.get("pedido") is not None]))
        else:
            st.warning("Requisição de Material não gerou pedido de compra.")
            st.stop()

    if pedido:
        try:
            pedido_int = int(pedido)
            if pedido_int not in pedidos:
                pedidos.append(pedido_int)
            
            if not rm_para_conferencia:
                resposta_rm_pedido = (
                    supabase
                    .table("pedido_compra")
                    .select("rm")
                    .eq("pedido", pedido_int)
                    .limit(1)
                    .execute()
                )
                # Acessa o índice [0] antes de dar o .get(), pois o retorno é uma lista
                if resposta_rm_pedido.data and len(resposta_rm_pedido.data) > 0:
                    rm_para_conferencia = str(resposta_rm_pedido.data[0].get("rm", ""))
        except ValueError:
            st.error("Pedido inválido.")
            st.stop()
        
    pedidos = list(set(pedidos))

    # CENÁRIO A: BUSCA POR PEDIDO (DADOS UNIFICADOS DOS ITENS)
    if pedido and pedidos:
        resposta_itens = (
            supabase
            .table("vw_pedidos")
            .select("*")
            .in_("pedido", pedidos)
            .execute()
        )
        dados_itens = resposta_itens.data
        
        if not dados_itens:
            st.warning(f"Pedido {pedido} não possui itens cadastrados.")
            st.stop()
            
        df = pd.DataFrame(dados_itens)
        df.columns = df.columns.str.lower()
        
        colunas_seguras = [c for c in ["pedido", "mat", "quantidade", "desc_item", "nome_fantasia", "cnpj", "total_pedido"] if c in df.columns]
        df = df.drop_duplicates(subset=colunas_seguras).copy()
        
        for col in ["pedido", "quantidade", "mat"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
                
        for col_data in ["emissao", "entrega"]:
            if col_data in df.columns:
                df[col_data] = pd.to_datetime(df[col_data], errors="coerce").dt.strftime("%d/%m/%Y")
                
        if "total_pedido" in df.columns:
            df["total_pedido"] = pd.to_numeric(df["total_pedido"], errors="coerce").fillna(0)
            df["total_pedido"] = df["total_pedido"].map(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            df["total_pedido"] = df["total_pedido"].where(~df.duplicated(subset=["pedido"]), "")
                
        st.success(f"Pedido {pedido} encontrado com {len(df)} itens")
        
        # Acesso seguro usando o .iloc do Pandas
        nome_filial = df["nome_filial"].iloc[0] if "nome_filial" in df.columns and not df.empty else ""
        data_consulta = pd.Timestamp.now().strftime("%d/%m/%Y %H:%M")
        
        inf_col1, inf_col2, inf_col3, inf_col4 = st.columns(4)
        with inf_col1:
            st.markdown(f"**RM:** {rm_para_conferencia}")
        with inf_col2:
            st.markdown(f"**Pedido:** {pedido}")
        with inf_col3:
            st.markdown(f"**Filial:** {nome_filial}")
        with inf_col4:
            st.markdown(f"**Data da Consulta:** {data_consulta}")
            
        st.divider()
        
        df_visual = df.rename(columns={
            "pedido": "Pedido",
            "mat": "Material",
            "desc_item": "Descrição",
            "quantidade": "Qtd Solicitada",
            "emissao": "Emissão",
            "entrega": "Entrega",
            "situacao_pedido": "Status",
            "nome_fantasia": "Fornecedor",
            "cnpj": "CNPJ",
            "total_pedido": "Valor Total"
        })
        
        colunas_final = ["Pedido", "Material", "Descrição", "Qtd Solicitada", "Emissão", "Entrega", "Valor Total", "Fornecedor", "CNPJ", "Status"]
        colunas_validas = [c for c in colunas_final if c in df_visual.columns]
        df_filtrado = df_visual[colunas_validas].copy()
        
        if "Material" in df_filtrado.columns:
            df_filtrado = df_filtrado.sort_values(by="Material")
            
        st.dataframe(
            df_filtrado.style.map(Skinner_status, subset=['Status']), 
            use_container_width=True, 
            hide_index=True
        )

    # CENÁRIO B: BUSCA POR RM
    elif rm_para_conferencia:
        resposta_conferencia = (
            supabase
            .table("vw_conferencia_rm")
            .select("*")
            .eq("rm", rm_para_conferencia)
            .execute()
        )
        dados_conferencia = resposta_conferencia.data
        
        if dados_conferencia:
            df_conf = pd.DataFrame(dados_conferencia)
            
            qtd_pedidos = len(pedidos)
            st.success(f"RM {rm_para_conferencia} gerou {qtd_pedidos} pedido(s)")
            
            # Remove decimais de colunas numéricas
            for col_qtd in ["qtd_solicitada", "qtd_comprada", "mat"]:
                if col_qtd in df_conf.columns:
                    df_conf[col_qtd] = pd.to_numeric(df_conf[col_qtd], errors="coerce").fillna(0).astype(int)
            
            # Trata a coluna pedido separadamente para aceitar nulos (None)
            if "pedido" in df_conf.columns:
                df_conf["pedido"] = pd.to_numeric(df_conf["pedido"], errors="coerce").astype("Int64")

            # Renomeia as colunas para exibição na tabela
            df_conf.rename(
                columns={
                    "pedido": "Pedido",
                    "mat": "Material",
                    "desc_item": "Descrição",
                    "qtd_solicitada": "Qtd Solicitada",
                    "qtd_comprada": "Qtd Comprada",
                    "status_atendimento": "Status"
                },
                inplace=True
            )
            
            # Garante a ordem correta das colunas
            colunas_desejadas = ["Pedido", "Material", "Descrição", "Qtd Solicitada", "Qtd Comprada", "Status"]
            colunas_validas = [col for col in colunas_desejadas if col in df_conf.columns]
            
            df_filtrado_rm = df_conf[colunas_validas]
            
            # Renderiza a tabela de RM na tela
            st.dataframe(
                df_filtrado_rm.style.map(Skinner_status, subset=['Status']), 
                use_container_width=True, 
                hide_index=True
            )
    #CENÁRIO C: RMs POR PERÍODO E STATUS SELECIONADOS (CORRIGIDO)
    elif periodo:
        if len(periodo) != 2:
            st.warning("Por favor, selecione as duas datas (Início e Fim) no calendário.")
            st.stop()
            
        if not status_selecionados:
            st.warning("Por favor, marque ao menos um Status antes de processar.")
            st.stop()
            
        # Extração correta acessando os índices [0] e [1] do objeto de intervalo do Streamlit
        data_inicio = periodo[0].strftime("%Y-%m-%d")
        data_fim = periodo[1].strftime("%Y-%m-%d")
        
        # Realiza a busca utilizando o operador de lotes dinâmicos .in_
        resposta_periodo = (
            supabase
            .table("vw_conferencia_rm")
            .select("*")
            .gte("data_emissao", data_inicio)
            .lte("data_emissao", data_fim)
            .in_("status_atendimento", status_selecionados)
            .execute()
        )
        dados_periodo = resposta_periodo.data
        
        if not dados_periodo:
            st.info(f"Nenhuma RM localizada entre {periodo[0].strftime('%d/%m/%Y')} e {periodo[1].strftime('%d/%m/%Y')}.")
            st.stop()
            
        df_periodo = pd.DataFrame(dados_periodo)
        st.success(f"Mapeada(s) {df_periodo['rm'].nunique()} RM(s) no período de consulta.")
        
        # Tratamento das colunas de identificadores e numéricas decimais
        for col_num in ["qtd_solicitada", "qtd_comprada", "mat", "rm"]:
            if col_num in df_periodo.columns:
                df_periodo[col_num] = pd.to_numeric(df_periodo[col_num], errors="coerce").fillna(0).astype(int)
        
        # Formatação amigável de data para o padrão de leitura nacional (DD/MM/AAAA)
        if "data_emissao" in df_periodo.columns:
            df_periodo["data_emissao"] = pd.to_datetime(df_periodo["data_emissao"], errors="coerce").dt.strftime("%d/%m/%Y")
            
        # Renomeação estrutural segura usando inplace=True
        df_periodo.rename(
            columns={
                "rm": "RM",
                "data_emissao": "Data Emissão",
                "mat": "Material",
                "desc_item": "Descrição",
                "qtd_solicitada": "Qtd Solicitada",
                "qtd_comprada": "Qtd Comprada",
                "status_atendimento": "Status"
            },
            inplace=True
        )
        
        colunas_exibicao = ["RM", "Data Emissão", "Material", "Descrição", "Qtd Solicitada", "Qtd Comprada", "Status"]
        colunas_validas = [c for c in colunas_exibicao if c in df_periodo.columns]
        
        # Renderização do DataFrame formatado com o mapeamento dinâmico de cores sutil
        st.dataframe(
            df_periodo[colunas_validas].style.map(Skinner_status, subset=['Status']),
            use_container_width=True,
            hide_index=True
        )
