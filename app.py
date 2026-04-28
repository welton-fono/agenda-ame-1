import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
import streamlit.components.v1 as components
from sqlalchemy import text

# Configuração da Página
st.set_page_config(page_title="AME | Gestão de EEG", layout="wide")

# CSS Estilizado
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background-color: #f4f7f5; }
    .logo-ame {
        font-size: 50px; font-weight: 800;
        background: linear-gradient(135deg, #1B5E20 0%, #4CAF50 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-align: center; margin-bottom: -10px;
    }
    .sub-logo {
        font-size: 12px; text-transform: uppercase; color: #666;
        text-align: center; margin-bottom: 30px; font-weight: 600;
    }
    .stButton>button {
        border: none; background-color: #ffffff; color: #2E7D32;
        border-radius: 12px !important; height: 90px !important;
        font-weight: 600; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    }
    .stButton>button:hover { transform: translateY(-3px); border: 1px solid #4CAF50; }
    div[data-testid="stColumn"] button[aria-label*="selected"] {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%) !important;
        color: white !important;
    }
    .feriado-box {
        background: #ffebee; color: #c62828; border-radius: 12px; height: 90px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        font-size: 0.85rem; font-weight: 700; border: 1px solid #ffcdd2;
    }
    .paciente-card {
        background: white; padding: 20px; border-radius: 15px;
        border-left: 5px solid #2E7D32; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 10px;
    }
    @media print {
        section[data-testid="stSidebar"], .stButton, hr, .stHeader, [data-testid="stHeader"] { display: none !important; }
        .stApp { background-color: white !important; }
        .paciente-card { border: 1px solid #eee !important; break-inside: avoid; }
    }
    </style>
""", unsafe_allow_html=True)

# Tenta conectar ao banco de dados
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("Erro crítico de conexão. Verifique os Secrets no Streamlit Cloud.")
    st.stop()

def inicializar_banco():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS agendamentos (id SERIAL PRIMARY KEY, data DATE, turno TEXT, paciente TEXT, empresa TEXT, observacao TEXT, responsavel TEXT, registro TEXT)"))
        s.execute(text("CREATE TABLE IF NOT EXISTS datas_bloqueadas (id SERIAL PRIMARY KEY, data DATE UNIQUE, motivo TEXT)"))
        s.execute(text("CREATE TABLE IF NOT EXISTS limites_vagas (id SERIAL PRIMARY KEY, data DATE, turno TEXT, limite INTEGER, UNIQUE(data, turno))"))
        s.commit()

def main():
    inicializar_banco()
    if 'data_sel' not in st.session_state: st.session_state.data_sel = date.today()
    if 'mes_ref' not in st.session_state: st.session_state.mes_ref = date.today().replace(day=1)

    # Carregar dados com tratamento para evitar erros de cache
    df_bloqueios = conn.query("SELECT data, motivo FROM datas_bloqueadas", ttl=0)
    dict_bloqueios = {row['data']: row['motivo'] for _, row in df_bloqueios.iterrows()}
    
    df_limites = conn.query("SELECT data, turno, limite FROM limites_vagas", ttl=0)
    dict_limites = {(row['data'], row['turno']): row['limite'] for _, row in df_limites.iterrows()}
    
    def obter_limite(d, t): return dict_limites.get((d, t), 6 if t == "Manhã" else 10)

    # Sidebar
    with st.sidebar:
        st.markdown('<div class="logo-ame">AME</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-logo">Assistência Médica Especializada</div>', unsafe_allow_html=True)
        
        st.markdown("### 🏥 Novo Agendamento")
        dt_cad = st.date_input("Data", value=st.session_state.data_sel)
        periodo = st.radio("Turno", ["Manhã", "Tarde"], horizontal=True)
        limite = obter_limite(dt_cad, periodo)
        
        res_ocup = conn.query("SELECT COUNT(*) as total FROM agendamentos WHERE data=:d AND turno=:t", params={"d": dt_cad, "t": periodo}, ttl=0)
        ocupadas = res_ocup['total'][0] if not res_ocup.empty else 0
        
        if dt_cad in dict_bloqueios:
            st.error(f"🔒 BLOQUEADO: {dict_bloqueios[dt_cad]}")
        elif ocupadas >= limite:
            st.error(f"🚫 LOTADO ({ocupadas}/{limite})")
        else:
            with st.form("f_ame", clear_on_submit=True):
                nome = st.text_input("Paciente").upper(); emp = st.text_input("Empresa").upper()
                obs = st.text_input("Obs"); resp = st.text_input("Sua Assinatura").upper()
                if st.form_submit_button("AGENDAR"):
                    if nome and emp and resp:
                        with conn.session as s:
                            s.execute(text("INSERT INTO agendamentos (data, turno, paciente, empresa, observacao, responsavel, registro) VALUES (:d,:t,:p,:e,:o,:r,:reg)"),
                                     {"d":dt_cad, "t":periodo, "p":nome, "e":emp, "o":obs, "r":resp, "reg":datetime.now().strftime("%d/%m %H:%M")})
                            s.commit()
                        st.rerun()
        
        st.markdown("---")
        with st.expander("⚙️ Bloqueios"):
            d_bl = st.date_input("Data Bloqueio", value=dt_cad)
            if d_bl in dict_bloqueios:
                if st.button("🔓 Desbloquear"):
                    with conn.session as s: s.execute(text("DELETE FROM datas_bloqueadas WHERE data=:d"), {"d":d_bl}); s.commit()
                    st.rerun()
            else:
                mot = st.text_input("Motivo", "Fechado")
                if st.button("🔒 Bloquear"):
                    with conn.session as s: s.execute(text("INSERT INTO datas_bloqueadas (data, motivo) VALUES (:d,:m)"), {"d":d_bl, "m":mot}); s.commit()
                    st.rerun()

        with st.expander("⚙️ Vagas"):
            d_v = st.date_input("Data Vaga", value=dt_cad); t_v = st.selectbox("Turno", ["Manhã", "Tarde"])
            nv = st.number_input("Novo Limite", 0, 50, obter_limite(d_v, t_v))
            if st.button("💾 Salvar"):
                with conn.session as s:
                    s.execute(text("INSERT INTO limites_vagas (data, turno, limite) VALUES (:d,:t,:l) ON CONFLICT (data, turno) DO UPDATE SET limite = EXCLUDED.limite"), {"d":d_v, "t":t_v, "l":nv})
                    s.commit()
                st.rerun()

    # Calendário
    c1, c2, c3 = st.columns([1,2,1])
    with c1: 
        if st.button("⬅️ Anterior"): st.session_state.mes_ref = (st.session_state.mes_ref - timedelta(days=1)).replace(day=1); st.rerun()
    with c2: 
        meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
        st.markdown(f"<h1 style='text-align: center; color: #1B5E20;'>{meses[st.session_state.mes_ref.month-1]} {st.session_state.mes_ref.year}</h1>", unsafe_allow_html=True)
    with c3: 
        if st.button("Próximo ➡️"): st.session_state.mes_ref = (st.session_state.mes_ref + timedelta(days=32)).replace(day=1); st.rerun()

    cols_h = st.columns(7)
    for i, d in enumerate(["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]): cols_h[i].markdown(f"<p style='text-align:center; font-weight:700;'>{d}</p>", unsafe_allow_html=True)

    df_ag_mes = conn.query("SELECT data, turno FROM agendamentos WHERE data >= :ini AND data <= :fim", params={"ini":st.session_state.mes_ref, "fim":st.session_state.mes_ref + timedelta(days=31)}, ttl=0)
    for semana in calendar.Calendar(6).monthdatescalendar(st.session_state.mes_ref.year, st.session_state.mes_ref.month):
        cols = st.columns(7)
        for i, dia in enumerate(semana):
            if dia.month == st.session_state.mes_ref.month:
                with cols[i]:
                    if dia in dict_bloqueios: st.markdown(f"<div class='feriado-box'>{dia.day}<br><small>{dict_bloqueios[dia][:10]}</small></div>", unsafe_allow_html=True)
                    else:
                        m = len(df_ag_mes[(df_ag_mes['data'] == dia) & (df_ag_mes['turno'] == 'Manhã')]) if not df_ag_mes.empty else 0
                        t = len(df_ag_mes[(df_ag_mes['data'] == dia) & (df_ag_mes['turno'] == 'Tarde')]) if not df_ag_mes.empty else 0
                        if st.button(f"{dia.day}\nM:{m}/{obter_limite(dia,'Manhã')}\nT:{t}/{obter_limite(dia,'Tarde')}", key=f"d_{dia}", use_container_width=True):
                            st.session_state.data_sel = dia; st.rerun()

    # Atendimento do Dia
    st.markdown("---")
    c_t, c_p = st.columns([4,1])
    c_t.markdown(f"### 📋 Atendimento: {st.session_state.data_sel.strftime('%d/%m/%Y')}")
    if c_p.button("🖨️ IMPRIMIR"): components.html("<script>window.print();</script>", height=0)

    df_dia = conn.query("SELECT * FROM agendamentos WHERE data=:d ORDER BY turno DESC", params={"d":st.session_state.data_sel}, ttl=0)
    col1, col2 = st.columns(2)
    for i, turno in enumerate(["Manhã", "Tarde"]):
        with [col1, col2][i]:
            st.markdown(f"#### {turno}")
            dados = df_dia[df_dia['turno'] == turno] if not df_dia.empty else pd.DataFrame()
            if dados.empty: st.info("Vazio")
            else:
                for _, r in dados.iterrows():
                    st.markdown(f'<div class="paciente-card"><b>{r["paciente"]}</b><br>{r["empresa"]}<br><small>{r["observacao"]}</small></div>', unsafe_allow_html=True)
                    if st.button("Remover", key=f"del_{r['id']}"):
                        with conn.session as s: s.execute(text("DELETE FROM agendamentos WHERE id=:id"), {"id":r["id"]}); s.commit()
                        st.rerun()

if __name__ == "__main__":
    main()
