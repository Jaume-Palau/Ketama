# Aplicación privada para socios — Especificación técnica

**Estado:** planificación funcional acordada; pendiente de iniciar desarrollo.  
**Documento de referencia para Codex.** Leer antes de crear archivos, instalar dependencias o modificar la arquitectura.

## 1. Objetivo

Desarrollar una aplicación web **privada e instalable en móviles (PWA)** para un club de socios. Sustituirá la aplicación comercial de comunicación con socios, cuyo coste aproximado es de **50 €/mes**, pero **no** sustituirá el programa de gestión interna «Gestión Verde».

El producto permite a los socios consultar un catálogo de genéticas, valorarlas y recibir noticias, eventos y comunicados. La administración gestionará el contenido desde una interfaz sencilla.

**Prioridades:** sencillez, bajo coste de mantenimiento, desarrollo rápido asistido por Codex, y un código comprensible y presentable como proyecto de portfolio. No se desea una infraestructura compleja ni sobreingeniería.

## 2. Decisiones tecnológicas cerradas

| Componente | Decisión |
| --- | --- |
| Equipo de desarrollo | MacBook con macOS |
| Editor y agente de programación | VS Code + Codex |
| Lenguaje principal | Python |
| Framework web | Django |
| Interfaz | Plantillas HTML de Django + CSS + JavaScript mínimo |
| Aplicación móvil | PWA (web instalable desde el navegador; sin apps nativas) |
| Base de datos definitiva | PostgreSQL desde el comienzo |
| Alojamiento de producción | Railway, aprovechando la suscripción existente si su consumo lo permite |
| Fotografías | Almacenamiento de objetos de Railway (Object Storage) |
| Control de versiones | Git + GitHub |
| Proceso de desarrollo | Codex escribe la mayor parte del código; el propietario revisa y comprende lo generado |

**No utilizar de entrada:** React, Vite, Supabase, microservicios, una API REST separada ni infraestructura adicional que no aporte una ventaja clara al alcance actual.

## 3. Alcance funcional (primera versión)

### 3.1. Dos perfiles

- **Administrador:** una sola cuenta con permisos completos; gestiona socios, catálogo, noticias, eventos y notificaciones.
- **Socio:** accede al contenido privado, consulta fichas y puede valorar genéticas.

No se necesitan roles adicionales ni registro público de usuarios.

### 3.2. Instalación y acceso

1. Se mostrará en el local un **código QR** que abre la URL privada de la PWA.
2. El socio accede a la web y puede **añadirla a la pantalla de inicio** siguiendo las opciones que permita su navegador/dispositivo.
3. El socio inicia sesión con su **número de socio** y una **contraseña temporal individual** facilitada por el club.
4. En el primer acceso deberá sustituirla por una contraseña personal.
5. El administrador podrá dar de alta, desactivar o restablecer el acceso manualmente.

No usar el número de socio como contraseña ni una contraseña temporal compartida. No utilizar SMS, correo electrónico ni proveedores de autenticación externos en esta primera versión.

### 3.3. Datos de los socios

Almacenar **solo**:
- Número de socio (identificador único y nombre de usuario).
- Nombre completo.
- Teléfono.
- Credenciales y datos técnicos mínimos imprescindibles para autenticación/permisos.

**No almacenar** DNI, dirección, fecha de nacimiento ni datos adicionales del sistema de trabajo.

**Importación inicial desde CSV:** el archivo ya existe, pero se incorporará en una fase posterior. Contiene los campos anteriores y un `estado` de origen:

| Estado en CSV | Importación |
| --- | --- |
| `activo` | Crear cuenta habilitada |
| `caducado` | Crear cuenta habilitada |
| `inactivo` | Omitir; no crear cuenta |

El estado del CSV se utiliza **solo como filtro inicial**. **No** se implementa gestión de cuotas, renovación ni caducidades dentro de la aplicación. No existe sincronización automática con Gestión Verde. Los usuarios importados estarán habilitados por defecto, y el administrador podrá desactivar cuentas manualmente. Los socios antes inactivos que regresen se crearán manualmente.

El importador debe verificar los datos, identificar duplicados y ser **idempotente** (repetirlo no debe crear cuentas duplicadas). Nunca guardar el CSV real ni las contraseñas en GitHub.

### 3.4. Catálogo de genéticas

**Vista del socio:** catálogo de fichas con fotografía y datos. Cada ficha incluye:
- Nombre.
- Fotografía.
- Tipo/categoría (según los valores definidos por el club; por ejemplo interior/exterior).
- Porcentaje sativa e índica.
- Porcentaje de THC y CBD (permitir valores desconocidos/vacíos).
- Descripción breve (*texto presentación*).
- Descripción ampliada (*texto completo*).
- Valoración media y número de valoraciones.

**Vista de administración:** crear, editar y eliminar fichas, rellenando un formulario y subiendo la fotografía. **No requiere modificar código** para gestionar contenidos. Se puede incorporar un control de visibilidad/publicación si resulta útil, sin ampliar innecesariamente el alcance.

