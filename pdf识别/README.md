# PDF 内容、表格、图表提取工程

这是一个面向批量处理的 PDF 解析项目，用来从 PDF 中提取：

- 正文文本和页面级 Markdown
- 表格数据，导出为 CSV 和一个汇总 XLSX
- 内嵌图片
- 由矢量线条、矩形等绘制对象组成的图表候选区域截图
- 页面与文档元数据，导出为 JSON

项目默认不依赖云服务，适合本地处理财报、研究报告、运营资料、论文和产品文档。

## 目录结构

```text
pdf识别/
  pyproject.toml
  requirements.txt
  requirements-ocr.txt
  README.md
  src/pdf_extractor/
    __main__.py
    cli.py
    extractor.py
    models.py
    options.py
    exporters.py
    utils.py
  samples/
    README.md
  tests/
    test_options.py
```

## 安装

建议使用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

如果需要识别扫描版 PDF，可以额外安装 OCR 依赖：

```powershell
pip install -e ".[ocr]"
```

OCR 还需要安装 Tesseract 系统程序，并确保 `tesseract` 命令在 PATH 中。

## 使用

从当前工程目录运行：

```powershell
python -m pdf_extractor .\samples\demo.pdf -o .\outputs\demo
```

指定页码：

```powershell
python -m pdf_extractor .\samples\demo.pdf -o .\outputs\demo --pages 1,3-5
```

对扫描页启用自动 OCR：

```powershell
python -m pdf_extractor .\samples\scan.pdf -o .\outputs\scan --ocr auto --ocr-lang chi_sim+eng
```

只提取文本，不提取表格和图表：

```powershell
python -m pdf_extractor .\samples\demo.pdf -o .\outputs\text-only --no-tables --no-figures
```

## 输出

一次解析会生成类似结构：

```text
outputs/demo/
  document.md
  metadata.json
  pages/
    page_001.txt
  tables/
    page_001_table_01.csv
    tables.xlsx
  figures/
    page_001_image_01.png
    page_002_chart_01.png
```

关键文件：

- `document.md`：按页面组织的可读结果，包含文本、表格路径、图片路径。
- `metadata.json`：结构化结果，适合后续进入数据库或知识库。
- `tables/*.csv`：每个表格独立文件。
- `tables/tables.xlsx`：所有表格按 Sheet 汇总。
- `figures/*`：PDF 内嵌图片和图表候选裁剪。

## 图表提取说明

PDF 中的图表通常有两种形态：

- 作为图片嵌入 PDF：项目会直接抽取原始图片。
- 由 PDF 矢量指令绘制：项目会根据页面线条、矩形、路径的密集区域生成图表候选截图。

矢量图表识别是启发式的，可能把复杂表格边框也识别为图表候选。工程中已用表格边界做了基本过滤，但对版式复杂的 PDF，建议人工复核 `figures/` 目录。

## 开发检查

```powershell
python -m compileall src tests
python -m pytest
```

`pytest` 属于开发依赖，未安装时可以先只运行 `compileall`。
