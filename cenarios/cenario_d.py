import streamlit as st
import pandas as pd
import os
from supabase import create_client

# 1. TRAVA DE SEGURANÇA E AUTO-LOGIN (À PROVA DE F5)
if "logado" not in st.session_state or not st.session_state.logado:
    usuario_url = st.query_params.get("u")
    if usuario_url:
        st.session_state.logado = True
        st.session_state.usuario_atual = usuario_url
    else:
        st.warning("⚠️ Acesso restrito. Por favor, faça login na tela inicial antes de continuar.")
        if st.button("Ir para a Tela de Login"):
            st.switch_page("app.py")
        st.stop()


def renderizar_cenario_d(rm_para_conferencia="", pedidos=None, supabase=None, Skinner_status=None):
    st.subheader("✅ Approvo Status — Cenário D")
    st.write("Visão ponta a ponta consolidada: Requisições (Mega/Approvo) vs Pedidos (Mega/Approvo).")
    st.divider()

    # 2. INICIALIZAÇÃO DO BANCO
    if supabase is None:
        SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 3. FILTRO DE BUSCA INICIAL
    buscar_rm = st.text_input("Filtrar por Número da RM:", value=rm_para_conferencia).strip()

    if not buscar_rm:
        st.info("💡 Insira o número de uma RM para visualizar a árvore completa de consolidação.")
        st.stop()

    # 4. CAPTURA E EXTRAÇÃO DAS TRÊS ORIGENS DE DADOS
    with st.spinner("Consolidando dados logísticos na nuvem..."):
        try:
            # A. Busca a RM e seus fluxos na primeira view
            res_rm = supabase.table("vw_approvo_rm").select("*").eq("rm", str(buscar_rm)).execute()
            df_rm_bruto = pd.DataFrame(res_rm.data)

            # B. Busca a tabela de relacionamento para descobrir qual Pedido essa RM gerou
            res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").eq("rm", int(buscar_rm)).execute()
            df_vinculo = pd.DataFrame(res_vinculo.data)

            if df_rm_bruto.empty:
                st.warning(f"Nenhum registro localizado para a RM {buscar_rm} na view `vw_approvo_rm`.")
                st.stop()

            # C. Inicializa o DataFrame do Pedido vazio (caso a RM não tenha gerado pedido ainda)
            df_pc_bruto = pd.DataFrame()

            # Se a RM possuir um vínculo com pedido_compra, busca os dados da segunda view
            if not df_vinculo.empty:
                # Remove duplicados e extrai a lista de pedidos gerados por essa RM
                lista_pedidos = list(set([str(p.get("pedido")) for p in res_vinculo.data if p.get("pedido") is not None]))
                
                if lista_pedidos:
                    # Busca os dados da segunda view baseada nos pedidos encontrados
                    res_pc = supabase.table("vw_approvo_pc").select("*").in_("pedido", lista_pedidos).execute()
                    df_pc_bruto = pd.DataFrame(res_pc.data)

                        # ==========================================================
                        # ==========================================================
            # 🔄 5. LOGÍSTICA DE CRUZAMENTO DE DADOS (PANDAS MERGE) - CORRIGIDO
            # ==========================================================
            # Converte as chaves de cruzamento para texto para evitar incompatibilidade de tipos
            df_rm_bruto["rm_str"] = df_rm_bruto["rm"].astype(str)
            
            if not df_vinculo.empty:
                df_vinculo["rm_str"] = df_vinculo["rm"].astype(str)
                df_vinculo["pedido_str"] = df_vinculo["pedido"].astype(str)
                
                # 1. Junta a RM com a tabela que diz qual pedido ela gerou
                df_consolidado = pd.merge(df_rm_bruto, df_vinculo[["rm_str", "pedido_str"]], on="rm_str", how="left")
                
                if not df_pc_bruto.empty:
                    df_pc_bruto["pedido_str"] = df_pc_bruto["pedido"].astype(str)
                    
                    # Renomeia colunas duplicadas da segunda view para não chocar com a primeira
                    df_pc_bruto.rename(columns={
                        "status_documento": "status_pc",
                        "data_oficial_ocorrencia": "data_ocorrencia_pc",
                        "data_ocorrencia": "data_ocorrencia_pc",
                        "nome_aprovador": "nome_aprovador_pc",
                        "quantidade": "quantidade_comprada" # Evita chocar com qtd_solicitada
                    }, inplace=True, errors="ignore")
                    
                    # 🚨 CORREÇÃO DO CRUZAMENTO: Cruzamos APENAS por pedido_str para garantir 
                    # que os dados do comprador e aprovação do PC se acoplem sem multiplicar linhas
                    df_final = pd.merge(df_consolidado, df_pc_bruto, on="pedido_str", how="left")
                else:
                    df_final = df_consolidado.copy()
                    for col in ["comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]:
                        df_final[col] = None
            else:
                df_final = df_rm_bruto.copy()
                df_final["pedido_str"] = None
                for col in ["comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]:
                    df_final[col] = None

            # ==========================================================
            # 📊 6. MAPEAMENTO, TRADUÇÃO E FORMATAÇÃO VISUAL
            # ==========================================================
            # Tradução das siglas de Status da RM e do PC (A -> Aprovado, E -> Em Aprovação, R -> Reprovado)
            mapa_status = {"A": "Aprovado", "E": "Em Aprovação", "R": "Reprovado"}
            
            if "status_documento" in df_final.columns:
                df_final["status_documento"] = df_final["status_documento"].map(lambda x: mapa_status.get(str(x).upper().strip(), x))
            if "status_pc" in df_final.columns:
                df_final["status_pc"] = df_final["status_pc"].map(lambda x: mapa_status.get(str(x).upper().strip(), x))

            # Formatação de datas para padrão BR
            datas_comuns = ["data_emissao", "data_necessidade", "entrega"]
            for col in datas_comuns:
                if col in df_final.columns:
                    df_final[col] = pd.to_datetime(df_final[col], errors="coerce").dt.strftime("%d/%m/%Y")
                    
            datas_horas = ["data_oficial_ocorrencia", "data_ocorrencia", "data_ocorrencia_pc"]
            for col in datas_horas:
                if col in df_final.columns:
                    df_final[col] = pd.to_datetime(df_final[col], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")

            # Tratamento de valores nulos para strings de exibição limpa
            df_final.fillna("---", inplace=True)

            # Mapeamento de colunas estruturado no formato MultiIndex (Super Cabeçalho Agrupado)
            colunas_multi_index = {
                "nome_solicitante":   ("REQUISICAO DE MATERIAL MEGA", "Requisitante"),
                "rm":                 ("REQUISICAO DE MATERIAL MEGA", "Nr. RM"),
                "mat":                ("REQUISICAO DE MATERIAL MEGA", "Nr. Material"),
                "desc_item":          ("REQUISICAO DE MATERIAL MEGA", "Descrição"),
                "qtd_solicitada":     ("REQUISICAO DE MATERIAL MEGA", "Qt. Sol."),
                "data_emissao":       ("REQUISICAO DE MATERIAL MEGA", "Data da Requisição"),
                "data_necessidade":   ("REQUISICAO DE MATERIAL MEGA", "Data da Nec."),
                
                "status_documento":   ("APPROVAL (RM)", "Status da Aprovação"),
                "data_oficial_ocorrencia": ("APPROVAL (RM)", "Data da Aprovação"),
                "data_ocorrencia":    ("APPROVAL (RM)", "Data da Aprovação"),
                "nome_aprovador":     ("APPROVAL (RM)", "Aprovador"),
                
                "comprador":          ("PEDIDO DE COMPRA MEGA", "Comprador"),
                "pedido_str":         ("PEDIDO DE COMPRA MEGA", "Nr. PC"),
                "entrega":            ("PEDIDO DE COMPRA MEGA", "Data de Entrega"),
                "quantidade_comprada": ("PEDIDO DE COMPRA MEGA", "Qt. Compr."),
                
                "status_pc":          ("APPROVAL (PC)", "Status da Aprovação"),
                "data_ocorrencia_pc": ("APPROVAL (PC)", "Data da Aprovação"),
                "nome_aprovador_pc":  ("APPROVAL (PC)", "Aprovador")
            }

            # Filtra apenas as colunas mapeadas e monta o cabeçalho duplo do Pandas
            colunas_existentes = [col for col in colunas_multi_index.keys() if col in df_final.columns]
            df_exibicao = df_final[colunas_existentes].copy()
            df_exibicao.columns = pd.MultiIndex.from_tuples([colunas_multi_index[c] for c in colunas_existentes])

            # ==========================================================
            # 🎨 7. MAPA DE ESTILIZAÇÃO CSS DE CORES (IDENTIDADE PASTEL)
            # ==========================================================
            def aplicar_cores_corpo(df):
                """Aplica cores suaves nas células de dados divididas por grupos"""
                estilos = pd.DataFrame('', index=df.index, columns=df.columns)
                for col in df.columns:
                    grupo = col[0] # Captura o primeiro nível do MultiIndex (O Super Cabeçalho)
                    if grupo == "REQUISICAO DE MATERIAL MEGA":
                        estilos[col] = 'background-color: #f2f7f2; color: #000000;'
                    elif grupo == "APPROVAL (RM)":
                        estilos[col] = 'background-color: #e2f0d9; color: #000000;'
                    elif grupo == "PEDIDO DE COMPRA MEGA":
                        estilos[col] = 'background-color: #fbf2fa; color: #000000;'
                    elif grupo == "APPROVAL (PC)":
                        estilos[col] = 'background-color: #f3daf1; color: #000000;'
                return estilos

            # Injeta CSS para pintar os blocos superiores fixos do cabeçalho HTML do Streamlit
            st.markdown("""
                <style>
                    th.col_heading.level0 { font-weight: bold !important; color: #000000 !important; text-align: center !important; }
                    th.col_heading.level0.id0_6 { background-color: #e2f0d9 !important; }   /* RM */
                    th.col_heading.level0.id7_9 { background-color: #a9d08e !important; }   /* Approval RM */
                    th.col_heading.level0.id10_13 { background-color: #f2dcfa !important; } /* PC */
                    th.col_heading.level0.id14_16 { background-color: #df9ff2 !important; } /* Approval PC */
                </style>
            """, unsafe_allow_html=True)

            # Aplica o mapa de estilos e renderiza na tela de ponta a ponta
            df_estilizado = df_exibicao.style.apply(aplicar_cores_corpo, axis=None)
            st.dataframe(df_estilizado, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error(f"❌ Erro crítico ao consolidar as visões no Cenário D: {e}")

if __name__ == "__main__":
    # Garante que se o Streamlit chamar o arquivo direto, ele não quebra por falta de parâmetros
    renderizar_cenario_d(rm_para_conferencia="", pedidos=None, supabase=None, Skinner_status=None)
