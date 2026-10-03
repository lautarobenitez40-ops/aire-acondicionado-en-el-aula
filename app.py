"""
Gemelo digital de un aula: temperatura interior con alumnos y aire acondicionado.

Modelo de parámetros concentrados (1 zona, balance de energía):

    C * dT/dt = Q_personas + Q_luces + Q_equipos + Q_solar
                + (UA_envolvente + UA_ventilacion) * (T_ext - T)
                - Q_aire

    C = rho * cp * V * factor_masa     (aire + mobiliario + muros interiores)

Ejecutar:  streamlit run app.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------------
RHO_AIRE = 1.2          # kg/m3
CP_AIRE = 1005.0        # J/(kg K)
FG_A_W = 1.163          # 1 frigoría/h = 1 kcal/h = 1.163 W
DT = 60.0               # paso de simulación [s]

st.set_page_config(page_title="Gemelo digital - Aula", page_icon="🌡️", layout="wide")


# ----------------------------------------------------------------------------
# Modelo
# ----------------------------------------------------------------------------
def temperatura_exterior(hora_decimal, t_media, amplitud):
    """Ciclo diario senoidal: mínimo ~3 h, máximo ~15 h."""
    return t_media + amplitud * np.sin(2 * np.pi * (hora_decimal - 9) / 24)


def simular(p, con_aire):
    """Devuelve un DataFrame con la evolución de la temperatura del aula."""
    volumen = p["largo"] * p["ancho"] * p["alto"]
    area_piso = p["largo"] * p["ancho"]
    c_term = RHO_AIRE * CP_AIRE * volumen * p["factor_masa"]  # J/K

    ua_env = p["u_muro"] * p["area_muro"] + p["u_vidrio"] * p["area_vidrio"]  # W/K
    ua_vent = RHO_AIRE * CP_AIRE * volumen * p["ach"] / 3600.0                # W/K

    q_personas = p["alumnos"] * p["w_persona"] + p["w_docente"]
    q_luces = p["w_luces_m2"] * area_piso
    q_solar = p["rad_solar"] * p["area_vidrio"] * p["shgc"]
    q_internas = q_personas + q_luces + p["w_equipos"]

    cap_aire_w = p["cap_fg"] * FG_A_W

    n = int(p["duracion_h"] * 3600 / DT)
    t = np.zeros(n + 1)
    t_ext = np.zeros(n + 1)
    q_ac = np.zeros(n + 1)
    t[0] = p["t_inicial"]
    ac_encendido = False

    for i in range(n + 1):
        hora = p["hora_inicio"] + i * DT / 3600.0
        t_ext[i] = temperatura_exterior(hora, p["t_ext_media"], p["t_ext_amp"])

        # Termostato con histéresis
        if con_aire and (i * DT / 60.0) >= p["min_encendido"]:
            if t[i] > p["consigna"] + p["histeresis"]:
                ac_encendido = True
            elif t[i] < p["consigna"] - p["histeresis"]:
                ac_encendido = False
        else:
            ac_encendido = False
        q_ac[i] = cap_aire_w if ac_encendido else 0.0

        if i == n:
            break
        flujo = (
            q_internas
            + q_solar
            + (ua_env + ua_vent) * (t_ext[i] - t[i])
            - q_ac[i]
        )
        t[i + 1] = t[i] + DT * flujo / c_term

    df = pd.DataFrame(
        {
            "minuto": np.arange(n + 1) * DT / 60.0,
            "T_aula": t,
            "T_exterior": t_ext,
            "Q_aire_W": q_ac,
        }
    )
    df["hora"] = p["hora_inicio"] + df["minuto"] / 60.0
    info = {
        "ganancia_interna_W": q_internas,
        "ganancia_solar_W": q_solar,
        "ua_total_WK": ua_env + ua_vent,
        "tau_h": c_term / (ua_env + ua_vent) / 3600.0,
        "volumen": volumen,
    }
    return df, info


# ----------------------------------------------------------------------------
# Interfaz: parámetros
# ----------------------------------------------------------------------------
st.title("🌡️ Gemelo digital: temperatura de un aula")
st.caption("Modelo térmico de una zona. Modificá los parámetros y compará con y sin aire acondicionado.")

with st.sidebar:
    st.header("Aula")
    largo = st.slider("Largo [m]", 4.0, 15.0, 9.0, 0.5)
    ancho = st.slider("Ancho [m]", 3.0, 12.0, 6.0, 0.5)
    alto = st.slider("Alto [m]", 2.4, 4.5, 3.0, 0.1)
    alumnos = st.slider("Alumnos", 0, 60, 30)
    w_persona = st.number_input("Calor sensible por persona [W]", 50, 150, 75)
    w_docente = st.number_input("Docente [W]", 0, 150, 75)

    st.header("Envolvente y clima")
    area_muro = st.number_input("Área de muros exteriores opacos [m²]", 0.0, 200.0, 30.0)
    area_vidrio = st.number_input("Área de ventanas [m²]", 0.0, 60.0, 8.0)
    u_muro = st.number_input("U muro [W/m²K]", 0.2, 4.0, 1.8)
    u_vidrio = st.number_input("U vidrio [W/m²K]", 1.0, 6.0, 5.0)
    shgc = st.slider("Factor solar del vidrio (0-1)", 0.1, 1.0, 0.6, 0.05)
    rad_solar = st.slider("Radiación solar sobre ventanas [W/m²]", 0, 800, 250, 10)
    ach = st.slider("Ventilación / infiltración [renov/h]", 0.0, 10.0, 2.0, 0.5)
    hora_inicio = st.slider("Hora de inicio de clase", 6.0, 20.0, 14.0, 0.5)
    t_ext_media = st.slider("Temp. exterior media [°C]", -5.0, 40.0, 30.0, 0.5)
    t_ext_amp = st.slider("Amplitud diaria exterior [°C]", 0.0, 12.0, 6.0, 0.5)
    t_inicial = st.slider("Temp. inicial del aula [°C]", 5.0, 40.0, 28.0, 0.5)

    st.header("Otras cargas")
    w_luces_m2 = st.slider("Iluminación [W/m²]", 0, 25, 10)
    w_equipos = st.number_input("Equipos (proyector, PC) [W]", 0, 5000, 300)
    factor_masa = st.slider("Masa térmica (múltiplo del aire)", 1.0, 20.0, 6.0, 0.5,
                            help="Equivalente de mobiliario y muros interiores. Más alto = el aula tarda más en cambiar.")

    st.header("Aire acondicionado")
    cap_fg = st.slider("Capacidad [frigorías/h]", 0, 12000, 4500, 250)
    consigna = st.slider("Temperatura de consigna [°C]", 16.0, 28.0, 24.0, 0.5)
    histeresis = st.slider("Histéresis ± [°C]", 0.1, 2.0, 0.5, 0.1)
    min_encendido = st.slider("Minuto de encendido", 0, 240, 0, 5)
    cop = st.slider("COP (eficiencia)", 2.0, 5.0, 3.0, 0.1)

    st.header("Simulación")
    duracion_h = st.slider("Duración [h]", 1.0, 12.0, 4.0, 0.5)
    t_confort = st.slider("Umbral de confort [°C]", 22.0, 30.0, 26.0, 0.5)

params = dict(
    largo=largo, ancho=ancho, alto=alto, alumnos=alumnos, w_persona=w_persona,
    w_docente=w_docente, area_muro=area_muro, area_vidrio=area_vidrio,
    u_muro=u_muro, u_vidrio=u_vidrio, shgc=shgc, rad_solar=rad_solar, ach=ach,
    hora_inicio=hora_inicio, t_ext_media=t_ext_media, t_ext_amp=t_ext_amp,
    t_inicial=t_inicial, w_luces_m2=w_luces_m2, w_equipos=w_equipos,
    factor_masa=factor_masa, cap_fg=cap_fg, consigna=consigna,
    histeresis=histeresis, min_encendido=min_encendido, duracion_h=duracion_h,
)

df_sin, info = simular(params, con_aire=False)
df_con, _ = simular(params, con_aire=True)

# ----------------------------------------------------------------------------
# Resultados
# ----------------------------------------------------------------------------
def minutos_sobre(df, umbral):
    return float((df["T_aula"] > umbral).sum() * DT / 60.0)


energia_kwh = (df_con["Q_aire_W"].sum() * DT / 3600.0) / 1000.0 / cop
horas_encendido = (df_con["Q_aire_W"] > 0).sum() * DT / 3600.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("T final sin aire", f"{df_sin['T_aula'].iloc[-1]:.1f} °C")
c2.metric("T final con aire", f"{df_con['T_aula'].iloc[-1]:.1f} °C",
          delta=f"{df_con['T_aula'].iloc[-1] - df_sin['T_aula'].iloc[-1]:.1f} °C",
          delta_color="inverse")
c3.metric("Min. sobre confort (sin → con)",
          f"{minutos_sobre(df_sin, t_confort):.0f} → {minutos_sobre(df_con, t_confort):.0f}")
c4.metric("Consumo eléctrico del aire", f"{energia_kwh:.2f} kWh",
          help=f"Encendido {horas_encendido:.1f} h")

fig = go.Figure()
fig.add_trace(go.Scatter(x=df_sin["hora"], y=df_sin["T_aula"], name="Sin aire",
                         line=dict(color="#d9534f", width=3)))
fig.add_trace(go.Scatter(x=df_con["hora"], y=df_con["T_aula"], name="Con aire",
                         line=dict(color="#0275d8", width=3)))
fig.add_trace(go.Scatter(x=df_sin["hora"], y=df_sin["T_exterior"], name="Exterior",
                         line=dict(color="gray", dash="dot")))
fig.add_hline(y=t_confort, line_dash="dash", line_color="orange",
              annotation_text="Umbral de confort", annotation_position="top left")
fig.add_hline(y=consigna, line_dash="dash", line_color="green",
              annotation_text="Consigna", annotation_position="bottom left")
fig.update_layout(
    xaxis_title="Hora del día", yaxis_title="Temperatura [°C]",
    height=480, margin=dict(l=10, r=10, t=30, b=10),
    legend=dict(orientation="h", y=1.08),
)
st.plotly_chart(fig, use_container_width=True)

with st.expander("Balance térmico y datos del modelo"):
    a, b, c = st.columns(3)
    a.metric("Ganancia interna (personas+luces+equipos)", f"{info['ganancia_interna_W']:.0f} W")
    b.metric("Ganancia solar", f"{info['ganancia_solar_W']:.0f} W")
    c.metric("Capacidad del aire", f"{cap_fg * FG_A_W:.0f} W")
    a.metric("UA total (envolvente + ventilación)", f"{info['ua_total_WK']:.0f} W/K")
    b.metric("Constante de tiempo", f"{info['tau_h']:.1f} h")
    c.metric("Volumen del aula", f"{info['volumen']:.0f} m³")

    fig2 = go.Figure(go.Scatter(x=df_con["hora"], y=df_con["Q_aire_W"],
                                fill="tozeroy", name="Potencia frigorífica"))
    fig2.update_layout(xaxis_title="Hora del día", yaxis_title="Q aire [W]",
                       height=250, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)

with st.expander("Descargar datos"):
    out = df_sin[["hora", "T_exterior"]].copy()
    out["T_sin_aire"] = df_sin["T_aula"]
    out["T_con_aire"] = df_con["T_aula"]
    out["Q_aire_W"] = df_con["Q_aire_W"]
    st.dataframe(out.iloc[::10], use_container_width=True)
    st.download_button("Descargar CSV", out.to_csv(index=False).encode("utf-8"),
                       "simulacion_aula.csv", "text/csv")