La fotografía se almacena como archivo en Object Storage; PostgreSQL guarda su referencia y el resto de atributos. La ficha y su fotografía permanecen asociadas hasta que el administrador las cambie o elimine.

### 3.5. Valoraciones

- Puntuación de **1 a 5 estrellas**.
- Un socio puede tener **una valoración por genética**, no varias.
- Puede modificar su puntuación.
- Mostrar media calculada y número de votos.
- Solo pueden valorar los usuarios con **cuenta habilitada**.
- No utilizar el estado `caducado` del CSV como restricción: esa caducidad **no se sigue** después de la importación.

La unicidad socio–genética debe garantizarse también en la base de datos.

### 3.6. Noticias y eventos (separados)

**Noticias:** título, imagen opcional, descripción/contenido y fecha de publicación.  
**Eventos:** título, imagen opcional, descripción, fecha y hora del evento.

Ambos tendrán su propio apartado para socios y su gestión desde administración.

### 3.7. Notificaciones

Se requieren **notificaciones push**, solicitando permiso al dispositivo y respetando las limitaciones de navegador y sistema operativo. Los casos de uso son:
- Avisar de una nueva genética.
- Avisar de una noticia.
- Avisar de un evento.
- Enviar un comunicado general.

**Regla principal: envío siempre manual.** El administrador decide cuándo enviar, mediante una acción claramente identificada (por ejemplo, «Publicar y notificar»). Publicar o editar contenido **no** debe enviar notificaciones automáticamente.

No enviar avisos de caducidad ni de renovación de cuotas.

**Nota técnica:** las notificaciones push de PWA requieren HTTPS, *service worker*, suscripciones y consentimiento. En iOS pueden requerir añadir la web a la pantalla de inicio. Desarrollarlas y probarlas en una fase posterior a la funcionalidad básica.

### 3.8. QR para el local

Generar un QR que apunte a la URL pública de acceso a la PWA. El QR **no descarga un archivo APK/IPA**: abre la web desde la que el socio podrá instalarla en su pantalla de inicio cuando el dispositivo lo permita.

## 4. Arquitectura y estructura inicial sugerida

Una **aplicación Django monolítica**, con plantillas renderizadas en el servidor. Aprovechar **Django Admin** para el panel de gestión de la primera versión, personalizándolo únicamente cuando sea necesario.

```text
club-app/
├── manage.py
├── config/                 # settings, urls, wsgi, asgi
├── socios/                 # autenticación, perfiles, importación CSV
├── geneticas/              # catálogo y valoraciones
├── comunicacion/           # noticias, eventos y avisos
├── templates/              # HTML: login, catálogo, detalle, noticias, eventos
├── static/                 # CSS, JS mínimo, iconos y recursos PWA
├── tests/                  # pruebas si no se ubican dentro de cada app
├── .env.example            # variables necesarias, SIN secretos reales
├── .gitignore
├── requirements.txt        # dependencias fijadas
├── README.md               # instalación, desarrollo y despliegue
└── ESPECIFICACION_PROYECTO.md
```

La estructura es una **base recomendada**, no una obligación de crear carpetas vacías ni capas artificiales. Priorizar convenciones estándar de Django.

### Datos y autenticación — recomendación de implementación

Para mantener la complejidad baja, se puede usar el sistema de usuarios de Django, con `username = numero_socio`, permisos nativos (`is_staff`, `is_superuser`, `is_active`) y un perfil `Socio` vinculado donde guardar `nombre_completo`, `telefono` y, si es necesario, un indicador de cambio obligatorio de contraseña. Considerar el modelo de usuario personalizado **antes de la primera migración** solo si aporta una ventaja clara; no complicar por anticipado.

Modelos conceptuales:

- `Socio` / cuenta: número de socio, nombre, teléfono, habilitado y credenciales.
- `Genetica`: nombre, tipo, porcentajes, textos, imagen y visibilidad (si se implementa).
- `Valoracion`: socio, genética, puntuación; restricción única socio–genética.
- `Noticia`: título, contenido, imagen opcional, fecha.
- `Evento`: título, contenido, imagen opcional, fecha y hora.
- `SuscripcionPush`: suscripción del dispositivo asociada al socio para notificaciones consentidas.

Usar migraciones de Django y validación de campos numéricos (porcentajes entre 0 y 100). No inventar valores de THC/CBD; permitir que queden vacíos.

## 5. Infraestructura, ficheros y backups

