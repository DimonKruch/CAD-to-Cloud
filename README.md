# CAD to Cloud (DXF -> LAS+CAD)

## Что делает

Утилита добавляет линии/границы из **DXF** в **облако точек LAS/LAZ**: на основе полилиний создаются CAD-точки и сохраняется **новое облако LAS с CAD-элементами**.

Идея: вместо отдельного `XYZ` (который потом нужно импортировать в CloudCompare) программа сразу создаёт итоговое облако `LAS+CAD`, которое можно открыть как обычный `.las`.

Поддерживает:
- много полилиний/линий в одном DXF
- режимы высоты для CAD-точек:
  - "По рельефу" (Z подбирается по соседям из облака)
  - "Над рельефом" (как "по рельефу", но с добавкой Z)
- если в DXF у вершин уже есть Z (топосъемка), можно использовать их напрямую
- выбор слоёв DXF и цвета по слоям

## Установка (для запуска из исходников)

```powershell
pip install -r requirements.txt
```

## Использование

### GUI (рекомендуется)

```powershell
python cad_boundary_gui.py
```

Дальше:
- выбери DXF
- выбери LAS/LAZ
- выбери режим высоты
- нажми **"Сгенерировать и выгрузить LAS+CAD"**

Результат:
- создаётся новый файл `.las`, в котором к исходным точкам облака добавлены CAD-точки
- исходное облако не изменяется

## Выходные файлы

По умолчанию имя выходного файла формируется автоматически по режиму:
- `*_relief_with_cad.las`
- `*_Z_0.2_with_cad.las`

Если файл уже существует, автоматически подбирается имя с суффиксом `_2`, `_3`, ...

## Импорт в CloudCompare

Откройте исходное облако (если нужно) и выходной `*_with_cad.las`.

## CLI (legacy/advanced)

CLI-скрипт оставлен для продвинутого использования. Он умеет писать `XYZ/XYZRGB` и другие варианты вывода.

### Пример: границы без высот, но повторяем рельеф (XYZ)

```powershell
python cad_boundary_to_cc.py --dxf boundary.dxf --cloud cloud.laz --out boundary_surface.xyz --assume-same-crs --z-mode surface_p10 --z-radius-m 2.0 --z-k 64 --z-offset 0.2 --step-m 1.0
```

Рекомендации:
- `--z-radius-m`: 1..3 м
- `--z-k`: 32..128
- `--z-offset`: 0.05..0.3 м

### 3) Топосъемка DXF с высотами (используем Z из DXF)

```powershell
python cad_boundary_to_cc.py --dxf topo.dxf --cloud cloud.laz --out topo.xyz --assume-same-crs --prefer-dxf-z --step-m 1.0
```

`--prefer-dxf-z` включает режим: если в DXF есть Z, они используются, облако нужно только для формата входа (и проверки), но Z не вычисляется.

### 4) Несколько границ в одном DXF и вывод идентификатора линии

```powershell
python cad_boundary_to_cc.py --dxf many.dxf --cloud cloud.laz --out many.xyz --assume-same-crs --z-mode p95 --write-poly-id
```

В этом режиме в `XYZ` будет 4-й столбец (ID полилинии).

## Сборка в EXE (Windows)

В проекте есть готовый spec для PyInstaller:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --clean --noconfirm "build/CAD to Cloud.spec"
```

Готовый EXE будет в:

`dist/CAD to Cloud/CAD to Cloud.exe`

## Примечания

- Для режима `surface_p10` загружаются точки облака только внутри bbox границ. По умолчанию ограничение `--las-max-points 2000000` (если точек больше, будет случайная подвыборка). Если нужно, можно поставить `--las-max-points 0`.
