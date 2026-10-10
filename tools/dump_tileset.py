import os, sys
import pygame

TILE = 128
SRC = "assets/terrain/summer_hd.png"
OUT = "tools/tileset_debug.png"
COLS_PER_ROW = 20
LABEL_H = 16


def main():
    pygame.init()
    pygame.display.set_mode((64, 64))
    pygame.font.init()
    font = pygame.font.SysFont(None, 14)

    sheet = pygame.image.load(SRC).convert_alpha()
    sw, sh = sheet.get_size()
    cols, rows = sw // TILE, sh // TILE
    print(f"Атлас {sw}x{sh} → {cols}x{rows} = {cols*rows} тайлов")

    thumb = 64
    total = cols * rows
    out_cols = min(COLS_PER_ROW, total)
    out_rows = (total + out_cols - 1) // out_cols
    canvas = pygame.Surface((out_cols * thumb, out_rows * (thumb + LABEL_H)))
    canvas.fill((0, 0, 0))

    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            tile = sheet.subsurface(pygame.Rect(c * TILE, r * TILE, TILE, TILE))
            small = pygame.transform.smoothscale(tile, (thumb, thumb))
            ox = (idx % out_cols) * thumb
            oy = (idx // out_cols) * (thumb + LABEL_H)
            canvas.blit(small, (ox, oy))
            lbl = font.render(str(idx), True, (255, 255, 0))
            canvas.blit(lbl, (ox + 2, oy + thumb))

    pygame.image.save(canvas, OUT)
    print(f"Сохранено: {OUT}")


if __name__ == "__main__":
    sys.exit(main())