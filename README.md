# Ketama

Aplicación privada para socios con Python, Django, PostgreSQL y plantillas HTML.
La referencia de alcance es [ESPECIFICACION_PROYECTO.md](ESPECIFICACION_PROYECTO.md).

## Estado actual

Está creado el esqueleto y el modelo `Socio`, vinculado al usuario nativo de
Django. `geneticas` y `comunicacion` aún no tienen funcionalidades.
Las rutas propias de estas aplicaciones aún no se conectan.
La única ruta configurada es `/admin/`, con el administrador estándar de Django.
La raíz `/` devuelve 404 hasta que se implemente la interfaz.

La migración inicial de `socios` está preparada pero no se ha aplicado.

## Gestión de socios

Tras revisar y aplicar la migración en una fase autorizada, los socios se
gestionarán desde **Autenticación y autorización → Usuarios** en Django Admin.
Al crear un usuario, indicar su número de socio en el nombre de usuario y
rellenar el perfil con nombre completo y teléfono. El número conserva ceros
iniciales y su unicidad la garantiza el usuario nativo.

La contraseña se gestiona con los formularios estándar y el hash de Django.
La casilla **Activo** habilita o deshabilita la autenticación. Las cuentas de
socios deben mantener desmarcadas las opciones de personal y superusuario.
El administrador puede existir sin perfil de socio. No se crean perfiles
automáticamente para todas las cuentas existentes.

Las pantallas de login de socios, el cambio obligatorio de contraseña inicial
y la importación CSV quedan pendientes. No se han añadido datos de socios reales.

## Estructura

- `config/`: ajustes, rutas principales y entradas WSGI/ASGI.
- `socios/`: perfil de socio y gestión conjunta con la cuenta desde Admin.
- `geneticas/`: futuro catálogo y valoraciones.
- `comunicacion/`: futuras noticias, eventos y notificaciones manuales.
- `templates/`: base HTML y espacios para las plantillas de cada sección.
- `static/`: CSS, JavaScript mínimo e iconos propios de la interfaz.
- Cada aplicación contiene `migrations/` y `tests/`; `socios` incluye su migración
  inicial y pruebas de validación del perfil sin base de datos.

## Requisitos pendientes de preparar

- Python 3.12 o posterior compatible con Django 5.2.
- Las dependencias fijadas en `requirements.txt`: Django, Psycopg con su
  distribución binaria y `python-dotenv` para cargar las variables locales.
- Un servidor PostgreSQL con una base de datos y un usuario para desarrollo.

Las versiones de referencia se consultaron en las fuentes oficiales:
[Django](https://www.djangoproject.com/download/) y
[Psycopg](https://pypi.org/project/psycopg/).

## Configuración local

`config/settings.py` carga automáticamente el archivo `.env` de la raíz con
`python-dotenv`. Las variables ya definidas en el entorno tienen prioridad.
Los valores se leen literalmente, sin interpolación de `${VARIABLE}`.
No es necesario ejecutar `source .env`.

Se ha generado un `.env` local con una `SECRET_KEY` aleatoria privada, `DEBUG=True`
y los hosts locales permitidos. El archivo tiene permisos de lectura/escritura
solo para su propietario y está excluido de Git. No contiene configuración de
PostgreSQL; esa preparación queda para una fase posterior.

En otro equipo, copiar `.env.example` a `.env` y generar una clave privada propia.
Los valores con espacios o caracteres especiales pueden ir entre comillas.
En Railway se definirán directamente como variables del servicio, sin subir `.env`.
`DEBUG` está desactivado por defecto; el ejemplo lo activa solo para desarrollo.
Sin `SECRET_KEY` el proyecto muestra un error de configuración.
La base de datos es siempre PostgreSQL; no se utiliza SQLite.

Una vez instalado el entorno, `python manage.py check` permitirá comprobar la
configuración sin aplicar migraciones. El arranque local se hará con
`python manage.py runserver` después de preparar la base de datos en su fase
correspondiente. `check` no configura PostgreSQL ni aplica migraciones.

## Fases posteriores

Acceso y administración de socios, catálogo, valoraciones, noticias y eventos,
PWA, push e importación CSV se implementarán por separado.
Las carpetas de plantillas y recursos vacías se conservan con `.gitkeep`.
No hay manifiesto, service worker ni lógica PWA todavía.

El despliegue en Railway, el servicio de estáticos en producción, las fotografías
en Railway Object Storage y las copias semanales con retención de cuatro copias
quedan pendientes. Este esqueleto no configura aún un despliegue de producción.
Las imágenes subidas no pertenecen a `static/`.

Nunca incorporar a Git datos reales de socios, CSV privados, contraseñas,
credenciales ni copias de seguridad. Usar datos ficticios para el portfolio.
