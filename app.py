import io
import os
import re
import time
import zipfile
from datetime import datetime

import pandas as pd
import streamlit as st
from PIL import Image

from google import genai
from google.genai import types

st.set_page_config(page_title="Generador de imágenes ", layout="wide")

MODEL_OPTIONS = {
    "Nano Banana 2 — calidad alta": "gemini-3.1-flash-image",
    "Nano Banana 2 Lite — calidad estándar": "gemini-3.1-flash-lite-image",
}
PROMPT_COL_CANDIDATES = ["Prompt de imagen", "Prompt", "prompt","Prompt completo", "Prompt de imagen completo", "prompt completo de imagen", "prompt completo"]
NUM_COL_CANDIDATES = ["Nº", "No", "N°", "Numero", "Número"]
SECCION_COL_CANDIDATES = ["Sección", "Seccion"]
MOMENTO_COL_CANDIDATES = ["Momento del guion", "Momento"]

DEFAULT_KEYWORDS = " "


def find_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def sanitize(text, maxlen=40):
    text = re.sub(r"[^\w\s-]", "", str(text)).strip()
    text = re.sub(r"[\s]+", "_", text)
    return text[:maxlen] if text else "sin_titulo"


def row_needs_reference(prompt_text, keywords):
    prompt_low = prompt_text.lower()
    return any(k.strip().lower() in prompt_low for k in keywords.split(",") if k.strip())


def unique_filename(base_filename, used_filenames):
    """Evita que dos filas con el mismo nombre se pisen entre sí (esto era lo que
    causaba que subieras 200 prompts y salieran 150 imágenes: la fila repetida
    sobreescribía a la anterior sin avisar)."""
    if base_filename not in used_filenames:
        return base_filename, False
    name, ext = os.path.splitext(base_filename)
    n = 2
    candidate = f"{name}_{n}{ext}"
    while candidate in used_filenames:
        n += 1
        candidate = f"{name}_{n}{ext}"
    return candidate, True


def generate_image(client, model_name, prompt_text, reference_images=None, max_retries=3):
    """Llama a la API de Gemini y devuelve bytes PNG o None + mensaje de error."""
    contents = []
    if reference_images:
        contents.extend(reference_images)
    contents.append(prompt_text)

    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    return part.inline_data.data, None
            # No image part returned (posible bloqueo de política de contenido)
            text_parts = [p.text for p in response.candidates[0].content.parts if p.text]
            last_error = "Sin imagen en la respuesta: " + " ".join(text_parts)[:200]
        except Exception as e:
            last_error = str(e)[:200]
            time.sleep(2 * (attempt + 1))
    return None, last_error


