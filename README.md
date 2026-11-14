# Ketama

Aplicación privada para socios con Python, Django, PostgreSQL y plantillas HTML.
La referencia de alcance es [ESPECIFICACION_PROYECTO.md](ESPECIFICACION_PROYECTO.md).

## Estado actual

Está creado el esqueleto y el modelo `Socio`, vinculado al usuario nativo de
Django. `geneticas` y `comunicacion` aún no tienen funcionalidades.
El espacio de socios incluye acceso, cambio de contraseña, cierre de sesión y
una bienvenida provisional. El panel de gestión conserva su entrada `/admin/`.
La migración `0004_socio_estado` está preparada sin aplicar.

## Gestión de socios

Tras revisar y aplicar la migración en una fase autorizada, los socios se
gestionarán desde **Autenticación y autorización → Usuarios** en Django Admin.
Al crear un usuario, indicar su número de socio en el nombre de usuario y
rellenar el perfil con nombre completo y, opcionalmente, teléfono. El número conserva ceros
iniciales y su unicidad la garantiza el usuario nativo.

La contraseña se gestiona con los formularios estándar y el hash de Django.
La casilla **Activo** habilita o deshabilita la autenticación. Las cuentas de
socios deben mantener desmarcadas las opciones de personal y superusuario.
El administrador puede existir sin perfil de socio. No se crean perfiles
automáticamente para todas las cuentas existentes.

El perfil tiene un **Estado del socio** independiente de la casilla **Activo**
del usuario: `activo` permite usar la aplicación y `caducado` permite iniciar
sesión pero solo muestra el aviso de cuota caducada, después del cambio obligatorio
de contraseña si está pendiente. Para renovar manualmente, editar el usuario en
Admin y cambiar el estado de su perfil a `activo`. No hace falta cambiar su
contraseña ni deshabilitar/habilitar su cuenta. La lista de usuarios muestra y
filtra este estado. El acceso administrativo mantiene sus permisos habituales.

Por seguridad, el valor inicial del estado es `caducado`. Al aplicar la migración,
todos los perfiles existentes quedan restringidos hasta revisar su estado o
recuperarlo del CSV. No se modifica ningún otro dato ni hash de contraseña.
Este control sustituye la regla inicial que solo usaba el estado como filtro;
no se implementan fechas de caducidad, pagos ni renovación automática.

El comando de importación CSV está preparado; no se ha ejecutado ninguna
importación real durante su desarrollo.

## Importación inicial desde CSV

El comando `importar_socios` lee directamente el archivo indicado, sin copiarlo.
Requiere UTF-8 (admite BOM), separador `;` y exactamente las columnas `ESTADO`,
`NºSocio`, `NOMBRE`, `APELLIDOS` y `TELEFONO` (pueden cambiar de orden).
El CSV real debe permanecer fuera de Git; las reglas existentes de `.gitignore`
excluyen los archivos CSV. El comando no cambia esas reglas ni añade archivos a Git.

Simulación, sin escrituras en la base de datos:

```sh
source .venv/bin/activate
python manage.py importar_socios "archivo_socios.csv" --dry-run
```

Sustituir el nombre de ejemplo por la ruta del archivo real. La simulación
necesita acceso a PostgreSQL para detectar usuarios existentes. Muestra únicamente
recuentos: filas, candidatos, inactivos, duplicados, errores y cuentas protegidas.

Reglas aplicadas:

- Solo `activo` y `caducado` crean cuentas habilitadas, sin permisos de personal
  ni superusuario. Se ignoran espacios exteriores y mayúsculas en los estados.
  El estado del CSV se conserva en `Socio.estado`; la caducidad no cambia
  `User.is_active` ni impide iniciar sesión.
- `inactivo` y `expulsado` se omiten y suman al contador de descartados por
  inactividad, sin considerarse errores ni crear cuentas.
- Se unen nombre y apellidos, normalizando los espacios del nombre completo.
  El teléfono se conserva como texto, incluidos ceros iniciales, signos y
  espacios internos. El teléfono es opcional: una celda vacía o con espacios
  se guarda como `""`, nunca como `NULL`. Las cinco columnas siguen siendo
  obligatorias; número de socio, nombre y apellidos deben estar cumplimentados.
- El número de socio debe contener dígitos ASCII y se conserva como texto,
  incluidos ceros iniciales. `00125` y `125` son identificadores distintos.
- Se descarta el número `0` siempre. No se actualizan cuentas existentes,
  tengan o no perfil de socio, ni sus contraseñas, permisos o estado.
- Ante duplicados dentro del CSV, se conserva la primera fila válida para
  cada número; las repeticiones posteriores se cuentan como duplicados.
- Se validan columnas, estado, campos vacíos, longitudes de los modelos,
  caracteres de control y un nombre utilizable para la contraseña.
  Las filas inactivas o expulsadas se descartan antes de validar sus datos personales.
