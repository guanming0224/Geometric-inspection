# Screw-to-Surface Gap Geometric Inspection Tool / 螺絲與平面間隙幾何檢測工具

**Language / 語言：** [English](#english) | [繁體中文](#繁體中文)

---

<a id="english"></a>

# English

This tool performs geometric inspection to check whether there is a gap between a screw or metal part and the surface of an object. Within a specified ROI (region of interest), it analyzes image edges and the dark-pixel ratio, locates the edge of the screw or metal part, and compares its distance to the object's reference surface line.

When the measured gap exceeds the configured threshold, the result is `separated`: the screw has come apart from the surface. If the gap is within the threshold, the screw or object is still seated against the surface and the result is `locked`. If the image does not provide enough edge information, the result is `unknown`.

## Files

| File | Description |
| --- | --- |
| `app/src/lock_geometry.py` | Core inspection logic: ROI normalization, edge detection, gap calculation, dark-pixel ratio calculation, and result drawing. |
| `app/src/lock_geometry_gui.py` | PyQt6 GUI: load images, open a camera, adjust the ROI and inspection parameters, and save annotated images. |
| `app/src/roi_preview.py` | Interactive preview widget: draw, move, and resize the ROI with the mouse. |
| `app/src/__init__.py` | Lets `app/src` be imported as a Python package. |
| `app/Data/last_region.json` | Generated automatically. Stores the last ROI, reference lines, and parameters, and is restored when the GUI starts. |
| `requirements.txt` | Python packages required to run the tool, with pinned versions. |

## Requirements

- Tested with Python 3.12.10
- The GUI runs directly on Windows
- A readable image or camera source is required

Install the packages:

```powershell
python -m pip install -r requirements.txt
```

Start the GUI:

```powershell
python -m app.src.lock_geometry_gui
```

## How It Works

For the ROI, the tool runs the following steps:

1. Crop the input image to the specified ROI.
2. Convert the ROI to grayscale.
3. Compute the dark-pixel ratio using the dark threshold.
4. Find horizontal edges with Gaussian blur and Canny edge detection.
5. Split the ROI at the split line into the screw / metal part region and the surface reference region.
6. Locate the metal edge and the surface reference line.
7. Compute the pixel distance between them as `gap_px`.
8. Compare `gap_px` with `gap_threshold_px` and output the seated or separated state.

## Main Parameters

| Parameter | Description |
| --- | --- |
| `x`, `y`, `w`, `h` | Relative position and size of the ROI in the image, in the range 0 to 1. |
| `gap_threshold_px` | Gap threshold in pixels. A gap above this value is judged as separated. |
| `dark_threshold_ratio` | Dark-pixel ratio threshold, used to help detect separation or shadow areas. |
| `dark_gray_threshold` | Grayscale threshold for dark pixels. Pixels below this value are treated as dark. |
| `mode` | Judgment mode: `gap`, `dark`, or `both`. |
| `metal_edge_count` | Number of metal edge candidates to keep. |
| `base_line_y` | Position of the surface reference line. If not set, it is searched automatically in the lower half of the ROI. |
| `red_line_y` | Optional red-line limit. If the metal edge crosses this line, the result is judged abnormal immediately. |
| `split_line_y` | Horizontal split line of the ROI, separating the metal edge search area from the surface reference search area. |

## GUI Guide

1. Click `Load Image` to load an image to inspect, or set the camera index and click `Start Camera` to use a live feed.
2. Draw the ROI directly on the preview so that it contains both the screw and the object surface:
   - Press and drag on an empty area to draw a new ROI.
   - Drag inside the box to move it; drag an edge or corner handle to resize it.
   - Arrow keys nudge by 1 px; `Shift` + arrow keys nudge by 10 px.
   - The `ROI` panel in the sidebar shows the current pixel coordinates and 0–1 ratios, which can be used directly as the `--x --y --w --h` arguments in headless mode. Click `Reset ROI` to return to the default position.
3. Set the judgment mode, gap threshold, dark-pixel ratio, and edge count under `Geometry Rules`.
4. Set the reference line, red line, and split line under `Reference Lines`. With Auto, the tool finds the corresponding position itself.
5. Check `Prediction` and the detail information on the right.
6. Click `Save Overlay` to save an annotated image with the ROI, edge lines, and reference lines.
7. The ROI, reference line settings, and parameters are saved automatically to `app/Data/last_region.json` after each adjustment and restored the next time the GUI starts. Delete that file to return to the defaults.

## Python Example

```python
import cv2

from app.src.lock_geometry import (
    analyze_lock_geometry_regions,
    default_lock_geometry_region,
    draw_lock_geometry_overlay,
)

frame = cv2.imread("sample.jpg")

regions = [
    default_lock_geometry_region(
        1,
        {
            "x": 0.35,
            "y": 0.35,
            "w": 0.25,
            "h": 0.20,
            "mode": "both",
            "gap_threshold_px": 6,
        },
    )
]

analyses = analyze_lock_geometry_regions(frame, regions)
annotated = draw_lock_geometry_overlay(frame.copy(), analyses)

for analysis in analyses:
    print(analysis.result.prediction, analysis.result.reason)

cv2.imwrite("sample_geometry_overlay.jpg", annotated)
```

## Results

| Result | Meaning |
| --- | --- |
| `locked` | The gap is within the threshold; the screw or object is still seated against the surface. |
| `separated` | The gap exceeds the threshold, or the red-line limit was triggered; the screw has separated from the surface. |
| `unknown` | Not enough edge or reference-line information could be obtained from the image; adjust the ROI, lighting, or parameters. |

## Notes

- `gap_threshold_px` depends on camera resolution, lens distance, and ROI size, so it must be calibrated for your actual setup.
- Lighting changes affect edges and the dark-pixel ratio; inspect under fixed lighting.
- If the screw edge or surface boundary is unclear, adjust the ROI, split line, or reference line settings.
- This tool uses classical image processing and geometric rules; no trained model is required.

## License

Released under the [MIT License](LICENSE).

---

<a id="繁體中文"></a>

# 繁體中文

這份程式用於幾何檢測，主要目的為檢查螺絲或金屬件與物件平面之間是否存在間隙。程式會在指定的 ROI 區域內分析影像邊緣與暗部比例，找出螺絲或金屬件邊緣，再與物件平面的基準線進行距離比較。

當量測出的間隙大於設定的界線值時，系統會判定螺絲與平面已經分離，狀態為 `separated`。如果間隙仍在設定界線值內，則表示螺絲或物件仍貼合於平面，狀態為 `locked`。如果影像中無法取得足夠的邊緣資訊，結果會顯示為 `unknown`。

## 檔案說明

| 檔案 | 說明 |
| --- | --- |
| `app/src/lock_geometry.py` | 幾何檢測核心邏輯，負責 ROI 正規化、邊緣偵測、間隙計算、暗部比例計算與結果繪製。 |
| `app/src/lock_geometry_gui.py` | PyQt6 圖形化操作介面，可載入圖片、開啟相機、調整 ROI 與檢測參數，並儲存標註後的影像。 |
| `app/src/roi_preview.py` | 可互動的預覽元件，支援在畫面上以滑鼠拖曳畫出、移動與縮放 ROI。 |
| `app/src/__init__.py` | 讓 `app/src` 資料夾可作為 Python package 被匯入使用。 |
| `app/Data/last_region.json` | 程式自動產生，記錄上次使用的 ROI 標註位置、基準線與判斷參數，啟動 GUI 時自動還原。 |
| `requirements.txt` | 執行此工具需要安裝的 Python 套件，已固定指定版本。 |

## 環境需求

- Python 3.12.10 已測試通過
- Windows 環境可直接執行 GUI
- 需要可讀取的圖片或相機影像來源

安裝套件：

```powershell
python -m pip install -r requirements.txt
```

啟動 GUI：

```powershell
python -m app.src.lock_geometry_gui
```

## 判斷方式

程式會對 ROI 區域執行以下流程：

1. 將輸入影像裁切成指定 ROI。
2. 將 ROI 轉為灰階影像。
3. 使用暗部閾值計算暗像素比例。
4. 使用 Gaussian blur 與 Canny edge 找出水平邊緣。
5. 依照分割線將 ROI 分成螺絲或金屬件區域與平面基準區域。
6. 找出金屬邊緣位置與平面基準線位置。
7. 計算兩者的像素距離，得到 `gap_px`。
8. 將 `gap_px` 與 `gap_threshold_px` 比較，輸出貼合或分離狀態。

## 主要參數

| 參數 | 說明 |
| --- | --- |
| `x`, `y`, `w`, `h` | ROI 在影像中的相對位置與大小，數值範圍為 0 到 1。 |
| `gap_threshold_px` | 間隙判斷界線值，單位為像素。超過此值會判定為分離。 |
| `dark_threshold_ratio` | 暗部比例界線值，可輔助判斷是否有分離或陰影區域。 |
| `dark_gray_threshold` | 灰階暗部閾值，低於此值的像素會被視為暗部。 |
| `mode` | 判斷模式，可使用 `gap`、`dark` 或 `both`。 |
| `metal_edge_count` | 要保留的金屬邊緣候選數量。 |
| `base_line_y` | 平面基準線位置。未設定時會自動從 ROI 下半部尋找。 |
| `red_line_y` | 可選的紅線限制。金屬邊緣越過此線時會直接判定為異常。 |
| `split_line_y` | ROI 的上下分割線，用來區分金屬邊緣搜尋區與平面基準搜尋區。 |

## GUI 操作說明

1. 按下 `Load Image` 載入待檢測圖片，或設定相機編號後按下 `Start Camera` 使用即時影像。
2. 直接在預覽畫面上框選 ROI，使範圍包含螺絲與物件平面：
   - 在空白處按住滑鼠拖曳，畫出新的 ROI。
   - 在框內拖曳可移動整個框；拉框的邊或四角把手可調整大小。
   - 方向鍵微調 1 px，`Shift` + 方向鍵微調 10 px。
   - 側欄 `ROI` 區塊會顯示目前的像素座標與 0~1 比例值，可直接拿來當作無視窗模式的 `--x --y --w --h` 參數；按 `Reset ROI` 可回到預設位置。
3. 在 `Geometry Rules` 設定判斷模式、間隙界線值、暗部比例與邊緣數量。
4. 在 `Reference Lines` 設定基準線、紅線與分割線；若使用 Auto，程式會自動尋找對應位置。
5. 觀察右側 `Prediction` 與細節資訊。
6. 按下 `Save Overlay` 可儲存含 ROI、邊緣線與基準線的標註影像。
7. ROI 位置、基準線設定與判斷參數會在調整後自動存到 `app/Data/last_region.json`，下次啟動 GUI 會直接還原上次的標註位置；刪除該檔案即可回到預設值。

## Python 使用範例

```python
import cv2

from app.src.lock_geometry import (
    analyze_lock_geometry_regions,
    default_lock_geometry_region,
    draw_lock_geometry_overlay,
)

frame = cv2.imread("sample.jpg")

regions = [
    default_lock_geometry_region(
        1,
        {
            "x": 0.35,
            "y": 0.35,
            "w": 0.25,
            "h": 0.20,
            "mode": "both",
            "gap_threshold_px": 6,
        },
    )
]

analyses = analyze_lock_geometry_regions(frame, regions)
annotated = draw_lock_geometry_overlay(frame.copy(), analyses)

for analysis in analyses:
    print(analysis.result.prediction, analysis.result.reason)

cv2.imwrite("sample_geometry_overlay.jpg", annotated)
```

## 輸出結果

| 結果 | 意義 |
| --- | --- |
| `locked` | 間隙在設定界線值內，判定螺絲或物件仍貼合於平面。 |
| `separated` | 間隙超過設定界線值，或觸發紅線限制，判定螺絲與平面已分離。 |
| `unknown` | 無法從影像中取得足夠邊緣或基準線資訊，需重新調整 ROI、光源或參數。 |

## 注意事項

- `gap_threshold_px` 會受到相機解析度、鏡頭距離與 ROI 大小影響，使用前需要依照實際設備校正。
- 光源變化會影響邊緣與暗部比例，建議在固定光源條件下檢測。
- 若螺絲邊緣或平面邊界不清楚，請調整 ROI、分割線或基準線設定。
- 此工具使用傳統影像處理與幾何規則，不需要訓練模型。

## 授權

本專案以 [MIT License](LICENSE) 授權釋出。