def main():
    st.title("Generador de imágenes")
    st.caption(
        "Sube el Excel de prompts, opcionalmente una foto de referencia del personaje "
        "principal para mantener su consistencia, y genera todas las imágenes."
    )

    with st.sidebar:
        st.header("Configuración")
        api_key = st.text_input("Gemini API key", type="password", help="Consíguela gratis en aistudio.google.com")
        model_label = st.selectbox("Calidad / modelo", list(MODEL_OPTIONS.keys()))
        model_name = MODEL_OPTIONS[model_label]
        keywords = st.text_area(
            "Palabras clave para detectar filas del personaje principal",
            value=DEFAULT_KEYWORDS,
            help="Si el texto del prompt contiene alguna de estas palabras, se le adjuntará la imagen de referencia.",
        )
        delay = st.slider("Pausa entre imágenes (segundos)", 0, 10, 2)

    col1, col2 = st.columns(2)
    with col1:
        excel_file = st.file_uploader("Excel de prompts (.xlsx)", type=["xlsx"])
    with col2:
        ref_files = st.file_uploader(
            "Imagen(es) de referencia del personaje principal (opcional, recomendado)",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True,
        )

    if not excel_file:
        st.info("Sube el archivo de Excel para comenzar.")
        return

    df = pd.read_excel(excel_file)
    prompt_col = find_col(df, PROMPT_COL_CANDIDATES)
    num_col = find_col(df, NUM_COL_CANDIDATES)
    seccion_col = find_col(df, SECCION_COL_CANDIDATES)
    momento_col = find_col(df, MOMENTO_COL_CANDIDATES)

    if prompt_col is None:
        st.error("No encontré una columna de prompt (esperaba algo como 'Prompt de imagen').")
        return

    st.success(f"{len(df)} filas detectadas. Columna de prompt: '{prompt_col}'.")

    reference_images = None
    if ref_files:
        reference_images = [Image.open(f) for f in ref_files]
        st.image(reference_images, width=120, caption=[f.name for f in ref_files])

    rows_with_ref = sum(1 for _, r in df.iterrows() if row_needs_reference(str(r[prompt_col]), keywords))
    st.write(f"Filas que recibirán la imagen de referencia: **{rows_with_ref}** de {len(df)}.")

    with st.expander("Vista previa de las primeras filas"):
        st.dataframe(df.head(10))

    if "generated" not in st.session_state:
        st.session_state.generated = {}  # filename -> bytes
    if "run_log" not in st.session_state:
        st.session_state.run_log = []  # lista de dicts, una entrada por fila del Excel

    start = st.button("🚀 Generar imágenes", type="primary", disabled=not api_key)
    if not api_key:
        st.warning("Ingresa tu Gemini API key en la barra lateral para poder generar.")

    if start:
        client = genai.Client(api_key=api_key)
        progress = st.progress(0.0)
        status = st.empty()
        log_box = st.container()
        total = len(df)

        # Reinicia todo en cada corrida nueva para que el reporte no mezcle
        # resultados de un Excel con otro.
        st.session_state.generated = {}
        st.session_state.run_log = []

        for i, (_, row) in enumerate(df.iterrows()):
            fila_excel = i + 2  # +2: fila 1 es encabezado y pandas empieza en 0
            entry = {
                "fila_excel": fila_excel,
                "filename": None,
                "estado": None,
                "detalle": "",
            }
            try:
                prompt_text = str(row[prompt_col])
                num_raw = row[num_col] if num_col else i + 1
                try:
                    num = int(num_raw)
                except (ValueError, TypeError):
                    num = i + 1
                    entry["detalle"] = f"Nº inválido en el Excel ('{num_raw}'), se usó {num} en su lugar. "
                seccion = sanitize(row[seccion_col]) if seccion_col else "seccion"
                momento = sanitize(row[momento_col]) if momento_col else ""
                base_filename = f"{num:03d}_{seccion}_{momento}.png"
                filename, was_renamed = unique_filename(base_filename, st.session_state.generated.keys())
                if was_renamed:
                    entry["detalle"] += f"Nombre duplicado de '{base_filename}', renombrado para no perder la imagen. "
                entry["filename"] = filename

                status.write(f"Generando {i + 1}/{total}: {filename}")

                refs = reference_images if row_needs_reference(prompt_text, keywords) else None
                img_bytes, error = generate_image(client, model_name, prompt_text, refs)

                if img_bytes:
                    st.session_state.generated[filename] = img_bytes
                    entry["estado"] = "OK"
                    log_box.write(f"✅ {filename}")
                else:
                    entry["estado"] = "ERROR_API"
                    entry["detalle"] += error or "Sin detalle"
                    log_box.write(f"❌ {filename} — {error}")

            except Exception as e:
                entry["estado"] = "ERROR_FILA"
                entry["detalle"] += f"Excepción al procesar la fila: {e}"
                log_box.write(f"⚠️ Fila {fila_excel} — error inesperado: {e}")

            st.session_state.run_log.append(entry)
            progress.progress((i + 1) / total)
            time.sleep(delay)

        status.write("¡Listo!")

    if st.session_state.run_log:
        log_df = pd.DataFrame(st.session_state.run_log)
        ok = (log_df["estado"] == "OK").sum()
        errores = (log_df["estado"] != "OK").sum()
        duplicados = log_df["detalle"].str.contains("renombrado", na=False).sum()

        st.subheader("📋 Reporte de la corrida")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Filas en el Excel", len(log_df))
        c2.metric("Imágenes generadas", ok)
        c3.metric("Fallidas", errores)
        c4.metric("Nombres duplicados corregidos", duplicados)

        if errores > 0:
            st.warning(f"{errores} fila(s) no generaron imagen. Revisa el detalle abajo.")
        with st.expander("Ver reporte completo (una fila por prompt del Excel)", expanded=errores > 0):
            st.dataframe(log_df, use_container_width=True)

        log_csv = log_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar reporte (CSV)",
            data=log_csv,
            file_name=f"reporte_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )

    if st.session_state.generated:
        st.subheader(f"Imágenes generadas: {len(st.session_state.generated)}")
        cols = st.columns(4)
        for i, (fname, data) in enumerate(st.session_state.generated.items()):
            with cols[i % 4]:
                st.image(data, caption=fname, use_container_width=True)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, data in st.session_state.generated.items():
                zf.writestr(fname, data)
            if st.session_state.run_log:
                zf.writestr("reporte.csv", pd.DataFrame(st.session_state.run_log).to_csv(index=False))
        buf.seek(0)

        st.download_button(
            "⬇️ Descargar todas + reporte (ZIP)",
            data=buf,
            file_name=f"imagenes_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
            mime="application/zip",
        )


if __name__ == "__main__":
    main()