- **Desarrollo:** macOS, proyecto local en VS Code, Django con PostgreSQL configurado por variables de entorno.
- **Producción:** Django en Railway, PostgreSQL persistente y fotografías en Railway Object Storage.
- **Archivos estáticos:** servir correctamente los CSS/JS en producción usando la solución más simple compatible con Railway.
- **Secretos:** `SECRET_KEY`, conexión a BD, credenciales de almacenamiento y claves push fuera del repositorio; usar variables de entorno.
- **Copias de seguridad:** **una cada semana**, conservar **las últimas cuatro**; automatizar backup de PostgreSQL y comprobar que pueda restaurarse. Las fotografías también requieren una estrategia de protección/recuperación; decidir la implementación más sencilla posible, sin asumir que una copia de la base de datos incluye las imágenes.
- **Costes:** intentar aprovechar el plan de Railway ya pagado. Verificar consumo real de PostgreSQL, Django, Object Storage, backups y tráfico; no asumir que todo estará incluido sin sobrecoste.

## 6. Seguridad y datos reales

Aunque sea un proyecto interno y pequeño:

- Acceso autenticado al contenido de socios y permisos de administrador restringidos.
- Contraseñas con los mecanismos de hash de Django; no guardar contraseñas en texto claro.
- Una contraseña temporal **distinta para cada usuario**, distribuida de forma privada y con cambio obligatorio al primer acceso.
- Protección estándar de Django frente a CSRF, validación de formularios, archivos subidos y sesiones seguras bajo HTTPS.
- No exponer el CSV real, números de teléfono ni datos de socios en GitHub, ejemplos, registros públicos o el portfolio.
- Los datos personales siguen requiriendo un tratamiento autorizado y medidas básicas de privacidad; revisar con el club el uso del fichero de socios y las comunicaciones. Mantener esta revisión proporcionada al alcance; no convertirla en un módulo funcional adicional.
- Para enseñar la aplicación en el portfolio, utilizar **datos ficticios** y capturas sin información privada.

## 7. Fuera de alcance

No desarrollar salvo petición explícita:

- Integración o sincronización con Gestión Verde.
- Gestión de cuotas, caducidades, cobros, stock o caja del club.
- Importación continua o actualización automática de socios.
- Altas públicas o autoservicio de registro.
- Aplicaciones nativas de App Store / Play Store.
- Sistemas complejos de marketing, Mailchimp, analítica avanzada o tiempo real.
- Múltiples niveles de permisos o empleados.
- Copia literal del código propietario o ingeniería inversa de la aplicación comercial.

## 8. Orden de implementación recomendado para Codex

1. **Esqueleto:** crear Django, configuración PostgreSQL, Git, `.env.example`, README y pruebas básicas de arranque.
2. **Acceso y administración:** inicio/cierre de sesión, cuenta de administrador, perfiles de socio y permisos.
3. **Genéticas:** modelos, Django Admin, subida de fotografía, catálogo privado y detalle de ficha.
4. **Valoraciones:** estrellas, edición del voto, media y restricciones.
5. **Noticias y eventos:** secciones separadas y gestión por administrador.
6. **PWA e instalación:** diseño móvil, manifiesto, iconos, service worker y QR.
7. **Push:** consentimiento y suscripciones, envíos manuales del administrador.
8. **Importación CSV:** solo cuando el archivo real esté disponible, importando activos y caducados; omitiendo inactivos.
9. **Despliegue y protección:** Railway, PostgreSQL, Object Storage, backups semanales, verificaciones y pruebas con móviles.

El orden puede ajustarse por dependencias técnicas; priorizar una **versión funcional pequeña** antes de refinamientos.

## 9. Forma de trabajar con Codex

- Implementar **una fase o funcionalidad a la vez**, sin generar toda la aplicación de golpe.
- Antes de cambios importantes, explicar brevemente **qué archivos se tocarán y por qué**.
- Elegir la solución **más sencilla y mantenible**; evitar nuevas dependencias si Django ya cubre la necesidad.
- Codex escribe el código y ejecuta pruebas; explicar después lo esencial para que el propietario entienda la arquitectura y las decisiones.
- No ejecutar migraciones destructivas, borrar datos, sustituir despliegues existentes ni publicar datos reales sin confirmación.
- No suponer que el CSV está disponible. No pedirlo hasta llegar a la fase de importación.
- Mantener el proyecto listo para GitHub y portfolio, sin información confidencial.

## 10. Criterios de éxito de la primera versión

- Un socio autorizado abre la web con QR, inicia sesión y accede al catálogo desde su móvil.
- El administrador crea una genética y sube una imagen **sin modificar código**.
- El socio ve las fichas, consulta los detalles y valora de 1 a 5 estrellas, una vez por genética.
- Se publican noticias y eventos por separado.
- El administrador **decide explícitamente** cuándo enviar notificaciones, que se entregan a los dispositivos compatibles y suscritos.
- Un script importa de manera segura los socios activos/caducados sin duplicados y excluye a los inactivos.
- La aplicación se despliega en Railway y persiste correctamente los datos e imágenes.
- Existen copias semanales recuperables y documentación suficiente para mantenerla.

---

**Resumen de producto:** «Catálogo privado de genéticas + valoraciones + noticias + eventos + avisos push manuales», administrado por una sola cuenta, desarrollado con Django, PostgreSQL y Railway, con costes y complejidad mínimos.
