"""Fail-closed OIDC authentication for the Streamlit dashboard.

Configure [auth] in .streamlit/secrets.toml or through Streamlit secrets.
Only set WEAVERS_AUTH_MODE=disabled in a trusted local test environment.
"""
import os
import streamlit as st


def require_login() -> None:
    mode = os.getenv("WEAVERS_AUTH_MODE", "required").lower()
    if mode != "required":
        if mode == "disabled" and os.getenv("WEAVERS_ALLOW_INSECURE_LOCAL") == "1":
            st.sidebar.warning("AUTH DESACTIVADA — no publicar esta configuración.")
            return
        st.error("Configuración de autenticación inválida. Acceso denegado.")
        st.stop()

    if not st.user.is_logged_in:
        st.title("Weavers Logistic")
        st.write("Accede con tu proveedor de identidad para consultar datos comerciales.")
        if st.button("Iniciar sesión", type="primary"):
            st.login()
        st.stop()

    allowed = {x.strip().casefold() for x in os.getenv("WEAVERS_ALLOWED_EMAILS", "").split(",") if x.strip()}
    email = str(getattr(st.user, "email", "") or "").strip().casefold()
    # Identity-provider authentication alone is insufficient for an internal console.
    if not allowed or not email or email not in allowed:
        st.error("Usuario sin autorización para acceder a esta consola.")
        if st.button("Cerrar sesión"):
            st.logout()
        st.stop()
    with st.sidebar:
        st.caption(f"Sesión: {email}")
        if st.button("Cerrar sesión", key="weavers_logout"):
            st.logout()
