# Generador de imágenes — De Cero a Icono

App web sencilla: el cliente sube el Excel de prompts (y opcionalmente una foto
de referencia del protagonista) y la app genera todas las imágenes usando la
API de Gemini (Nano Banana 2 / `gemini-3.1-flash-image`), que soporta hasta 14
imágenes de referencia para mantener la consistencia de un personaje entre
generaciones.

## 1. Conseguir una API key (gratis para empezar)

1. Entra a https://aistudio.google.com
2. Inicia sesión con una cuenta de Google.
3. Ve a "Get API key" → "Create API key".
4. Copia la key (empieza con algo como `AIza...`).

Google da crédito gratuito de prueba; después se cobra por uso
(aprox. $0.067 USD por imagen estándar con este modelo — 142 imágenes
≈ $9-10 USD).

## 2. Instalar y correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

Se abrirá en el navegador en `http://localhost:8501`.

## 3. Uso

1. Pega la API key en la barra lateral.
2. Sube el Excel de prompts (debe tener una columna con el texto del prompt,
   por ejemplo "Prompt de imagen").
3. (Recomendado) Sube 1-3 fotos de referencia del personaje principal —
   pueden ser una recreación/actor generado una sola vez, o una imagen que
   ya te guste de él. Ajusta las "palabras clave" en la barra lateral para
   que la app sepa en qué filas usar esa referencia (por defecto busca
   "Lorenzo", "joven de 18 años", etc. — edítalas si tu Excel usa otros
   términos).
4. Click en "Generar imágenes". La barra de progreso muestra el avance;
   cada imagen tarda unos segundos.
5. Al terminar, descarga el ZIP con todas las imágenes nombradas
   `001_SECCION_momento.png`, `002_...`, etc.

## 4. Publicarla para que el cliente la use sin tu computadora

La forma más rápida y gratuita es **Streamlit Community Cloud**:

1. Sube estos 3 archivos (`app.py`, `requirements.txt`, este README) a un
   repositorio de GitHub.
2. Entra a https://share.streamlit.io, conecta el repo y despliega.
3. Comparte el link con el cliente — él pone su propia API key cada vez que
   la usa (nunca se guarda en el servidor).

Alternativas si prefieres no depender de GitHub: Hugging Face Spaces o
Render, ambas también gratuitas para este tamaño de app.

## Notas importantes

- **Personajes reales/históricos**: algunos generadores restringen crear
  imágenes fotorrealistas de personas reales identificables. Si Gemini
  rechaza alguna fila por esto, esa fila queda marcada con ❌ en el log y
  puedes reintentarla suavizando el prompt (ej. "hombre joven que representa
  a un empresario mexicano de los años 30" en vez del nombre propio).
- **Reintentos**: si una imagen falla por error de red, la app reintenta
  automáticamente 3 veces antes de marcarla como fallida.
- **Costos**: puedes bajar el costo cambiando `MODEL_NAME` en `app.py` a un
  modelo más barato si la calidad te sigue conviniendo — revisa
  https://ai.google.dev/pricing para las tarifas vigentes.