- La contraseña temporal utiliza el campo `NOMBRE` completo, la primera palabra
  de `APELLIDOS` y el número de socio. La normalización Unicode elimina tildes y conserva solo letras y
  dígitos ASCII en minúsculas: se eliminan espacios, guiones, apóstrofos y todos
  los demás signos o caracteres que no produzcan letras/dígitos ASCII.
  Por ejemplo, `NOMBRE=María`, `APELLIDOS=García López` y `125` producen `mariagarcia125`.
  `NOMBRE=María José` conserva ambas palabras del nombre. Un apellido con guion
  se considera una sola palabra y el guion se elimina al normalizar.
  Solo se almacena su hash nativo de Django; nunca se imprime ni se exporta.
- Cada perfil nuevo queda con `debe_cambiar_password=True`. Se mantiene el flujo
  de cambio obligatorio existente sin modificarlo.

La ejecución sin modo explícito falla. La aplicación requiere `--apply` en
lugar de `--dry-run` y debe realizarse solo después de revisar la simulación.
Si hay errores de validación, no se crea ninguna cuenta. Si no hay errores,
se crean usuarios y perfiles en una única transacción; cualquier fallo
inesperado revierte todas las altas de esa ejecución, incluida una colisión
concurrente de un nombre de usuario. Los mensajes no incluyen datos personales.
Una segunda importación omite las cuentas que ya existen.

Pruebas del importador con datos ficticios:

```sh
python manage.py test socios.tests.test_importar_socios
```

El runner crea su propia base de pruebas PostgreSQL y aplica allí las
migraciones; no debe configurarse para usar la base real. Los CSV ficticios
de las pruebas se crean temporalmente dentro de Ketama y se eliminan al terminar.
Estas pruebas no utilizan el archivo de socios real.

## Recuperar estados de cuentas ya importadas

El comando independiente `asignar_estados_socios` consulta el CSV original y
localiza cuentas existentes por número de socio. No crea usuarios ni perfiles;
solo actualiza `Socio.estado`. Conserva nombres, teléfonos, contraseñas, permisos,
habilitación de la cuenta e indicador de cambio de contraseña.
Excluye administradores, personal y el número `0`, y descarta filas inactivas o
expulsadas. Los recuentos no están fijados en 409: dependen de las cuentas reales.

Tras revisar y aplicar manualmente la migración, simular sin escrituras:

```sh
python manage.py asignar_estados_socios "archivo_socios.csv" --dry-run
```

El resultado solo muestra recuentos por estado de destino, cambios necesarios,
cuentas omitidas y errores. No muestra datos personales ni contraseñas.
Las cuentas cuyo estado ya coincide no se reescriben. Los errores de validación
o dos filas válidas con estados activo/caducado contradictorios para el mismo
número bloquean la aplicación. Los duplicados coincidentes se omiten.

Solo después de revisar la simulación se puede autorizar la asignación:

```sh
python manage.py asignar_estados_socios "archivo_socios.csv" --apply
```

La operación es transaccional: cualquier fallo inesperado revierte todos sus
cambios. Es una recuperación inicial manual, sin tareas programadas ni
sincronización posterior con el CSV. Después se gestiona el estado en Admin;
reaplicar manualmente el CSV podría sustituir estados ya renovados en Admin.
El socio ficticio `0` queda excluido del comando: para probar como activo,
el administrador debe revisar y asignar manualmente su estado en el perfil.

## Actualizar contraseñas temporales ya importadas

`actualizar_passwords_iniciales` utiliza el CSV original, sin modificarlo ni
deducir el primer apellido del nombre completo de la base de datos. Comparte
las validaciones del importador y requiere un modo explícito:

```sh
python manage.py actualizar_passwords_iniciales "archivo_socios.csv" --dry-run
```

Solo considera filas activas o caducadas y cuentas existentes con perfil y
`debe_cambiar_password=True`. Excluye el número `0`, personal y superusuarios,
cuentas sin perfil y socios que ya cambiaron la contraseña. No crea usuarios,
no modifica datos de perfiles, permisos ni el indicador de cambio pendiente.
No hay un número fijo de 409 actualizaciones: el recuento depende de las cuentas
que sigan siendo elegibles cuando se ejecute.

La simulación solo consulta y muestra recuentos. Si una cuenta ya tiene la
contraseña del nuevo formato, se omite sin reescribir su hash. No se muestran
nombres, teléfonos, contraseñas ni hashes.

Solo después de revisar la simulación, se puede autorizar la operación con:

```sh
python manage.py actualizar_passwords_iniciales "archivo_socios.csv" --apply
```

Las actualizaciones usan `set_password`, se realizan en una única transacción y
revalidan cuentas y perfiles bajo bloqueo. Los errores del CSV bloquean la
aplicación y un fallo inesperado revierte todas las actualizaciones. Los socios
afectados siguen obligados a cambiar la contraseña; sus sesiones anteriores
quedan invalidadas por el mecanismo nativo de Django al cambiar el hash.

