# scrap-url-broke-&-SEO-Links

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
python check_blog_links.py [test|full|audit]
```

Salida esperada:
- Archivos CSV en la carpeta `Reports`, con timestamp en el nombre:
  - `enlaces_blog_YYYYMMDDHHMMSS.csv`
  - `seo_posts_YYYYMMDDHHMMSS.csv`
- Archivo CSV en la carpeta `Auditoria` cuando se usa el modo `audit`:
  - `auditoria_nombre_del_sitio_YYYYMMDDHHMMSS.csv`
- Mensajes en consola del tipo: `Reporte generado: Reports/enlaces_blog_YYYYMMDDHHMMSS.csv`.
Durante la ejecución se solicita la URL base en consola (Enter usa el valor por defecto).

### Modo auditoría (sitio completo)
El modo `audit` consulta los sitemaps configurados y genera un reporte por página con (excluye la sección `/post/`):
- Etiquetas H1, H2, H3.
- Párrafos (`<p>`).
- `alt` y nombres de archivo de imágenes.
- URLs internas detectadas.
- Código de estado HTTP, título y metadescripción.

Para ejecutarlo:
```bash
python check_blog_links.py audit
```

## Cambiar el sitio a analizar (otro Wix con misma estructura)
Cuando ejecutes el script, ingresa la URL base cuando lo solicite la consola. El script deriva automáticamente los sitemaps y el dominio interno a partir de esa URL.
