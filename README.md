# Ketama

Aplicación privada para socios con Python, Django, PostgreSQL y plantillas HTML.
La referencia de alcance es [ESPECIFICACION_PROYECTO.md](ESPECIFICACION_PROYECTO.md).

## Estado actual

Está creado el esqueleto y el modelo `Socio`, vinculado al usuario nativo de
Django. `geneticas` y `comunicacion` aún no tienen funcionalidades.
El espacio de socios incluye acceso, cambio de contraseña, cierre de sesión y
una bienvenida provisional. El panel de gestión conserva su entrada `/admin/`.
La migración `0002_socio_debe_cambiar_password` está preparada sin aplicar.

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

La importación CSV queda pendiente. No se han añadido datos de socios reales.

## Autenticación de socios

- `/acceso/`: número de socio (`User.username`) y contraseña, mediante
  `AuthenticationForm` y `LoginView` de Django.
- `/cambiar-password/`: contraseña actual y nueva contraseña confirmada,
  mediante `PasswordChangeForm` y `PasswordChangeView`.
- `/`: bienvenida provisional, disponible después del cambio obligatorio.
- `/salir/`: cierre de sesión mediante POST con token CSRF.

`Socio.debe_cambiar_password` vale `True` por defecto. La migración añade el
indicador también a los perfiles existentes sin alterar sus contraseñas.
En Admin se puede marcar de nuevo al entregar una contraseña temporal nueva.
Solo un cambio válido de contraseña lo desmarca desde el espacio de socios.
La nueva contraseña debe superar los validadores de Django y ser distinta de
la actual. El cambio conserva la sesión mediante el mecanismo nativo de Django.

`AccesoSociosMiddleware` protege todas las rutas del namespace `socios`:
exige cuenta activa con perfil, rechaza personal y superusuarios, y fuerza el
cambio pendiente antes de acceder a páginas privadas. Las futuras páginas
privadas deben seguir este mismo control de acceso. Los destinos `next` del
login se ignoran para evitar saltos al Admin o fuera del flujo obligatorio.
Las respuestas de socios llevan cabeceras para evitar su almacenamiento en caché.

Los formularios y rutas del Admin son independientes. El middleware de socios
no interviene en `/admin/`; una cuenta de socio sin permisos de personal no puede
entrar en ese panel, y una sesión del Admin no da acceso al espacio de socios.
Se utiliza el motor de autenticación y sesiones nativo de un único proyecto Django.

## Comprobación local del acceso

No se han ejecutado migraciones ni cambiado contraseñas existentes durante esta
implementación. Antes de probar, revisar la migración y ejecutar localmente:

```sh
source .venv/bin/activate
python manage.py check
python manage.py migrate --plan
python manage.py migrate socios
python manage.py runserver
```

Abrir `http://127.0.0.1:8000/acceso/` e introducir el número **0** y su contraseña
actual. No hay que crear otra cuenta ni restablecerla. El perfil existente queda
pendiente de cambio tras la migración. Verificar que abrir `/` directamente
redirige al cambio y que se puede cerrar sesión sin completarlo.

La prueba manual completa implica establecer voluntariamente una contraseña
nueva desde el formulario; esta implementación no realiza ese cambio por sí sola.
Después del cambio, comprobar la bienvenida, cerrar sesión y volver a entrar
con la contraseña nueva. El Admin sigue en `http://127.0.0.1:8000/admin/`.

Las pruebas automatizadas se ejecutan aparte con:

```sh
python manage.py test socios
```

El runner de Django crea una base PostgreSQL de pruebas y aplica allí las
migraciones. Requiere que el usuario de PostgreSQL tenga permiso para crear esa
base. No debe apuntarse su configuración `TEST` a la base local real.
El usuario `0` de estas pruebas es ficticio, creado solo en esa base temporal;
no se consulta ni modifica la cuenta `0` de desarrollo. La suite cubre acceso,
cambio obligatorio, contraseñas inválidas, cuentas inactivas, separación del
Admin, cierre de sesión, CSRF y conservación de la sesión.

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
solo para su propietario y está excluido de Git. La conexión local a PostgreSQL
se configura con `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST` y `PGPORT`.

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

Catálogo, valoraciones, noticias y eventos, PWA, push e importación CSV
se implementarán por separado.
Las carpetas de plantillas y recursos vacías se conservan con `.gitkeep`.
No hay manifiesto, service worker ni lógica PWA todavía.

El despliegue en Railway, el servicio de estáticos en producción, las fotografías
en Railway Object Storage y las copias semanales con retención de cuatro copias
quedan pendientes. Este esqueleto no configura aún un despliegue de producción.
Las imágenes subidas no pertenecen a `static/`.

Nunca incorporar a Git datos reales de socios, CSV privados, contraseñas,
credenciales ni copias de seguridad. Usar datos ficticios para el portfolio.
