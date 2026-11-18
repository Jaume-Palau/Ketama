"""Inspección del HTML real de los indicadores, sin navegador ni dependencias."""
from html.parser import HTMLParser


class BarrasPrecioParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.barras = []
        self.actual = None
        self.profundidad_svg = 0
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "svg":
            self.profundidad_svg += 1
            if "nivel-precio-barra" in attrs.get("class", "").split():
                self.actual = {"atributos": attrs, "segmentos": [], "profundidad": self.profundidad_svg}
                self.barras.append(self.actual)
        elif tag == "rect" and self.actual is not None:
            self.actual["segmentos"].append(attrs)

    def handle_endtag(self, tag):
        if tag == "svg":
            if self.actual and self.actual["profundidad"] == self.profundidad_svg:
                self.actual = None
            self.profundidad_svg -= 1
