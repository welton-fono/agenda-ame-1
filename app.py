import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta, timezone
import calendar
import streamlit.components.v1 as components
from sqlalchemy import text

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA E TEMA CHIQUE
# ==========================================
st.set_page_config(page_title="AME | Gestão de EEG", layout="wide", initial_sidebar_state="expanded")

# CSS PERSONALIZADO 
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

    /* Botões Normais (Mais compactos) */
    .stButton>button {
        border: none;
        background-color: #ffffff;
        color: #2E7D32;
        border-radius: 8px !important;
        min-height: 35px; 
        padding: 5px 10px !important;
        font-weight: 600;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
        font-size: 0.85rem !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 10px rgba(46, 125, 50, 0.2);
        background-color: #ffffff;
        border: 1px solid #4CAF50;
    }
    
    /* Dia Selecionado fica Verde */
    button[kind="primary"] {
        background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%) !important;
        color: white !important;
        box-shadow: 0 6px 12px rgba(27, 94, 32, 0.3) !important;
        border: none !important;
    }
    button[kind="primary"] * {
        color: white !important;
    }

    /* Data Bloqueada / Feriado */
    .feriado-box {
        background: #ffebee;
        color: #c62828;
        border-radius: 8px;
        min-height: 80px;
        padding: 10px;
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
        padding: 12px 15px; 
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 2px; 
        font-size: 0.9rem; 
        line-height: 1.4;
    }

    /* Resultados da Busca */
    .busca-card {
        background: #e8f5e9;
        border-left: 4px solid #2E7D32;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 8px;
        font-size: 0.85rem;
        color: #333;
    }

    /* --- REGRAS DE IMPRESSÃO --- */
    @media print {
        section[data-testid="stSidebar"], 
        .stButton, 
        hr, 
        .stHeader, 
        [data-testid="stHeader"],
        div[data-testid="stHorizontalBlock"]:has(button), 
        div[class*="st-emotion-cache-"] > div:has(button),
        iframe { 
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
# 2. BANCO DE DADOS (SUPABASE / NUVEM)
# ==========================================
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error("Erro crítico de conexão com o Supabase. Verifique os Secrets.")
    st.stop()

def inicializar_banco():
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS agendamentos (id SERIAL PRIMARY KEY, data DATE, turno TEXT, paciente TEXT, empresa TEXT, observacao TEXT, responsavel TEXT, registro TEXT, status TEXT DEFAULT 'Pendente')"))
        s.execute(text("ALTER TABLE agendamentos ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Pendente'"))
        s.execute(text("CREATE TABLE IF NOT EXISTS datas_bloqueadas (id SERIAL PRIMARY KEY, data DATE UNIQUE, motivo TEXT)"))
        s.execute(text("CREATE TABLE IF NOT EXISTS limites_vagas (id SERIAL PRIMARY KEY, data DATE, turno TEXT, limite INTEGER, UNIQUE(data, turno))"))
        s.commit()

# ==========================================
# 3. APLICAÇÃO PRINCIPAL
# ==========================================
def main():
    inicializar_banco()
    
    if 'data_sel' not in st.session_state: st.session_state.data_sel = date.today()
    if 'mes_ref' not in st.session_state: st.session_state.mes_ref = date.today().replace(day=1)
    if 'edit_id' not in st.session_state: st.session_state.edit_id = None

    df_bloqueios = conn.query("SELECT data, motivo FROM datas_bloqueadas", ttl=0)
    dict_bloqueios = {row['data']: row['motivo'] for _, row in df_bloqueios.iterrows()}

    df_limites = conn.query("SELECT data, turno, limite FROM limites_vagas", ttl=0)
    dict_limites = {(row['data'], row['turno']): row['limite'] for _, row in df_limites.iterrows()}

    def obter_limite(d, t):
        return dict_limites.get((d, t), 6 if t == "Manhã" else 10)

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown('<div class="logo-ame">AME</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-logo">Assistência Médica Especializada</div>', unsafe_allow_html=True)
        
        aba_novo, aba_busca = st.tabs(["🏥 Novo Agendamento", "🔍 Buscar"])
        
        with aba_novo:
            dt_cad = st.date_input("Selecione a Data", value=st.session_state.data_sel)
            periodo = st.radio("Período do Exame", ["Manhã", "Tarde"], horizontal=True)
            
            limite = obter_limite(dt_cad, periodo)
            res_ocup = conn.query("SELECT COUNT(*) as total FROM agendamentos WHERE data=:d AND turno=:t", params={"d": dt_cad, "t": periodo}, ttl=0)
            ocupadas = res_ocup['total'][0] if not res_ocup.empty else 0
            livres = limite - ocupadas

            if dt_cad in dict_bloqueios:
                motivo = dict_bloqueios[dt_cad]
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
                            fuso_brasilia = timezone(timedelta(hours=-3))
                            agora = datetime.now(fuso_brasilia).strftime("%d/%m/%Y %H:%M")
                            
                            with conn.session as s:
                                s.execute(text("INSERT INTO agendamentos (data, turno, paciente, empresa, observacao, responsavel, registro, status) VALUES (:d,:t,:p,:e,:o,:r,:reg, 'Pendente')"),
                                          {"d":dt_cad, "t":periodo, "p":nome, "e":emp, "o":obs, "r":resp, "reg":agora})
                                s.commit()
                            st.session_state.data_sel = dt_cad
                            st.success("✅ Sucesso!")
                            st.rerun()

        with aba_busca:
            busca = st.text_input("Pesquisar Paciente/Empresa:")
            if busca:
                # CORREÇÃO 1: Prevenção de SQL Injection usando :b (bind param)
                busca_param = f"%{busca}%"
                res_busca = conn.query("SELECT data, turno, paciente, empresa, status FROM agendamentos WHERE paciente ILIKE :b OR empresa ILIKE :b ORDER BY data DESC LIMIT 10", params={"b": busca_param}, ttl=0)
                
                if not res_busca.empty:
                    st.caption("Últimos 10 resultados encontrados:")
                    for _, r_b in res_busca.iterrows():
                        d_format = pd.to_datetime(r_b['data']).strftime('%d/%m/%Y')
                        st.markdown(f"""
                        <div class='busca-card'>
                            <b>{r_b['paciente']}</b><br>
                            🏢 {r_b['empresa']}<br>
                            📅 {d_format} ({r_b['turno']}) | Status: <b>{r_b['status']}</b>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("Nenhum registro encontrado.")

        st.markdown("---")
        
        with st.expander("⚙️ Gerenciar Bloqueios de Agenda"):
            dt_bloq = st.date_input("Data para bloquear", value=st.session_state.data_sel, key="dt_bloq")
            if dt_bloq in dict_bloqueios:
                st.warning(f"Data fechada: {dict_bloqueios[dt_bloq]}")
                if st.button("🔓 Desbloquear", use_container_width=True):
                    with conn.session as s:
                        s.execute(text("DELETE FROM datas_bloqueadas WHERE data=:d"), {"d":dt_bloq})
                        s.commit()
                    st.rerun()
            else:
                motivo_bloq = st.text_input("Motivo", value="Clínica Fechada")
                if st.button("🔒 Bloquear", use_container_width=True):
                    with conn.session as s:
                        s.execute(text("INSERT INTO datas_bloqueadas (data, motivo) VALUES (:d,:m)"), {"d":dt_bloq, "m":motivo_bloq})
                        s.commit()
                    st.rerun()

        with st.expander("⚙️ Gerenciar Vagas / Limites"):
            dt_lim = st.date_input("Data", value=st.session_state.data_sel, key="dt_lim")
            turno_lim = st.selectbox("Turno", ["Manhã", "Tarde"], key="turno_lim")
            limite_atual = obter_limite(dt_lim, turno_lim)
            novo_limite = st.number_input(f"Limite ({turno_lim})", min_value=0, max_value=50, value=limite_atual, step=1)
            if st.button("💾 Salvar Limite", use_container_width=True):
                with conn.session as s:
                    s.execute(text("DELETE FROM limites_vagas WHERE data=:d AND turno=:t"), {"d":dt_lim, "t":turno_lim})
                    s.execute(text("INSERT INTO limites_vagas (data, turno, limite) VALUES (:d,:t,:l)"), {"d":dt_lim, "t":turno_lim, "l":novo_limite})
                    s.commit()
                st.rerun()

    # --- PAINEL PRINCIPAL ---
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

    dias_semana = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]
    cols_header = st.columns(7)
    for i, d in enumerate(dias_semana):
        cols_header[i].markdown(f"<p style='text-align:center; font-weight:700; color:#2E7D32;'>{d}</p>", unsafe_allow_html=True)

    cal = calendar.Calendar(firstweekday=6)
    dias_do_mes = cal.monthdatescalendar(st.session_state.mes_ref.year, st.session_state.mes_ref.month)
    
    df_mes = conn.query("SELECT data, turno FROM agendamentos WHERE data >= :ini AND data <= :fim", 
                        params={"ini":st.session_state.mes_ref, "fim":st.session_state.mes_ref + timedelta(days=31)}, ttl=0)

    for semana in dias_do_mes:
        cols = st.columns(7)
        for i, dia in enumerate(semana):
            with cols[i]:
                if dia.month == st.session_state.mes_ref.month:
                    if dia in dict_bloqueios:
                        motivo_curto = dict_bloqueios[dia][:12] + '...' if len(dict_bloqueios[dia]) > 12 else dict_bloqueios[dia]
                        st.markdown(f"<div class='feriado-box'>{dia.day}<br><small>{motivo_curto}</small></div>", unsafe_allow_html=True)
                    else:
                        m = len(df_mes[(df_mes['data'] == dia) & (df_mes['turno'] == 'Manhã')]) if not df_mes.empty else 0
                        t = len(df_mes[(df_mes['data'] == dia) & (df_mes['turno'] == 'Tarde')]) if not df_mes.empty else 0
                        
                        lim_m = obter_limite(dia, "Manhã")
                        lim_t = obter_limite(dia, "Tarde")
                        
                        label = f"{dia.day}\n\n🌅 M:{m}/{lim_m}\n☀️ T:{t}/{lim_t}"
                        key_label = f"btn_{dia}"
                        btn_type = "primary" if dia == st.session_state.data_sel else "secondary"
                        
                        if st.button(label, key=key_label, type=btn_type, use_container_width=True):
                            st.session_state.data_sel = dia
                            st.rerun()

    st.markdown("---")

    # --- LISTA DE PACIENTES DIÁRIA & DASHBOARD ---
    data_f = st.session_state.data_sel.strftime('%d/%m/%Y')
    
    c_titulo, c_botao_print = st.columns([4, 1])
    with c_titulo:
        st.markdown(f"### 📋 Atendimento do Dia: {data_f}")
    
    with c_botao_print:
        # CORREÇÃO 2: Botão HTML Seguro para impressão (Evita tela branca)
        js_print_dia = """
        <button onclick="window.parent.print()" style="width: 100%; border: 1px solid #2E7D32; background: white; color: #2E7D32; padding: 8px 15px; border-radius: 8px; cursor: pointer; font-weight: 600; font-family: 'Inter', sans-serif; transition: 0.3s; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            🖨️ IMPRIMIR O DIA
        </button>
        <style>
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 10px rgba(46, 125, 50, 0.2);
            }
        </style>
        """
        components.html(js_print_dia, height=50)

    if st.session_state.data_sel in dict_bloqueios:
        st.warning(f"Agenda bloqueada. ({dict_bloqueios[st.session_state.data_sel]})")

    df_dia = conn.query("SELECT * FROM agendamentos WHERE data=:d ORDER BY turno DESC, id ASC", params={"d":st.session_state.data_sel}, ttl=0)
    
    # 📊 PAINEL DE RESUMO RÁPIDO (DASHBOARD)
    if not df_dia.empty:
        tot_dia = len(df_dia)
        tot_pres = len(df_dia[df_dia['status'] == 'Presente'])
        tot_falt = len(df_dia[df_dia['status'] == 'Faltou'])
        tot_pend = len(df_dia[df_dia['status'] == 'Pendente'])
        
        st.markdown("<div style='background-color: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 20px;'>", unsafe_allow_html=True)
        col_res1, col_res2, col_res3, col_res4 = st.columns(4)
        col_res1.metric("📌 Total Agendados", tot_dia)
        col_res2.metric("✅ Presentes", tot_pres)
        col_res3.metric("❌ Faltas", tot_falt)
        col_res4.metric("⏳ Pendentes", tot_pend)
        st.markdown("</div>", unsafe_allow_html=True)

    # ALERTA DE ATRASOS (PISCANTE)
    fuso_brasilia = timezone(timedelta(hours=-3))
    agora = datetime.now(fuso_brasilia)
    
    if st.session_state.data_sel == agora.date():
        limite_hora = agora.replace(hour=8, minute=30, second=0, microsecond=0)
        if agora > limite_hora and not df_dia.empty and 'status' in df_dia.columns:
            faltosos_df = df_dia[(df_dia['turno'] == 'Manhã') & (df_dia['status'] == 'Pendente')]
            if not faltosos_df.empty:
                lista_nomes = ", ".join([str(nome) for nome in faltosos_df['paciente'].tolist() if pd.notnull(nome)])
                alerta_html = f"""
                <style>
                @keyframes alerta-pisca-anim {{
                    0% {{ background-color: #ffebee; color: #c62828; transform: scale(1); box-shadow: 0 0 5px rgba(211,47,47,0.3); border-color: #ffcdd2; }}
                    50% {{ background-color: #d32f2f; color: white; transform: scale(1.02); box-shadow: 0 0 25px rgba(211,47,47,0.9); border-color: #ff0000; }}
                    100% {{ background-color: #ffebee; color: #c62828; transform: scale(1); box-shadow: 0 0 5px rgba(211,47,47,0.3); border-color: #ffcdd2; }}
                }}
                .caixa-alerta-pisca {{
                    animation: alerta-pisca-anim 1.5s infinite;
                    padding: 15px; border-radius: 8px; border: 3px solid #b71c1c; text-align: center; margin-bottom: 20px; font-family: 'Inter', sans-serif;
                }}
                </style>
                <div class="caixa-alerta-pisca">
                    <h3 style='margin-top:0;'>🚨 ATENÇÃO: ATRASO DETECTADO! 🚨</h3>
                    <p style="font-weight: bold;">Já passou das 08:30! Os seguintes funcionários ainda estão PENDENTES:</p>
                    <p style="font-size: 1.3rem; font-weight: 800; text-transform: uppercase;">{lista_nomes}</p>
                </div>
                """
                st.markdown(alerta_html, unsafe_allow_html=True)

    col_m, col_t = st.columns(2)
    
    def exibir_cartao_paciente(r, coluna):
        with coluna:
            # CORREÇÃO 3: Controle Seguro de "NaN" / Vazio nas Observações
            obs_texto = "-"
            if not pd.isna(r['observacao']) and str(r['observacao']).strip() != "":
                obs_texto = str(r['observacao']).strip()

            # ✏️ MODO EDIÇÃO
            if st.session_state.edit_id == r['id']:
                with st.form(key=f"form_edit_{r['id']}"):
                    st.markdown(f"**✏️ Editando Agendamento**")
                    novo_nome = st.text_input("Paciente", str(r['paciente'])).upper()
                    nova_emp = st.text_input("Empresa", str(r['empresa'])).upper()
                    
                    # Previne que exiba "NaN" no input de texto
                    valor_obs_edit = "" if pd.isna(r['observacao']) else str(r['observacao'])
                    nova_obs = st.text_input("Observação", valor_obs_edit)
                    
                    novo_resp = st.text_input("Responsável", str(r['responsavel'])).upper()
                    
                    c_salvar, c_cancelar = st.columns(2)
                    if c_salvar.form_submit_button("💾 Salvar Alterações"):
                        with conn.session as s:
                            # CORREÇÃO 4: Garantir que o ID seja int na hora do UPDATE/DELETE
                            s.execute(text("UPDATE agendamentos SET paciente=:p, empresa=:e, observacao=:o, responsavel=:r WHERE id=:id"), 
                                      {"p":novo_nome, "e":nova_emp, "o":nova_obs, "r":novo_resp, "id": int(r['id'])})
                            s.commit()
                        st.session_state.edit_id = None
                        st.rerun()
                    if c_cancelar.form_submit_button("❌ Cancelar"):
                        st.session_state.edit_id = None
                        st.rerun()
            # 👁️ MODO VISUALIZAÇÃO NORMAL
            else:
                status_atual = r.get('status', 'Pendente')
                cor_borda = "#2E7D32" if status_atual == 'Presente' else "#C62828" if status_atual == 'Faltou' else "#FF9800"
                
                st.markdown(f"""
                <div class="paciente-card" style="border-left: 5px solid {cor_borda};">
                    <b>👤 {r['paciente']}</b> | 🏢 {r['empresa']}<br>
                    <span style="font-size: 0.9em;"><b>📝 OBS:</b> {obs_texto}</span><br>
                    <span style="font-size: 0.8em; color: #666;">✍️ Por: {r['responsavel']} | 🕒 {r['registro']}</span><br>
                    <span style="font-size: 0.85em; font-weight: bold; color: {cor_borda};">Status: {status_atual.upper()}</span>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    if status_atual == 'Pendente':
                        if st.button("✅ Veio", key=f"conf_{r['id']}", help="Presente", use_container_width=True):
                            with conn.session as s:
                                s.execute(text("UPDATE agendamentos SET status='Presente' WHERE id=:id"), {"id": int(r["id"])})
                                s.commit()
                            st.rerun()
                    else:
                        if st.button("🔄 Voltar", key=f"undo_{r['id']}", help="Voltar Status", use_container_width=True):
                            with conn.session as s:
                                s.execute(text("UPDATE agendamentos SET status='Pendente' WHERE id=:id"), {"id": int(r["id"])})
                                s.commit()
                            st.rerun()
                with c2:
                    if status_atual == 'Pendente':
                        if st.button("❌ Faltou", key=f"faltou_{r['id']}", help="Faltou", use_container_width=True):
                            with conn.session as s:
                                s.execute(text("UPDATE agendamentos SET status='Faltou' WHERE id=:id"), {"id": int(r["id"])})
                                s.commit()
                            st.rerun()
                with c3:
                    if st.button("✏️ Editar", key=f"edit_{r['id']}", help="Editar Dados", use_container_width=True):
                        st.session_state.edit_id = r['id']
                        st.rerun()
                with c4:
                    if st.button("🗑️ Del", key=f"del_{r['id']}", help="Remover", use_container_width=True):
                        with conn.session as s:
                            s.execute(text("DELETE FROM agendamentos WHERE id=:id"), {"id": int(r["id"])})
                            s.commit()
                        st.rerun()

    # Distribuindo nas colunas
    with col_m:
        st.markdown("#### 🌅 Período da Manhã")
        lista_m = df_dia[df_dia['turno'] == "Manhã"] if not df_dia.empty else pd.DataFrame()
        if lista_m.empty: st.info("Nenhum paciente agendado.")
        else:
            for _, r in lista_m.iterrows(): exibir_cartao_paciente(r, col_m)

    with col_t:
        st.markdown("#### ☀️ Período da Tarde")
        lista_t = df_dia[df_dia['turno'] == "Tarde"] if not df_dia.empty else pd.DataFrame()
        if lista_t.empty: st.info("Nenhum paciente agendado.")
        else:
            for _, r in lista_t.iterrows(): exibir_cartao_paciente(r, col_t)

    # ==========================================
    # RELATÓRIO MENSAL (PLANILHA)
    # ==========================================
    st.markdown("---")
    st.markdown(f"### 📊 Planilha Mensal: {titulo_mes}")
    
    mes_formatado = f"{st.session_state.mes_ref.year}-{st.session_state.mes_ref.month:02d}"
    df_mes_relatorio = conn.query(f"SELECT data, turno, paciente, empresa, observacao, responsavel, registro, status FROM agendamentos WHERE CAST(data AS TEXT) LIKE '{mes_formatado}-%' ORDER BY data ASC, turno DESC", ttl=0)
    
    if df_mes_relatorio.empty:
        st.info("Nenhum agendamento encontrado para este mês.")
    else:
        df_mes_relatorio = df_mes_relatorio.rename(columns={
            'data': 'Data do Exame', 'turno': 'Turno', 'paciente': 'Paciente',
            'empresa': 'Empresa', 'observacao': 'Observação', 'responsavel': 'Responsável',
            'registro': 'Registrado Em', 'status': 'Status da Presença'
        })
        df_mes_relatorio['Data do Exame'] = pd.to_datetime(df_mes_relatorio['Data do Exame']).dt.strftime('%d/%m/%Y')
        
        st.dataframe(df_mes_relatorio, use_container_width=True, hide_index=True)
        
        col_down, col_print = st.columns([1, 1])
        with col_down:
            csv_data = df_mes_relatorio.to_csv(index=False, sep=';').encode('utf-8-sig')
            st.download_button("📥 Baixar Planilha", data=csv_data, file_name=f"Agendamentos_{titulo_mes.replace(' ', '_')}.csv", mime="text/csv", use_container_width=True)
            
        with col_print:
            html_table = df_mes_relatorio.to_html(index=False).replace('\n', '')
            js_print_code = f"""
            <button onclick="printTable()" style="width: 100%; border: 1px solid #2E7D32; background: white; color: #2E7D32; padding: 5px 15px; border-radius: 8px; cursor: pointer; font-weight: bold; font-family: sans-serif; transition: 0.3s;">
                🖨️ IMPRIMIR PLANILHA
            </button>
            <script>
            function printTable() {{
                var printWin = window.open('', '', 'height=800,width=1000');
                printWin.document.write('<html><head><title>Impressão - {titulo_mes}</title><style>body {{ font-family: sans-serif; }} table {{width:100%; border-collapse: collapse; margin-top: 20px;}} th, td {{border: 1px solid #444; padding: 10px; text-align: left;}} th {{background-color: #f2f2f2;}} h2 {{ color: #1B5E20; text-align: center; }}</style></head><body><h2>Agendamentos - {titulo_mes}</h2>{html_table}</body></html>');
                printWin.document.close();
                setTimeout(function() {{ printWin.print(); printWin.close(); }}, 300);
            }}
            </script>
            """
            components.html(js_print_code, height=50)

if __name__ == "__main__":
    main()
