# Ketama

Aplicación privada para socios con Python, Django, PostgreSQL y plantillas HTML.
La referencia de alcance es [ESPECIFICACION_PROYECTO.md](ESPECIFICACION_PROYECTO.md).

## Estado actual

Está creado el esqueleto y el modelo `Socio`, vinculado al usuario nativo de
Django. `geneticas` incluye el catálogo privado y `comunicacion`, los avisos publicados.
El espacio de socios incluye acceso, cambio de contraseña, cierre de sesión y
el catálogo como pantalla inicial. El panel de gestión conserva su entrada `/admin/`.
La migración `0004_socio_estado` está preparada sin aplicar.

## Gestión de socios

Tras revisar y aplicar la migración en una fase autorizada, los socios se
gestionarán desde **Autenticación y autorización → Usuarios** en Django Admin.
Al crear un usuario, indicar su número de socio en el nombre de usuario y
rellenar el perfil con nombre completo y estado. El número conserva ceros
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

## Protección de los accesos con django-axes

`django-axes==9.0.0` protege `/acceso/` y `/admin/login/` mediante los backends
nativos de autenticación. Ambos formularios utilizan `username`: número de socio
(conservando ceros iniciales) o nombre del administrador. Axes se ejecuta antes
de `ModelBackend` y su middleware es el último de la lista, según la
[documentación de Axes 9.0](https://django-axes.readthedocs.io/en/stable/2_installation.html).

Al quinto fallo de credenciales se bloquea ese usuario durante 15 minutos.
Los fallos se suman entre ambos accesos y desde distintas IP, navegadores o
sesiones. Otro usuario en la misma IP conserva su acceso. Los reintentos durante
el bloqueo no prolongan su duración; un acceso correcto reinicia el contador.
La expiración se comprueba en las siguientes peticiones, sin tareas programadas.
No se desactiva `User.is_active`, no se cierran sesiones existentes ni se cambian
contraseñas o el requisito de cambio obligatorio. Al bloquear por nombre, alguien
que lo conozca puede provocar un bloqueo temporal de esa cuenta.

El handler de base de datos guarda los intentos en PostgreSQL para compartirlos
entre todos los procesos Gunicorn; no utiliza caché local ni requiere Redis.
No se guardan IPs reales: `0.0.0.0` es un marcador técnico fijo que no participa
en la decisión de bloqueo. No se habilita historial de accesos correctos ni un
registro adicional por cada fallo. Los registros de intentos contienen el
usuario necesario para el contador; Axes enmascara la contraseña del formulario.

La pantalla de bloqueo reutiliza `login.css`, devuelve HTTP 429 y no muestra
usuario ni contraseña, también si la petición lleva `XMLHttpRequest`. La respuesta
es privada y no debe almacenarse en caché.

Axes 9.0 puede mostrar `axes.W006` al ejecutar comprobaciones: aconseja incluir
la IP en los criterios de bloqueo. Aquí se mantiene deliberadamente
`AXES_LOCKOUT_PARAMETERS = ["username"]` para respetar la política acordada de
no bloquear a otros socios de una misma IP. No añadir bloqueo por IP para
silenciar esta advertencia.

### Preparación y comprobaciones

La dependencia está declarada; esta implementación no instala paquetes ni aplica
migraciones. En una fase autorizada, instalar los requisitos y aplicar **todas
las migraciones incluidas por Axes 9.0**, hasta `0010_accessattemptexpiration`:

```sh
python -m pip install -r requirements.txt
python manage.py check
python manage.py migrate axes --plan
python manage.py migrate axes
```

No se crean migraciones ni campos en los modelos de Ketama para esta protección.
Las migraciones pendientes de las otras aplicaciones se revisan por separado.
No publicar esta configuración antes de instalar Axes y preparar sus tablas.

Pruebas con cuentas ficticias y base independiente del runner, nunca la base real:

```sh
python manage.py test socios.tests.test_bloqueo
python manage.py test socios geneticas comunicacion
```

### Desbloqueo manual desde Django Admin

1. Entrar en `/admin/` con una cuenta administrativa autorizada que no esté bloqueada.
2. Abrir **Axes → Access attempts / Intentos de acceso** y buscar el `username`
   exacto; para socios, conservar los ceros iniciales.
3. Eliminar todos los registros de intentos de ese usuario (puede haber varios
   por distintos navegadores) y confirmar. Esto reinicia el contador sin eliminar
   al usuario, su perfil o sus contraseñas. No basta con borrar los registros de
   historial de accesos.
4. El usuario ya puede volver a intentar iniciar sesión.

Si la única cuenta administrativa está bloqueada, esperar los 15 minutos o,
desde una consola autorizada conectada al entorno correcto, ejecutar:

```sh
python manage.py axes_reset_username NUMERO_O_USUARIO_EXACTO
```

Este comando modifica únicamente los registros de bloqueo. No ejecutarlo en
producción sin autorización; no se ha ejecutado durante esta implementación.

## Importación inicial desde CSV

### Retirada de teléfonos

La migración pendiente `socios.0005_remove_socio_telefono` elimina únicamente
la columna de teléfono; conserva socios, nombres, números, estados y contraseñas.
No modifica las migraciones históricas ni el CSV original. Los teléfonos siguen
en PostgreSQL hasta aplicarla; recrear la columna posteriormente no recuperaría
su contenido. Aplicarla antes de crear socios con esta versión del código.

Comando para una fase autorizada (no ejecutado durante este cambio):

```sh
python manage.py migrate socios 0005_remove_socio_telefono
```

Pruebas afectadas, en la base independiente creada por el runner:

```sh
python manage.py test socios
```

### Uso del importador

El comando `importar_socios` lee directamente el archivo indicado, sin copiarlo.
Requiere UTF-8 (admite BOM), separador `;` y las columnas `ESTADO`,
`NºSocio`, `NOMBRE` y `APELLIDOS` (pueden cambiar de orden).
También acepta la columna opcional `TELEFONO` del archivo original, pero ignora
su contenido: no lo valida, almacena ni utiliza para generar contraseñas.
No se admiten otras columnas ni cabeceras duplicadas.
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
  Número de socio, nombre y apellidos deben estar cumplimentados.
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
solo actualiza `Socio.estado`. Conserva nombres, contraseñas, permisos,
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
nombres, datos del CSV, contraseñas ni hashes.

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

El Admin permite consultar las valoraciones en modo de solo lectura. El catálogo
muestra la media y el número de votos, y la ficha permite guardar o modificar
la puntuación del socio. No hay rankings independientes.
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

## Catálogo privado

`/catalogo/` muestra exclusivamente las genéticas activas de PostgreSQL, con
una tarjeta por fila e imágenes 4:3. El diseño toma como referencia el archivo
`design/referencias/Catálogo Ketama de Genéticas Cannabis.png`. No utiliza
fotografías ni registros de ejemplo como datos del catálogo.

Parámetros GET, combinables y conservados al cambiar los filtros:

- `q`: búsqueda parcial por nombre, sin distinguir mayúsculas.
- `clasificacion`: `sativa`, `indica` o `hibrida`; vacío muestra todas.
- `orden`: `valoracion` (predeterminado), `precio_asc` o `precio_desc`.

La media y el número de votos se anotan mediante `Avg` y `Count` en la misma
consulta del listado. La media más alta va primero; en caso de empate se usa
el número de votos y el nombre. Las genéticas sin votos se muestran al final.
Los precios desconocidos van al final en ambos órdenes de precio.

La interfaz de socios muestra «Nivel de precio» con una barra de cinco segmentos,
sin importes, rangos ni símbolos monetarios. Un precio 0 pertenece al primer
nivel; un precio no informado muestra «Nivel no disponible». Los límites se
centralizan en `geneticas/precios.py` y se calculan como decimales en PostgreSQL.
La ordenación ascendente/descendente sigue usando el precio real, también cuando
dos genéticas comparten nivel. El precio exacto y la unidad se conservan en Admin.

Las vistas seleccionan únicamente los campos públicos y el nivel calculado;
las plantillas reciben objetos de presentación sin `precio`, `unidad_precio` ni
acceso diferido al ORM. No se incluyen importes en atributos, campos ocultos,
JSON o JavaScript. Ambas pantallas utilizan `geneticas/_nivel_precio.html`.
La barra es un SVG con cinco rectángulos, separación y esquinas redondeadas.
Cada rectángulo lleva dimensiones y color propios (verde para los activos,
gris para los restantes), por lo que no depende de estilos de elementos vacíos.
La hoja específica `nivel_precio.css?v=2` añade el acabado neón y utiliza una URL
nueva para evitar reutilizar el CSS anterior. Un precio de nivel 2 genera
exactamente dos rectángulos verdes y tres grises.
Sin votos aparece «Sin valoraciones»; sin imagen aparece un marcador, también
si la URL externa falla. Cada tarjeta enlaza a su ficha completa.

El CSS del catálogo se comparte con la ficha detallada. La autenticación conserva
sus estilos existentes. La búsqueda y ordenación funcionan sin JavaScript,
mediante los botones Buscar/Aplicar; el JavaScript gestiona imágenes fallidas y
la restauración del desplazamiento al regresar de una ficha.
La barra inferior permite navegar entre Catálogo, Avisos y Perfil, resaltando la
sección actual. El encabezado mantiene un cierre de sesión POST.

El acceso de socios activos y el cambio de contraseña completado llevan al
catálogo; `/` también redirige allí después de pasar el control de acceso.
Se mantienen el aviso de caducidad, la exigencia de contraseña personal y la
separación del Admin. Ninguna visita al catálogo modifica genéticas ni votos.

Para probarlo con la base local ya preparada y las dependencias existentes:

```sh
source .venv/bin/activate
python manage.py check
python manage.py runserver
```

Abrir `http://127.0.0.1:8000/acceso/` e iniciar sesión como socio habilitado,
en estado activo y con el cambio de contraseña completado. El catálogo está
en `http://127.0.0.1:8000/catalogo/`. Las pruebas se pueden ejecutar con
`python manage.py test geneticas socios`; el runner usa una base separada y
aplica migraciones en esa base de pruebas. No se ejecutan migraciones reales
como parte de esta implementación del catálogo.

Pruebas específicas del indicador y su llegada a catálogo y detalle:

```sh
python manage.py test geneticas.tests.test_indicador_precio geneticas.tests.test_nivel_precio
```

Las primeras prueban la plantilla sin base de datos; las de integración utilizan
solo la base de pruebas. Se inspeccionan los cinco rectángulos del HTML, colores,
dimensiones, relleno por nivel, límites y ausencia de importes públicos.

## Ficha detallada de genéticas

`/catalogo/<id>/` muestra una única fotografía, nombre, clasificación, nivel de
precio, THC, CBD, descripción y el resumen de valoraciones de una genética activa.
La referencia visual es `design/referencias/Ficha Purple Punch en Ketama.png`.
Se reutilizan cabecera, iconos, etiquetas de clasificación, marcador de imagen y
barra inferior. Esta mantiene Catálogo, Avisos y Perfil habilitados.
No se añaden Inicio, Carrito ni favoritos.

La ficha obtiene en una sola consulta la media, el total de votos, el reparto
de 5 a 1 estrellas y, si existe, la puntuación del socio autenticado. Todos son
datos persistidos, sin números de ejemplo. La sección «Tu valoración» permite
seleccionar de 1 a 5 estrellas enteras y pulsar «Guardar valoración». Abrir la
ficha no modifica votos; solo se guardan mediante el envío explícito del formulario.

El formulario usa controles de radio nativos, utilizables con teclado o pantalla
táctil. El CSS muestra las estrellas seleccionadas y su valor, sin JavaScript ni
AJAX adicionales. Si ya hay un voto, la puntuación guardada aparece seleccionada.
`ValoracionForm` solo admite los cinco enteros válidos; los valores vacíos,
fraccionarios o fuera de rango se rechazan en el servidor y muestran errores.

`POST /catalogo/<id>/valorar/` exige CSRF y los permisos actuales. Identifica al
socio por la sesión y a la genética por la URL, sin aceptar identidades enviadas
por el formulario. Revalida usuario, estado, cambio de contraseña y genética activa
bajo bloqueo en una transacción. Usa `update_or_create` y la validación del modelo
para mantener un solo voto por socio y genética, conservando la fecha de creación.
Tras guardar, redirige a la ficha con una confirmación junto al formulario y
recalcula media, recuento y distribución. Refrescar ese GET no reenvía la valoración.
Los parámetros de búsqueda, clasificación y ordenación se conservan.

El precio vacío se muestra como «Nivel no disponible»; un 0 real se representa
con nivel 1. THC y CBD vacíos se muestran como no informados y sus valores 0 se
conservan. Una URL de imagen fallida muestra el mismo marcador que
una imagen no informada. Las descripciones se escapan y conservan los saltos
de línea, sin interpretar HTML almacenado.

Los enlaces de las tarjetas llevan `q`, `clasificacion` y `orden`. «Volver al
catálogo» y la barra inferior reconstruyen una URL interna con esos parámetros
y el ancla de la tarjeta. No se aceptan URLs externas de retorno. El JavaScript
guarda temporalmente URL y desplazamiento en `sessionStorage` de la pestaña,
y los restaura una sola vez al volver por el enlace o por el botón del navegador.
Si JavaScript o ese almacenamiento están deshabilitados, permanecen los filtros
y el ancla a la tarjeta, aunque no se restaura la posición exacta en píxeles.

El middleware sigue protegiendo el acceso directo: cuenta habilitada, estado
activo y cambio obligatorio de contraseña completado. Las genéticas inactivas
o inexistentes devuelven 404 al socio autorizado. La ficha admite solo GET/HEAD;
el envío de valoraciones utiliza su URL POST independiente. Las respuestas
mantienen las cabeceras que evitan el almacenamiento en caché.

Para probar la navegación, iniciar el servidor con la base local ya preparada,
entrar como socio activo, buscar/filtrar/ordenar el catálogo, desplazarse y abrir
una tarjeta. Comprobar la ficha y regresar con «Volver al catálogo» y con Atrás
del navegador. Para probar votos, usar un entorno destinado a pruebas: seleccionar
estrellas, guardar y comprobar el resumen; cambiar la selección y verificar que
el total de votos permanece igual. No se han ejecutado migraciones ni operaciones
sobre la base real durante esta implementación.

Pruebas de la nueva vista y regresiones del catálogo:

```sh
python manage.py test geneticas.tests.test_detalle geneticas.tests.test_catalogo geneticas.tests.test_votacion
```

El runner usa su propia base PostgreSQL de pruebas y aplica allí las migraciones.
No debe configurarse para apuntar a la base real. La restauración visual del
desplazamiento se comprueba manualmente en el navegador.

## Avisos del club

`comunicacion.Aviso` contiene título y mensaje obligatorios, fecha de creación
automática y `activo` (publicado). Los nuevos avisos son borradores por defecto.
En Django Admin se pueden crear, editar, eliminar y publicar/ocultar; la casilla
de publicación se puede cambiar desde el listado, que muestra título y fecha.
No se envían notificaciones automáticas al publicar o editar.

`/avisos/` muestra solo los avisos publicados, ordenados por fecha descendente
y, para empates, por identificador descendente. Conserva los saltos de línea y
escapa HTML en título y mensaje. Si no hay avisos publicados, muestra un estado
vacío. La sección reutiliza cabecera, iconos, navegación y estética del catálogo,
con un CSS propio para las tarjetas. No permite escrituras desde la vista de socios.

Se mantienen los permisos existentes: cuenta habilitada, perfil de socio activo
y cambio de contraseña completado. Los caducados ven su aviso de cuota, los
pendientes deben cambiar su contraseña y los administradores usan Django Admin.
No hay cambios en el middleware ni en la autenticación.

La migración `comunicacion/0001_initial.py` está preparada sin aplicar. Después
de revisarla, la preparación manual y las pruebas se pueden realizar con:

```sh
python manage.py migrate comunicacion --plan
python manage.py migrate comunicacion
python manage.py test comunicacion socios geneticas
```

No se han ejecutado migraciones ni cambios reales durante esta implementación.
El runner de pruebas usa su propia base independiente. Para comprobar la sección
en el navegador tras preparar la base, publicar un aviso desde Admin en el entorno
de pruebas e iniciar sesión como socio activo para abrir Avisos desde la barra.

## Perfil del socio

`/perfil/` muestra únicamente nombre completo y número del socio autenticado,
incluidos los ceros iniciales del número. No admite identificadores de otros
socios en la ruta ni toma esos datos de parámetros GET/POST. Es una pantalla
de consulta; no permite editar nombre ni otros datos.

Reutiliza cabecera, iconos, estilos dark/neón y navegación del catálogo, con un
CSS específico para la tarjeta de datos y acciones. La navegación resalta Perfil
cuando corresponde. El botón «Cambiar contraseña» enlaza a `/cambiar-password/`
y el cierre de sesión envía POST con CSRF a `/salir/`.

El cambio voluntario conserva el flujo existente: exige la contraseña actual,
valida la nueva, mantiene la sesión y vuelve al catálogo para socios activos.
No se altera el cambio obligatorio del primer acceso. Los socios caducados o
con cambio pendiente mantienen sus redirecciones; administradores y cuentas sin
perfil no acceden a este espacio. Las respuestas conservan `no-store`.

Para comprobarlo, iniciar el servidor habitual, entrar como socio activo y
pulsar Perfil desde el catálogo o una ficha. Revisar los datos propios y probar
las acciones con una cuenta destinada a pruebas. Las pruebas automatizadas usan
una base independiente:

```sh
python manage.py test socios.tests.test_perfil socios.tests.test_auth geneticas.tests.test_catalogo geneticas.tests.test_detalle
```

No se han creado modelos, migraciones ni ejecutado modificaciones sobre la base
real para incorporar esta sección.

## Autenticación de socios

- `/acceso/`: número de socio (`User.username`) y contraseña, mediante
  `AuthenticationForm` y `LoginView` de Django.
- `/cambiar-password/`: contraseña actual y nueva contraseña confirmada,
  mediante `PasswordChangeForm` y `PasswordChangeView`.
- `/`: redirección al catálogo para socios activos después del cambio obligatorio.
- `/catalogo/`: catálogo de genéticas activas.
- `/perfil/`: datos del socio autenticado y acceso a las acciones de cuenta.
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
Para comprobar el catálogo, el perfil de prueba debe estar en estado `activo`
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

## Seguridad de desarrollo y producción

`DJANGO_ENV` acepta `development` (por defecto) o `production`. Es independiente
de `DEBUG`: probar con `DEBUG=False` en local no fuerza HTTPS. El `.env` local
no se modifica; sus hosts permitidos, incluida la IP LAN existente, se conservan.

En desarrollo se mantienen desactivados la redirección HTTPS y los atributos
Secure de las cookies de sesión y CSRF. Para acceder desde el móvil por Wi-Fi,
incluir la IP LAN real del ordenador en `ALLOWED_HOSTS` (sin esquema ni puerto),
ejecutar `python manage.py runserver 0.0.0.0:8000` y abrir desde el móvil
`http://IP_LAN_REAL:8000`. La IP debe coincidir con la red actual. Un formulario
servido y enviado al mismo origen no necesita añadir ese origen a
`CSRF_TRUSTED_ORIGINS`.

Para el futuro servicio de Railway, definir las variables en su configuración:

- `DJANGO_ENV=production` y `DEBUG=False`. El arranque falla si se intenta
  utilizar `DEBUG=True` en producción o un nombre de entorno desconocido.
- `SECRET_KEY`: una clave aleatoria exclusiva de producción, fuera de Git.
- `ALLOWED_HOSTS`: dominios reales autorizados, separados por comas, sin esquema
  ni puerto. En producción no se aceptan una lista vacía ni el valor `*`.
- `CSRF_TRUSTED_ORIGINS`: los orígenes adicionales realmente necesarios, con
  `https://` y sin rutas, separados por comas. Puede permanecer vacío si solo
  se utiliza el mismo origen y Django reconoce HTTPS correctamente. No reemplaza
  `ALLOWED_HOSTS` ni deshabilita CSRF.
- `TRUST_PROXY_HTTPS=True`: solo después de verificar que el proxy de Railway
  elimina/sobrescribe la cabecera enviada por el cliente y establece
  `X-Forwarded-Proto`, y que Django no admite tráfico público que evite ese proxy.
  Habilita `SECURE_PROXY_SSL_HEADER` únicamente en producción. Confiar en una
  cabecera controlable por el cliente permitiría falsear el esquema seguro.

En producción `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` y
`CSRF_COOKIE_SECURE` se activan automáticamente. Tras verificar el proxy, una
petición HTTPS externa debe reconocerse como segura y no entrar en un bucle
de redirecciones. No se inventa ni configura todavía ningún dominio de Railway.
Los ajustes siguen las [recomendaciones de Django 5.2](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

Comprobaciones sin migraciones ni acceso a la base de datos en estas pruebas:

```sh
python manage.py test config.tests
python manage.py check
```

Las pruebas de configuración usan variables ficticias en memoria, ignoran `.env`
y comprueban HTTP local/Wi-Fi, HTTPS, proxy, cookies y rechazo de ajustes inseguros.
Antes del despliegue, con las variables de producción reales definidas, ejecutar
`python manage.py check --deploy`. Se revisan sus avisos por separado: HSTS sigue
sin habilitarse hasta comprobar dominio y HTTPS; Axes puede emitir la advertencia
`axes.W006` documentada anteriormente por el bloqueo deliberado solo por usuario.
Esta preparación no configura Gunicorn, estáticos, PostgreSQL ni un despliegue.

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
