# NEW EMPIRE

Фэнтезийная RTS с активной паузой. Идейный наследник Warcraft II: Tides of Darkness.

## Суть

NEW EMPIRE — не классическая RTS, а **симулятор империи нового типа**.
- Игрок не производит — он координирует.
- Вассалы — автономные колонии WC1-эпохи, они производят.
- Империя — экосистема. Ободрал сеть → потерял империю.

## Стек

- Python 3.11+
- Pygame 2.x
- numpy

## Структура
new_empire/
├── docs/ — канон (00–20)
├── data/ — базовый контент (JSON)
├── mods/ — DLC (папки + manifest.json)
├── assets/ — спрайты, звук, тайлы
├── src/
│ ├── backend/ — симуляция (без pygame)
│ └── frontend/ — рендер, ввод, UI
├── tests/ — pytest
└── tools/ — редактор карт, утилиты

## Правила

1. Frontend НЕ импортирует backend.
2. Backend НЕ импортирует pygame.
3. Мост — только через `src/main.py`.
4. Один файл = одна ответственность.
5. Канон — только в `docs/`.
6. `constants.py` — единственный файл с балансом.

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
python src/main.py