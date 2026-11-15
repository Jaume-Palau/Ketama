// Las imágenes externas fallidas dejan visible el marcador local, sin peticiones adicionales.
document.querySelectorAll("[data-imagen-catalogo]").forEach((imagen) => {
    const mostrarMarcador = () => {
        imagen.hidden = true;
        const contenedor = imagen.closest(".genetica-foto");
        contenedor.setAttribute("role", "img");
        contenedor.setAttribute("aria-label", "Imagen no disponible");
    };
    imagen.addEventListener("error", mostrarMarcador, { once: true });
    if (imagen.complete && imagen.naturalWidth === 0) mostrarMarcador();
});

// Estado efímero de la pestaña. Si el almacenamiento está bloqueado, el enlace
// de retorno sigue conservando los filtros y apunta a la tarjeta mediante un ancla.
const listaCatalogo = document.querySelector("[data-catalogo-lista]");
if (listaCatalogo) {
    const claveRetorno = "ketama:catalogo-retorno";
    const urlCatalogo = new URL(listaCatalogo.dataset.catalogoUrl, window.location.origin);
    const rutaCatalogo = urlCatalogo.pathname + urlCatalogo.search;
    listaCatalogo.querySelectorAll("[data-ficha-genetica]").forEach((enlace) => {
        enlace.addEventListener("click", (evento) => {
            if (evento.defaultPrevented || evento.button !== 0 || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
            try {
                sessionStorage.setItem(claveRetorno, JSON.stringify({
                    url: rutaCatalogo, y: window.scrollY, tarjeta: enlace.dataset.fichaGenetica,
                }));
            } catch (_) { /* El catálogo funciona también sin sessionStorage. */ }
        });
    });
    window.addEventListener("pageshow", () => {
        try {
            const retorno = JSON.parse(sessionStorage.getItem(claveRetorno));
            if (!retorno || retorno.url !== rutaCatalogo || !Number.isFinite(retorno.y) || retorno.y < 0) return;
            if (!document.getElementById(retorno.tarjeta)) return;
            sessionStorage.removeItem(claveRetorno);
            requestAnimationFrame(() => window.scrollTo(0, retorno.y));
        } catch (_) { /* Sin restauración exacta se mantiene el ancla del enlace. */ }
    });
}
