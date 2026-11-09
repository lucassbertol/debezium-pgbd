"""Substitui as capturas dos slides de demonstração pelas imagens atuais de evidencias/etapa-5.

Uso, na raiz do projeto, depois de scripts/gerar-evidencias.py:

    python scripts/atualizar-slides.py

Requer python-pptx e Pillow (pip install python-pptx pillow). Altera o deck final no lugar.
"""
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "apresentacao" / "CDC-com-Debezium-e-PostgreSQL-final.pptx"
SHOTS = ROOT / "evidencias" / "etapa-5"
GAP = 80_000  # espaço entre a imagem e a legenda, em EMU
FOOTER = 6_300_000  # topo da linha do rodapé, em EMU

# Título do slide -> capturas, da esquerda para a direita.
SLIDES = {
    "Inserção do produto 101": ["01-insercao.png"],
    "Atualização do estoque": ["02-atualizacao.png"],
    "Exclusão do produto 101": ["03-exclusao.png"],
    "Inserção com o sink pausado": ["04-sink-pausado.png"],
    "Consulta dos bancos com o sink pausado": ["06-consulta-origem.png", "07-consulta-destino.png"],
    "Retomada do sink": ["05-sink-retomado.png"],
}


def slide_title(slide):
    texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    return next((t for t in texts if t in SLIDES), None)


def replace(slide, picture, path, box):
    left, top, width, height = box
    _, rid = slide.part.get_or_add_image_part(str(path))
    picture._element.find(".//" + qn("a:blip")).set(qn("r:embed"), rid)
    w, h = Image.open(path).size
    scale = min(width / w, height / h)
    picture.width, picture.height = int(w * scale), int(h * scale)
    picture.left = left + (width - picture.width) // 2
    picture.top = top


def main():
    prs = Presentation(DECK)
    done = set()
    for slide in prs.slides:
        title = slide_title(slide)
        if title is None:
            continue
        files = [SHOTS / name for name in SLIDES[title]]
        missing = [f.name for f in files if not f.exists()]
        if missing:
            sys.exit(f"Capturas ausentes: {', '.join(missing)}")
        logo_limit = 3_000_000  # o logotipo da UFSM é a imagem pequena do cabeçalho
        pictures = sorted((sh for sh in slide.shapes if sh.shape_type == 13 and sh.width > logo_limit),
                          key=lambda sh: sh.left)
        if len(pictures) != len(files):
            sys.exit(f"O slide '{title}' tem {len(pictures)} capturas, esperado {len(files)}.")
        # Legenda: o texto logo abaixo da captura, acima da linha do rodapé.
        caption = max((sh for sh in slide.shapes if sh.has_text_frame and sh.text_frame.text
                       and pictures[0].top < sh.top < FOOTER), key=lambda sh: sh.top)
        for picture, path in zip(pictures, files):
            if len(files) == 1:
                box = (571_680, picture.top, 11_048_760, caption.top - GAP - picture.top)
            else:
                box = (picture.left, picture.top, picture.width, caption.top - GAP - picture.top)
            replace(slide, picture, path, box)
        done.add(title)
    if done != set(SLIDES):
        sys.exit(f"Slides não encontrados: {', '.join(sorted(set(SLIDES) - done))}")
    prs.save(DECK)
    print(f"{len(done)} slides atualizados em {DECK.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
