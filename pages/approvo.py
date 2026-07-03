import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

# 1. CONFIGURAÇÃO E INTERFACE STREAMLIT
st.set_page_config(page_title="Upload de Pedidos", layout="wide")
st.title("📥 Approvo Consolidado")
st.write("Informas Cruzadas do Mega com o Approvo")

# 2. CONEXÃO COM O SUPABASE (Puxando dos Secrets do Streamlit ou .env)
SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("❌ Erro: Credenciais do Supabase não configuradas.")
    st.stop()

# Inicializa o cliente do Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.divider()