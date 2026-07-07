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
                        # A. Busca a RM e já elimina duplicados da origem
            res_rm = supabase.table("vw_approvo_rm").select("*").eq("rm", str(buscar_rm)).execute()
            df_rm_bruto = pd.DataFrame(res_rm.data)
            if not df_rm_bruto.empty:
                df_rm_bruto = df_rm_bruto.drop_duplicates() # 🚨 Limpa duplicados idênticos da RM

            # B. Busca a tabela de relacionamento
            res_vinculo = supabase.table("pedido_compra").select("rm", "pedido").eq("rm", int(buscar_rm)).execute()
            df_vinculo = pd.DataFrame(res_vinculo.data)
            if not df_vinculo.empty:
                df_vinculo = df_vinculo.drop_duplicates() # 🚨 Limpa duplicados idênticos do Vínculo

            # C. Busca os dados da segunda view baseada nos pedidos
            if not df_vinculo.empty:
                lista_pedidos = list(set([str(p.get("pedido")) for p in res_vinculo.data if p.get("pedido") is not None]))
                if lista_pedidos:
                    res_pc = supabase.table("vw_approvo_pc").select("*").in_("pedido", lista_pedidos).execute()
                    df_pc_bruto = pd.DataFrame(res_pc.data)
                    
                    if "entregas_agendadas" in df_pc_bruto.columns:
                        df_pc_bruto.drop(columns=["entregas_agendadas"], inplace=True)
                    
                    if not df_pc_bruto.empty:
                        # 🚨 LIMPA DUPLICADOS DA ORIGEM DO PC (Resolve o problema do print!)
                        df_pc_bruto = df_pc_bruto.drop_duplicates() 
                            

                        # ==========================================================
            # 🔄 5. LOGÍSTICA DE CRUZAMENTO DE DADOS (PANDAS MERGE) - BLINDADO
            # ==========================================================
            # 🚨 1. FORÇA A LIMPEZA E PADRONIZAÇÃO DE TEXTOS/NÚMEROS DA VIEW DA RM
            df_rm_bruto["rm_str"] = df_rm_bruto["rm"].astype(str).str.strip()
            df_rm_bruto["mat_str"] = df_rm_bruto["mat"].astype(str).str.strip()
            
            # 🚨 2. RESOLVE A DUPLICIDADE: Mantém apenas as colunas fundamentais que você quer ver na tela
            colunas_vitais_rm = ["nome_solicitante", "rm", "mat", "desc_item", "qtd_solicitada", "data_emissao", "data_necessidade", "status_documento", "data_ocorrencia", "nome_aprovador", "rm_str", "mat_str"]
            colunas_existentes_rm = [c for c in colunas_vitais_rm if c in df_rm_bruto.columns]
            
            df_rm_limpo = df_rm_bruto[colunas_existentes_rm].drop_duplicates().copy()
            
            if not df_vinculo.empty:
                df_vinculo["rm_str"] = df_vinculo["rm"].astype(str).str.strip()
                df_vinculo["pedido_str"] = df_vinculo["pedido"].astype(str).str.strip()
                
                # Junta RM com a tabela que diz qual pedido ela gerou
                df_consolidado = pd.merge(df_rm_limpo, df_vinculo[["rm_str", "pedido_str"]], on="rm_str", how="left")
                
                if not df_pc_bruto.empty:
                    # 🚨 3. FORÇA A PADRONIZAÇÃO DE TIPOS NA SEGUNDA VIEW (PC)
                    df_pc_bruto["pedido_str"] = df_pc_bruto["pedido"].astype(str).str.strip()
                    df_pc_bruto["mat_str"] = df_pc_bruto["mat"].astype(str).str.strip()
                    
                    # Limpa o histórico de ocorrências do PC mantendo apenas os dados de exibição
                    # Importante: Não colocamos 'entregas_agendadas' aqui para isolar a coluna problemática
                    colunas_vitais_pc = ["pedido_str", "mat_str", "comprador", "entrega", "quantidade", "status_documento", "data_ocorrencia", "nome_aprovador"]
                    colunas_existentes_pc = [c for c in colunas_vitais_pc if c in df_pc_bruto.columns]
                    
                    df_pc_limpo = df_pc_bruto[colunas_existentes_pc].drop_duplicates().copy()
                    
                    # Renomeia colunas para não chocar com os nomes da primeira view
                    df_pc_limpo.rename(columns={
                        "status_documento": "status_pc",
                        "data_oficial_ocorrencia": "data_ocorrencia_pc",
                        "data_ocorrencia": "data_ocorrencia_pc",
                        "nome_aprovador": "nome_aprovador_pc",
                        "quantidade": "quantidade_comprada"
                    }, inplace=True, errors="ignore")
                    
                    # 🚨 4. EXECUTA O CRUZAMENTO PERFEITO POR NÚMERO DO PEDIDO E CÓDIGO DO MATERIAL
                    df_final = pd.merge(df_consolidado, df_pc_limpo, on=["pedido_str", "mat_str"], how="left")
                else:
                    df_final = df_consolidado.copy()
                    for col in ["comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]:
                        df_final[col] = None
            else:
                df_final = df_rm_limpo.copy()
                df_final["pedido_str"] = None
                for col in ["comprador", "entrega", "quantidade_comprada", "status_pc", "data_ocorrencia_pc", "nome_aprovador_pc"]:
                    df_final[col] = None
            if "mat" in df_final.columns:
                df_final = df_final.drop_duplicates(subset=["rm", "mat"]).copy()
            else:
                df_final = df_final.drop_duplicates().copy()        

            # 🚨 5. SOLUÇÃO DEFINITIVA DO ERRO 'unhashable type: list':
            # Removemos qualquer coluna de lista/JSONB residual (como entregas_agendadas) antes do drop_duplicates
            colunas_para_remover = ["entregas_agendadas"]
            colunas_reais_para_tirar = [c for c in colunas_para_remover if c in df_final.columns]
            if colunas_reais_para_tirar:
                df_final.drop(columns=colunas_reais_para_tirar, inplace=True)

            # Agora que a lista foi removida do DataFrame, o comando roda com 100% de sucesso e velocidade
            if "mat" in df_final.columns:
                df_final = df_final.drop_duplicates(subset=["rm", "mat"]).copy()
            else:
                df_final = df_final.drop_duplicates().copy()
                
                
              # ==========================================================
            # 🛠️ 5.5 PAINEL DE FILTROS COMBINADOS (APLICADOS NO DF_FINAL)
            # ==========================================================
            st.markdown("#### 🔍 Refinar Resultados de Busca")
            
            # Divide os filtros em duas linhas de colunas para organizar o layout
            f_col1, f_col2, f_col3 = st.columns(3)
            f_col4, f_col5 = st.columns(2)
            
            # Coleta as opções únicas direto do DataFrame para os Selectboxes (evita travar fixo)
            opcoes_requisitante = ["Todos"] + sorted(list(df_final["nome_solicitante"].unique())) if "nome_solicitante" in df_final.columns else ["Todos"]
            opcoes_comprador = ["Todos"] + sorted(list(df_final["comprador"].unique())) if "comprador" in df_final.columns else ["Todos"]
            
            # Tradução temporária para bater com o banco antes do mapeamento final
            mapa_siglas = {"A": "Aprovado", "E": "Em Aprovação", "R": "Reprovado", "---": "---"}
            
            with f_col1:
                filtro_req = st.selectbox("Filtrar por Requisitante:", opcoes_requisitante)
            with f_col2:
                filtro_comp = st.selectbox("Filtrar por Comprador:", opcoes_comprador)
            with f_col3:
                # Intervalo de Datas (Retorna uma lista com 2 elementos se o usuário escolher o fim)
                filtro_periodo = st.date_input("Intervalo (Data da Requisição):", value=[], format="DD/MM/YYYY")
                
            with f_col4:
                filtro_status_rm = st.selectbox("Status da RM:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"])
            with f_col5:
                filtro_status_pc = st.selectbox("Status do PC:", ["Todos", "Aprovado", "Em Aprovação", "Reprovado"])

            # --- APLICAÇÃO DOS FILTROS NO DATAFRAME ANTES DA EXIBIÇÃO ---
            df_filtrado = df_final.copy()
            
            if filtro_req != "Todos":
                df_filtrado = df_filtrado[df_filtrado["nome_solicitante"] == filtro_req]
                
            if filtro_comp != "Todos":
                df_filtrado = df_filtrado[df_filtrado["comprador"] == filtro_comp]
                
            if filtro_status_rm != "Todos":
                # Inverte a tradução para buscar a sigla original ("A", "E", "R") na coluna bruta do banco
                sigla_rm = [k for k, v in mapa_siglas.items() if v == filtro_status_rm][0]
                df_filtrado = df_filtrado[df_filtrado["status_documento"].astype(str).str.strip() == sigla_rm]
                
            if filtro_status_pc != "Todos":
                sigla_pc = [k for k, v in mapa_siglas.items() if v == filtro_status_pc][0]
                df_filtrado = df_filtrado[df_filtrado["status_pc"].astype(str).str.strip() == sigla_pc]
                
            if len(filtro_periodo) == 2:
                # Converte a coluna de data para o tipo Datetime do Pandas para fazer o filtro de data_inicio e data_fim
                data_inicio, data_fim = pd.to_datetime(filtro_periodo[0]), pd.to_datetime(filtro_periodo[1])
                df_filtrado["data_emissao_dt"] = pd.to_datetime(df_filtrado["data_emissao"], errors="coerce")
                df_filtrado = df_filtrado[(df_filtrado["data_emissao_dt"] >= data_inicio) & (df_filtrado["data_emissao_dt"] <= data_fim)]

            # Se o filtro esvaziar a tabela, avisa o usuário de forma amigável
            if df_filtrado.empty:
                st.warning("⚠️ Nenhum registro corresponde aos filtros selecionados. Tente ajustar os critérios.")
                st.stop()   

                    
                        # ==========================================================
            # 📊 6. MAPEAMENTO, TRADUÇÃO E FORMATAÇÃO VISUAL
            # ==========================================================
            # Dicionário de tradução das siglas de Status da RM e do PC
            mapa_status_extenso = {"A": "Aprovado", "E": "Em Aprovação", "R": "Reprovado", "---": "---"}
            
            # Aplica a tradução estrita mapeando os valores de texto
            if "status_documento" in df_filtrado.columns:
                df_filtrado["status_documento"] = df_filtrado["status_documento"].astype(str).str.strip().map(lambda x: mapa_status_extenso.get(x.upper(), x))
            if "status_pc" in df_filtrado.columns:
                df_filtrado["status_pc"] = df_filtrado["status_pc"].astype(str).str.strip().map(lambda x: mapa_status_extenso.get(x.upper(), x))

            # Limpa as casas decimais das colunas de quantidade do Mega (.000000 -> inteiro)
            if "qtd_solicitada" in df_filtrado.columns:
                df_filtrado["qtd_solicitada"] = pd.to_numeric(df_filtrado["qtd_solicitada"], errors="coerce").fillna(0).astype(int)
            if "quantidade_comprada" in df_filtrado.columns:
                df_filtrado["quantidade_comprada"] = pd.to_numeric(df_filtrado["quantidade_comprada"], errors="coerce").fillna(0).astype(int)

            # Formatação de datas comuns para o padrão brasileiro (DD/MM/AAAA)
            datas_comuns = ["data_emissao", "data_necessidade", "entrega"]
            for col in datas_comuns:
                if col in df_filtrado.columns:
                    df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors="coerce").dt.strftime("%d/%m/%Y")
                    
            # Formatação de datas com hora para as ocorrências de auditoria do Approvo
            datas_horas = ["data_ocorrencia", "data_ocorrencia_pc"]
            for col in datas_horas:
                if col in df_filtrado.columns:
                    df_filtrado[col] = pd.to_datetime(df_filtrado[col], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")

            # Garante que qualquer campo que tenha ficado nulo após os filtros exiba traços limpos
            df_filtrado.fillna("---", inplace=True)
            df_filtrado.replace("nan", "---", inplace=True)

            # Estrutura do Dicionário de MultiIndex (Vincula colunas físicas às colunas executivas coloridas)
            colunas_multi_index = {
                "nome_solicitante":   ("REQUISICAO DE MATERIAL MEGA", "Requisitante"),
                "rm":                 ("REQUISICAO DE MATERIAL MEGA", "Nr. RM"),
                "mat":                ("REQUISICAO DE MATERIAL MEGA", "Nr. Material"),
                "desc_item":          ("REQUISICAO DE MATERIAL MEGA", "Descrição"),
                "qtd_solicitada":     ("REQUISICAO DE MATERIAL MEGA", "Qt. Sol."),
                "data_emissao":       ("REQUISICAO DE MATERIAL MEGA", "Data da Requisição"),
                "data_necessidade":   ("REQUISICAO DE MATERIAL MEGA", "Data da Nec."),
                
                "status_documento":   ("APPROVAL (RM)", "Status da Aprovação"),
                "data_ocorrencia":    ("APPROVAL (RM)", "Data da Aprovação"),
                "nome_aprovador":     ("APPROVAL (RM)", "Aprovador"),
                
                "comprador":          ("PEDIDO DE COMPRA MEGA", "Comprador"),
                "pedido_str":         ("PEDIDO DE COMPRA MEGA", "Nr. PC"),
                "entrega":            ("PEDIDO DE COMPRA MEGA", "Data de Entrega"),
                "quantidade_comprada":("PEDIDO DE COMPRA MEGA", "Qt. Compr."),
                
                "status_pc":          ("APPROVAL (PC)", "Status da Aprovação"),
                "data_ocorrencia_pc": ("APPROVAL (PC)", "Data da Aprovação"),
                "nome_aprovador_pc":  ("APPROVAL (PC)", "Aprovador")
            }

            # Filtra apenas as colunas mapeadas presentes e monta o cabeçalho duplo agrupado do Pandas
            colunas_existentes = [col for col in colunas_multi_index.keys() if col in df_filtrado.columns]
            df_exibicao = df_filtrado[colunas_existentes].copy()
            df_exibicao.columns = pd.MultiIndex.from_tuples([colunas_multi_index[c] for c in colunas_existentes])


            # ==========================================================
            # 🎨 7. MAPA DE ESTILIZAÇÃO CSS DE CORES (IDENTIDADE PASTEL)
            # ==========================================================
            def aplicar_cores_corpo(df):
                estilos = pd.DataFrame('', index=df.index, columns=df.columns)
                for col in df.columns:
                    grupo = col[0] # Alvo: Captura a string do nível superior do MultiIndex
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
