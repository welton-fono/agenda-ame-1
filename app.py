import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta
import calendar
import streamlit.components.v1 as components

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E TEMA CHIQUE
# ==========================================
st.set_page_config(page_title="AME | Gestão de EEG", layout="wide", initial_sidebar_state="expanded")

# CSS PERSONALIZADO (Design Moderno + Regras de Impressão)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
    
    * { font-family: 'Inter', sans-serif; }

    /* Fundo da aplicação */
    .stApp { background-color: #f4f7f5; }

    /* Estilização do LOGO AME */
    .logo-ame {
        font-size: 50px;
        font-weight: 800;
        background: linear-gradient(135deg, #1B5E20 0%, #4CAF50 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -2px;
        text-align: center;
        margin-bottom: -10px;
        filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.1));
    }
    .sub-logo {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 2px;
        color: #666;
        text-align: center;
        margin-bottom: 30px;
        font-weight: 600;
    }

    /* Barra Lateral */
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e0e0e0;
    }

    /* Botões do Calendário */
    .stButton>button {
        border: none;
        background-color: #ffffff;
        color: #2E7D32;
        border-radius: 12px !important;
        height: 90px !important;
        font-weight: 600;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 15px rgba(46, 125, 50, 0.2);
        background-color: #ffffff;
        border: 1px solid #4CAF50;
    }
    
    /* Dia Selecionado */
    div[data-testid="stColumn"] button[aria-label*="selected"] {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%) !important;
        color: white !important;
        box-shadow: 0 8px 15px rgba(27, 94, 32, 0.3) !important;
    }

    /* Data Bloqueada / Feriado */
    .feriado-box {
        background: #ffebee;
        color: #c62828;
        border-radius: 12px;
        height: 90px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
        font-weight: 700;
        border: 1px solid #ffcdd2;
        text-align: center;
    }

    /* Cards de Pacientes */
    .paciente-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #2E7D32;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 10px;
    }

    /* --- REGRAS DE IMPRESSÃO --- */
    @media print {
        section[data-testid="stSidebar"], 
        .stButton, 
        hr, 
        .stHeader, 
        [data-testid="stHeader"],
        div[data-testid="stHorizontalBlock"]:has(button), 
        div[class*="st-emotion-cache-"] > div:has(button) { 
            display: none !important; 
        }
        .stApp { background-color: white !important; }
        .paciente-card { 
            border: 1px solid #eee !important; 
            box-shadow: none !important;
            break-inside: avoid; 
        }
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. BANCO DE DADOS
# ==========================================
def conectar():
    conn = sqlite3.connect('agenda_ame_turbo.db', check_same_thread=False)
    c = conn.cursor()
    
    # Tabela de Agendamentos
    c.execute('''CREATE TABLE IF NOT EXISTS agendamentos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, turno TEXT, 
                 paciente TEXT, empresa TEXT, observacao TEXT, responsavel TEXT, registro TEXT)''')
    try: 
        c.execute("ALTER TABLE agendamentos ADD COLUMN observacao TEXT")
    except: 
        pass
    
    # Tabela de Datas Bloqueadas
    c.execute('''CREATE TABLE IF NOT EXISTS datas_bloqueadas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, motivo TEXT)''')

    # Tabela de Limites de Vagas Personalizados
    c.execute('''CREATE TABLE IF NOT EXISTS limites_vagas
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, turno TEXT, limite INTEGER)''')
    
    conn.commit()
    return conn

# ==========================================
# 3. APLICAÇÃO PRINCIPAL
# ==========================================
def main():
    conn = conectar()
    
    if 'data_sel' not in st.session_state: st.session_state.data_sel = date.today()
    if 'mes_ref' not in st.session_state: st.session_state.mes_ref = date.today().replace(day=1)

    # Carregar dados rápidos do banco
    df_bloqueios = pd.read_sql_query("SELECT data, motivo FROM datas_bloqueadas", conn)
    dict_bloqueios = dict(zip(df_bloqueios.data, df_bloqueios.motivo))

    df_limites = pd.read_sql_query("SELECT data, turno, limite FROM limites_vagas", conn)
    dict_limites = {(row['data'], row['turno']): row['limite'] for _, row in df_limites.iterrows()}

    def obter_limite(data_str, turno):
        """Retorna o limite personalizado ou o padrão (6 Manhã, 10 Tarde)"""
        return dict_limites.get((data_str, turno), 6 if turno == "Manhã" else 10)

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown('<div class="logo-ame">AME</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-logo">Assistência Médica Especializada</div>', unsafe_allow_html=True)
        
        # Formulário de Agendamento
        with st.container():
            st.markdown("### 🏥 Novo Agendamento")
            dt_cad = st.date_input("Selecione a Data", value=st.session_state.data_sel)
            dt_cad_str = dt_cad.strftime("%Y-%m-%d")
            periodo = st.radio("Período do Exame", ["Manhã", "Tarde"], horizontal=True)
            
            # Aplica a lógica dinâmica de limite
            limite = obter_limite(dt_cad_str, periodo)
            ocupadas = pd.read_sql_query(f"SELECT COUNT(*) as total FROM agendamentos WHERE data='{dt_cad_str}' AND turno='{periodo}'", conn)['total'][0]
            livres = limite - ocupadas

            if dt_cad_str in dict_bloqueios:
                motivo = dict_bloqueios[dt_cad_str]
                st.error(f"🔒 AGENDA FECHADA\nMotivo: {motivo}")
            elif livres <= 0:
                st.error(f"🚫 Lotação Máxima Atingida ({ocupadas}/{limite})")
            else:
                st.info(f"Vagas disponíveis: {livres} de {limite}")
                with st.form("form_ame", clear_on_submit=True):
                    nome = st.text_input("Nome do Paciente").upper()
                    emp = st.text_input("Empresa / Convênio").upper()
                    obs = st.text_input("Observações Adicionais")
                    resp = st.text_input("Sua Assinatura").upper()
                    
                    if st.form_submit_button("FINALIZAR AGENDAMENTO"):
                        if nome and emp and resp:
                            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
                            conn.cursor().execute("INSERT INTO agendamentos (data, turno, paciente, empresa, observacao, responsavel, registro) VALUES (?,?,?,?,?,?,?)",
                                                (dt_cad_str, periodo, nome, emp, obs, resp, agora))
                            conn.commit()
                            st.session_state.data_sel = dt_cad
                            st.success("✅ Sucesso!")
                            st.rerun()

        st.markdown("---")
        
        # Gerenciar Bloqueios
        with st.expander("⚙️ Gerenciar Bloqueios de Agenda"):
            dt_bloq = st.date_input("Data para bloquear", value=st.session_state.data_sel, key="dt_bloq")
            dt_bloq_str = dt_bloq.strftime("%Y-%m-%d")
            
            if dt_bloq_str in dict_bloqueios:
                st.warning(f"Data fechada: {dict_bloqueios[dt_bloq_str]}")
                if st.button("🔓 Desbloquear Data", use_container_width=True):
                    conn.cursor().execute("DELETE FROM datas_bloqueadas WHERE data=?", (dt_bloq_str,))
                    conn.commit()
                    st.rerun()
            else:
                motivo_bloq = st.text_input("Motivo (ex: Feriado)", value="Clínica Fechada")
                if st.button("🔒 Bloquear Data", use_container_width=True):
                    conn.cursor().execute("INSERT INTO datas_bloqueadas (data, motivo) VALUES (?,?)", (dt_bloq_str, motivo_bloq))
                    conn.commit()
                    st.rerun()

        # Gerenciar Limites de Vagas
        with st.expander("⚙️ Gerenciar Vagas / Limites"):
            dt_lim = st.date_input("Data para alterar o limite", value=st.session_state.data_sel, key="dt_lim")
            dt_lim_str = dt_lim.strftime("%Y-%m-%d")
            turno_lim = st.selectbox("Turno para alterar", ["Manhã", "Tarde"], key="turno_lim")
            
            limite_atual = obter_limite(dt_lim_str, turno_lim)
            novo_limite = st.number_input(f"Limite de vagas ({turno_lim})", min_value=0, max_value=50, value=limite_atual, step=1)
            
            if st.button("💾 Salvar Limite", use_container_width=True):
                conn.cursor().execute("DELETE FROM limites_vagas WHERE data=? AND turno=?", (dt_lim_str, turno_lim))
                conn.cursor().execute("INSERT INTO limites_vagas (data, turno, limite) VALUES (?,?,?)", (dt_lim_str, turno_lim, novo_limite))
                conn.commit()
                st.rerun()

    # --- PAINEL PRINCIPAL ---
    
    # Cabeçalho com Navegação
    c_nav1, c_nav2, c_nav3 = st.columns([1, 2, 1])
    with c_nav1:
        if st.button("⬅️ Anterior"):
            st.session_state.mes_ref = (st.session_state.mes_ref - timedelta(days=1)).replace(day=1)
            st.rerun()
    with c_nav2:
        meses = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
        titulo_mes = f"{meses[st.session_state.mes_ref.month - 1]} {st.session_state.mes_ref.year}"
        st.markdown(f"<h1 style='text-align: center; color: #1B5E20; letter-spacing: 2px;'>{titulo_mes}</h1>", unsafe_allow_html=True)
    with c_nav3:
        if st.button("Próximo ➡️"):
            st.session_state.mes_ref = (st.session_state.mes_ref + timedelta(days=32)).replace(day=1)
            st.rerun()

    # Grade do Calendário
    dias_semana = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]
    cols_header = st.columns(7)
    for i, d in enumerate(dias_semana):
        cols_header[i].markdown(f"<p style='text-align:center; font-weight:700; color:#2E7D32;'>{d}</p>", unsafe_allow_html=True)

    cal = calendar.Calendar(firstweekday=6)
    dias_do_mes = cal.monthdatescalendar(st.session_state.mes_ref.year, st.session_state.mes_ref.month)
    df_mes = pd.read_sql_query(f"SELECT data, turno FROM agendamentos", conn)

    for semana in dias_do_mes:
        cols = st.columns(7)
        for i, dia in enumerate(semana):
            with cols[i]:
                dia_str = dia.strftime("%Y-%m-%d")
                
                # Renderiza Bloco Fechado ou Botão de Data
                if dia_str in dict_bloqueios:
                    motivo_curto = dict_bloqueios[dia_str][:12] + '...' if len(dict_bloqueios[dia_str]) > 12 else dict_bloqueios[dia_str]
                    st.markdown(f"<div class='feriado-box'>{dia.day}<br><small>{motivo_curto}</small></div>", unsafe_allow_html=True)
                else:
                    m = len(df_mes[(df_mes['data'] == dia_str) & (df_mes['turno'] == 'Manhã')])
                    t = len(df_mes[(df_mes['data'] == dia_str) & (df_mes['turno'] == 'Tarde')])
                    
                    lim_m = obter_limite(dia_str, "Manhã")
                    lim_t = obter_limite(dia_str, "Tarde")
                    
                    label = f"{dia.day}\n\n🌅 M:{m}/{lim_m}\n☀️ T:{t}/{lim_t}"
                    key_label = f"btn_{dia}" + ("_selected" if dia == st.session_state.data_sel else "")
                    
                    if st.button(label, key=key_label, use_container_width=True):
                        st.session_state.data_sel = dia
                        st.rerun()

    st.markdown("---")

    # --- LISTA DE PACIENTES DIÁRIA ---
    data_f = st.session_state.data_sel.strftime('%d/%m/%Y')
    
    c_titulo, c_botao_print = st.columns([4, 1])
    with c_titulo:
        st.markdown(f"### 📋 Lista de Atendimento do Dia: {data_f}")
    with c_botao_print:
        if st.button("🖨️ IMPRIMIR O DIA", use_container_width=True):
            components.html("<script>window.print();</script>", height=0)

    if st.session_state.data_sel.strftime("%Y-%m-%d") in dict_bloqueios:
        st.warning(f"Atenção: A agenda para o dia {data_f} encontra-se bloqueada. ({dict_bloqueios[st.session_state.data_sel.strftime('%Y-%m-%d')]})")

    df_dia = pd.read_sql_query(f"SELECT * FROM agendamentos WHERE data='{st.session_state.data_sel.strftime('%Y-%m-%d')}'", conn)
    
    col_m, col_t = st.columns(2)
    
    with col_m:
        st.markdown("#### 🌅 Período da Manhã")
        lista_m = df_dia[df_dia['turno'] == "Manhã"]
        if lista_m.empty: st.info("Nenhum paciente agendado.")
        for _, r in lista_m.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="paciente-card">
                    <b>👤 PACIENTE:</b> {r['paciente']}<br>
                    <b>🏢 EMPRESA:</b> {r['empresa']}<br>
                    <b>📝 OBS:</b> {r['observacao'] if r['observacao'] else '-'}<br>
                    <small>✍️ Por: {r['responsavel']}</small>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Remover", key=f"del_{r['id']}"):
                    conn.cursor().execute(f"DELETE FROM agendamentos WHERE id={r['id']}")
                    conn.commit()
                    st.rerun()

    with col_t:
        st.markdown("#### ☀️ Período da Tarde")
        lista_t = df_dia[df_dia['turno'] == "Tarde"]
        if lista_t.empty: st.info("Nenhum paciente agendado.")
        for _, r in lista_t.iterrows():
            with st.container():
                st.markdown(f"""
                <div class="paciente-card">
                    <b>👤 PACIENTE:</b> {r['paciente']}<br>
                    <b>🏢 EMPRESA:</b> {r['empresa']}<br>
                    <b>📝 OBS:</b> {r['observacao'] if r['observacao'] else '-'}<br>
                    <small>✍️ Por: {r['responsavel']}</small>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Remover ", key=f"del_{r['id']}"):
                    conn.cursor().execute(f"DELETE FROM agendamentos WHERE id={r['id']}")
                    conn.commit()
                    st.rerun()

    # ==========================================
    # NOVO: RELATÓRIO MENSAL (PLANILHA)
    # ==========================================
    st.markdown("---")
    st.markdown(f"### 📊 Planilha Mensal: {titulo_mes}")
    
    # Busca os dados do mês atual e organiza por data
    mes_formatado = f"{st.session_state.mes_ref.year}-{st.session_state.mes_ref.month:02d}"
    df_mes_relatorio = pd.read_sql_query(
        f"SELECT data as Data, turno as Turno, paciente as Paciente, empresa as Empresa, observacao as Observação, responsavel as Responsável FROM agendamentos WHERE data LIKE '{mes_formatado}-%' ORDER BY data ASC, turno DESC", conn
    )
    
    if df_mes_relatorio.empty:
        st.info("Nenhum agendamento encontrado para este mês.")
    else:
        # Formata a data para padrão brasileiro
        df_mes_relatorio['Data'] = pd.to_datetime(df_mes_relatorio['Data']).dt.strftime('%d/%m/%Y')
        
        # Exibe a tabela na tela
        st.dataframe(df_mes_relatorio, use_container_width=True, hide_index=True)
        
        col_down, col_print = st.columns([1, 1])
        
        # Botão para baixar Excel/CSV
        with col_down:
            csv_data = df_mes_relatorio.to_csv(index=False, sep=';').encode('utf-8-sig')
            st.download_button(
                label="📥 Baixar Planilha (Excel/CSV)",
                data=csv_data,
                file_name=f"Agendamentos_{titulo_mes.replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
        # Botão para imprimir tabela (Gera um HTML limpo em janela separada)
        with col_print:
            html_table = df_mes_relatorio.to_html(index=False).replace('\n', '')
            js_print_code = f"""
            <button onclick="printTable()" style="width: 100%; border: 1px solid #2E7D32; background: white; color: #2E7D32; padding: 10px 15px; border-radius: 8px; cursor: pointer; font-weight: bold; font-family: sans-serif; transition: 0.3s; box-shadow: 0 2px 5px rgba(0,0,0,0.05);" onmouseover="this.style.background='#2E7D32'; this.style.color='white'" onmouseout="this.style.background='white'; this.style.color='#2E7D32'">
                🖨️ IMPRIMIR PLANILHA DO MÊS
            </button>
            <script>
            function printTable() {{
                var printWin = window.open('', '', 'height=800,width=1000');
                printWin.document.write('<html><head><title>Impressão - {titulo_mes}</title>');
                printWin.document.write('<style>body {{ font-family: sans-serif; }} table {{width:100%; border-collapse: collapse; margin-top: 20px;}} th, td {{border: 1px solid #444; padding: 10px; text-align: left;}} th {{background-color: #f2f2f2;}} h2 {{ color: #1B5E20; text-align: center; }}</style>');
                printWin.document.write('</head><body>');
                printWin.document.write('<h2>Agendamentos - {titulo_mes}</h2>');
                printWin.document.write('{html_table}');
                printWin.document.write('</body></html>');
                printWin.document.close();
                setTimeout(function() {{
                    printWin.print();
                    printWin.close();
                }}, 300);
            }}
            </script>
            """
            components.html(js_print_code, height=50)

if __name__ == "__main__":
    main()
