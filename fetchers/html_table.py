"""
极简、零第三方依赖的 HTML 表格解析器(只用标准库 html.parser)。

之前用正则抓 Farside 页面 "Total" 行的做法太脆弱——前端框架一换class名/换空白
格式,正则就直接失配。这里改成真正解析 DOM 结构:把所有 <table> 解析成
list[list[str]] 的行列结构,上层再按语义(找含"Total"的行)去取值,
对空白/嵌套标签/属性变化都不敏感。
"""
from __future__ import annotations
from html.parser import HTMLParser


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._in_table = 0
        self._cur_table: list[list[str]] = []
        self._cur_row: list[str] = []
        self._in_cell = False
        self._cell_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table += 1
            self._cur_table = []
        elif tag == "tr" and self._in_table:
            self._cur_row = []
        elif tag in ("td", "th") and self._in_table:
            self._in_cell = True
            self._cell_text = []

    def handle_endtag(self, tag):
        if tag == "table" and self._in_table:
            self._in_table -= 1
            if self._in_table == 0:
                self.tables.append(self._cur_table)
        elif tag == "tr" and self._in_table:
            if self._cur_row:
                self._cur_table.append(self._cur_row)
        elif tag in ("td", "th") and self._in_table:
            self._cur_row.append("".join(self._cell_text).strip())
            self._in_cell = False

    def handle_data(self, data):
        if self._in_cell:
            self._cell_text.append(data)


def extract_tables(html: str) -> list[list[list[str]]]:
    """返回页面里所有表格,每个表格是 list[row], row 是 list[cell_text]。"""
    if not html:
        return []
    parser = _TableParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - 容错优先,解析失败就返回已收集到的部分
        pass
    return parser.tables


def find_row_containing(tables: list[list[list[str]]], keyword: str) -> list[str] | None:
    """在所有表格里找第一行"任意单元格包含 keyword"的行,返回该行。"""
    for table in tables:
        for row in table:
            if any(keyword.lower() in cell.lower() for cell in row):
                return row
    return None


def last_numeric_cell(row: list[str]) -> float | None:
    """从一行里找最后一个能解析成数字的单元格(常见于 Total 行末尾就是合计值)。"""
    for cell in reversed(row):
        cleaned = cell.replace(",", "").replace("(", "-").replace(")", "").strip()
        if cleaned in ("", "-", "—"):
            continue
        try:
            return float(cleaned)
        except ValueError:
            continue
    return None
