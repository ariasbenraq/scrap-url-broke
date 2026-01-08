# scrap-url-broke

## Descripción
Script para generar un reporte CSV con enlaces internos y externos encontrados en los posts de un blog con estructura Wix.

## Requisitos
- Python 3.10+.
- Dependencias:
  - `requests`
  - `beautifulsoup4`
  - `lxml`

### Instalación de dependencias
```bash
python -m venv .venv
source .venv/bin/activate
pip install requests beautifulsoup4 lxml
```

## Variables de entorno
Este proyecto **no requiere variables de entorno** para ejecutarse.

## Ejecución
```bash
python check_blog_links.py
```

Salida esperada:
- Archivo `reporte_seo_posts.csv` en el directorio raíz.
- Mensaje en consola: `Reporte generado: reporte_seo_posts.csv`.

## Cambiar el sitio a analizar (otro Wix con misma estructura)
Si quieres analizar un sitio distinto (pero con la misma estructura de Wix), actualiza estas constantes en `check_blog_links.py`:

- `BASE_SITE`: dominio base (ej. `https://www.otrositio.com`).
- `BLOG_INDEX_URL`: URL de índice de posts (ej. `https://www.otrositio.com/post/`).
- `SITEMAP_URLS`: lista de sitemaps del nuevo dominio.

Además, modifica la función `classify_link` para que el dominio del nuevo sitio se considere interno. Actualmente valida `tusitiazo.com`:

```python
if parsed.netloc.endswith("tusitiazo.com"):
    return "internal"
```

Cámbialo por el dominio del nuevo sitio, por ejemplo:

```python
if parsed.netloc.endswith("otrositio.com"):
    return "internal"
```

Con eso, el script seguirá detectando los posts, extrayendo enlaces y generando el CSV para el nuevo sitio.
