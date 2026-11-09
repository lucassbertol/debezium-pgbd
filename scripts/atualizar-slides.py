"""Substitui as capturas dos slides de demonstração pelas imagens atuais de evidencias/etapa-5.

Uso, na raiz do projeto, depois de scripts/gerar-evidencias.py:

    python scripts/atualizar-slides.py

Requer python-pptx e Pillow (pip install python-pptx pillow). Altera o deck final no lugar.
"""
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "apresentacao" / "CDC-com-Debezium-e-PostgreSQL-final.pptx"
SHOTS = ROOT / "evidencias" / "etapa-5"
CANVAS = (2000, 770)

# Título do slide -> captura.
SLIDES = {
    "Inserção do produto 101": "01-insercao.png",
    "Atualização do estoque": "02-atualizacao.png",
    "Editar e excluir na origem": "06-acoes-origem.png",
    "Exclusão do produto 101": "03-exclusao.png",
    "Inserção com o sink pausado": "04-sink-pausado.png",
    "Retomada do sink": "05-sink-retomado.png",
}


def slide_title(slide):
    texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    return next((t for t in texts if t in SLIDES), None)


def replace(slide, picture, path, scale):
    with Image.open(path) as raw:
        image = raw.convert("RGB").resize(
            (round(raw.width * scale), round(raw.height * scale)), Image.Resampling.LANCZOS
        )
    frame = Image.new("RGB", CANVAS, "white")
    frame.paste(image, ((frame.width - image.width) // 2, 0))
    data = BytesIO()
    frame.save(data, format="PNG")
    _, rid = slide.part.get_or_add_image_part(data)
    picture._element.find(".//" + qn("a:blip")).set(qn("r:embed"), rid)


def main():
    sizes = []
    for name in SLIDES.values():
        path = SHOTS / name
        if not path.is_file():
            sys.exit(f"Captura ausente: {name}")
        with Image.open(path) as image:
            sizes.append(image.size)
    scale = min(CANVAS[0] / max(w for w, _ in sizes), CANVAS[1] / max(h for _, h in sizes))
    prs = Presentation(DECK)
    done = set()
    for slide in prs.slides:
        title = slide_title(slide)
        if title is None:
            continue
        logo_limit = 3_000_000  # o logotipo da UFSM é a imagem pequena do cabeçalho
        pictures = [sh for sh in slide.shapes if sh.shape_type == 13 and sh.width > logo_limit]
        if len(pictures) != 1:
            sys.exit(f"O slide '{title}' tem {len(pictures)} capturas, esperada uma.")
        replace(slide, pictures[0], SHOTS / SLIDES[title], scale)
        done.add(title)
    if done != set(SLIDES):
        sys.exit(f"Slides não encontrados: {', '.join(sorted(set(SLIDES) - done))}")
    prs.save(DECK)
    print(f"{len(done)} slides atualizados em {DECK.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
