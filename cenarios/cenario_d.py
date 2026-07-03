# cenarios/cenario_d.py
import streamlit as st
import pandas as pd

def renderizar_cenario_d(supabase):
    st.subheader("✅ Approvo Status — Cenário D")
    st.write("Monitore aqui o cruzamento das informações do Mega com a view `vw_nova`.")
    
    # 1. Filtros da tela
    col1, col2 = st.columns(2)
    with col1:
        buscar_rm = st.text_input("Filtrar por Número da RM:", "").strip()
        
    # 2. Busca de dados na view_nova
    with st.spinner("Buscando dados na view..."):
        try:
            query = supabase.table("vw_nova").select("*")
            if buscar_rm:
                query = query.eq("rm", int(buscar_rm))
                
            dados = query.execute().data
            
            if dados:
                df = pd.DataFrame(dados)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum dado localizado para os filtros selecionados.")
        except Exception as e:
            st.error(f"Erro ao carregar Cenário D: {e}")
