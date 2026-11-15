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