Pruebas con datos ficticios (el runner utiliza su propia base de pruebas):

```sh
python manage.py test socios.tests.test_importar_socios socios.tests.test_actualizar_passwords_iniciales
```

No se ha ejecutado ninguna actualización real durante esta implementación.

## Valoraciones de genéticas

`geneticas.Valoracion` relaciona un socio con una genética, una puntuación entera
de 1 a 5 y la fecha automática de creación. La combinación socio–genética es
única en PostgreSQL; otra restricción SQL impide guardar puntuaciones fuera del
rango, incluido 0. Si el socio no ha valorado, no existe registro.

Solo los socios en estado `activo` con cuenta habilitada pueden crear o modificar
valoraciones. `save()` ejecuta la validación completa y bloquea la fila del socio
durante la operación para comprobar su estado actual. Una valoración existente
mantiene su socio, genética y fecha; se puede modificar su puntuación mediante
`save()` o `update_or_create()`. Las operaciones `update()`, `bulk_create()` y
`bulk_update()` se rechazan porque eluden la validación de `save()`.

Caducar un socio o desactivar una genética no elimina sus votos. Las agregaciones
incluyen estos votos históricos. `genetica.resumen_valoraciones()` devuelve
`{"media": ..., "numero": ...}` mediante `Avg` y `Count` en una consulta.
También están disponibles las propiedades `puntuacion_media` y
`numero_valoraciones`. Sin votos, la media y el número son 0. No se almacena
la media en la tabla de genéticas.

El Admin permite consultar las valoraciones en modo de solo lectura. No hay
vistas, formularios públicos, endpoints, estrellas visuales ni rankings.
La migración `geneticas/0002_valoracion.py` está preparada sin aplicar y depende
de `socios/0004_socio_estado.py`.

Comprobaciones locales:

```sh
python manage.py check
python manage.py makemigrations geneticas --check --dry-run
python manage.py test geneticas
```

Las pruebas de valoraciones utilizan una base de pruebas PostgreSQL, donde el
runner aplica las migraciones. No deben ejecutarse con una configuración `TEST`
que apunte a la base real. Tras revisar el plan, la aplicación manual se realiza
con `python manage.py migrate geneticas`; este comando también puede aplicar
dependencias pendientes de `socios`, cuyo estado inicial es `caducado`.
No se han ejecutado migraciones sobre PostgreSQL real durante esta implementación.

## Autenticación de socios

- `/acceso/`: número de socio (`User.username`) y contraseña, mediante
  `AuthenticationForm` y `LoginView` de Django.
- `/cambiar-password/`: contraseña actual y nueva contraseña confirmada,
  mediante `PasswordChangeForm` y `PasswordChangeView`.
- `/`: bienvenida provisional, disponible para socios activos después del cambio obligatorio.
- `/cuota-caducada/`: aviso «Tu cuota de socio está caducada. Contacta con el club para renovarla».
- `/salir/`: cierre de sesión mediante POST con token CSRF.

`Socio.debe_cambiar_password` vale `True` por defecto. La migración añade el
indicador también a los perfiles existentes sin alterar sus contraseñas.
En Admin se puede marcar de nuevo al entregar una contraseña temporal nueva.
Solo un cambio válido de contraseña lo desmarca desde el espacio de socios.
La nueva contraseña debe superar los validadores de Django y ser distinta de
la actual. El cambio conserva la sesión mediante el mecanismo nativo de Django.

`AccesoSociosMiddleware` protege las rutas de los namespaces `socios`, `geneticas`
y `comunicacion`, también si se accede directamente mediante GET o POST:
exige cuenta habilitada con perfil, rechaza personal y superusuarios, y fuerza
el cambio pendiente antes de acceder a páginas privadas. Después permite las
funcionalidades solo si `Socio.estado` es `activo`; en otro caso redirige al
aviso de cuota caducada. El cambio de contraseña y el cierre de sesión siguen
disponibles para ambos estados. Las futuras páginas privadas deben mantener
estos namespaces o incorporarse explícitamente al control. Los destinos `next` del
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
Para comprobar la bienvenida, el perfil de prueba debe estar en estado `activo`
(asignado manualmente en Admin). Si está caducado, debe aparecer únicamente el
aviso de cuota y el cierre de sesión. Después, cerrar sesión y volver a entrar
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

Catálogo, valoraciones, noticias y eventos, PWA y push
se implementarán por separado.
Las carpetas de plantillas y recursos vacías se conservan con `.gitkeep`.
No hay manifiesto, service worker ni lógica PWA todavía.

El despliegue en Railway, el servicio de estáticos en producción, las fotografías
en Railway Object Storage y las copias semanales con retención de cuatro copias
quedan pendientes. Este esqueleto no configura aún un despliegue de producción.
Las imágenes subidas no pertenecen a `static/`.

Nunca incorporar a Git datos reales de socios, CSV privados, contraseñas,
credenciales ni copias de seguridad. Usar datos ficticios para el portfolio.
