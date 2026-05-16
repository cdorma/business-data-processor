"""
业务数据自动化处理工具
功能：数据读取 → 数据清洗 → 格式转换 → 报表导出
"""
import logging
import sys
from pathlib import Path

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# 日志配置（处理 Windows 控制台编码问题）
# ---------------------------------------------------------------------------
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("DataProcessor")

# ---------------------------------------------------------------------------
# 第一部分：数据读取
# ---------------------------------------------------------------------------
def read_source_file(file_path: str) -> pd.DataFrame:
    """根据文件扩展名自动识别并读取 CSV 或 Excel 文件。"""
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == ".csv":
        log.info("识别为 CSV 文件，正在读取: %s", path.name)
        df = pd.read_csv(path, encoding="utf-8-sig")
    elif ext in (".xlsx", ".xls"):
        log.info("识别为 Excel 文件，正在读取: %s", path.name)
        df = pd.read_excel(path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}（仅支持 .csv / .xlsx / .xls）")

    log.info("读取完成：%d 行 × %d 列", len(df), len(df.columns))
    return df


def generate_sample_data(output_dir: str = ".") -> str:
    """生成一份模拟业务数据文件，用于功能演示。"""
    np.random.seed(42)
    n = 200

    data = {
        "订单ID": [f"ORD-{i:04d}" for i in range(n)],
        "订单日期": pd.date_range("2025-01-01", periods=n, freq="12h").strftime("%Y-%m-%d %H:%M:%S"),
        "客户名称": np.random.choice(["张三", "李四", "王五", "赵六", "钱七", "孙八"], n),
        "产品类别": np.random.choice(["办公用品", "电子产品", "家具", "食品"], n),
        "数量": np.random.randint(1, 20, n),
        "单价": np.round(np.random.uniform(10, 500, n), 2),
        "折扣率": np.round(np.random.uniform(0.0, 0.3, n), 2),
        "销售区域": np.random.choice(["华北", "华东", "华南", "华西", None], n),
    }
    df = pd.DataFrame(data)

    # 人为引入一些脏数据，用于测试清洗功能
    # 1. 重复行（2 条）
    df = pd.concat([df, df.iloc[:2]], ignore_index=True)
    # 2. 缺失值：在"销售区域"已有 None 的基础上，再打掉几个单元格
    df.loc[[5, 42, 99], "数量"] = np.nan
    df.loc[[12, 88], "单价"] = np.nan
    # 3. 异常值
    df.loc[10, "数量"] = -5          # 负数
    df.loc[25, "单价"] = 999999.0    # 明显偏高
    df.loc[77, "折扣率"] = 1.5        # 超过合理范围

    out = Path(output_dir) / "sample_business_data.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    log.info("已生成模拟数据: %s (%d 行)", out, len(df))
    return str(out)

# ---------------------------------------------------------------------------
# 第二部分：数据清洗
# ---------------------------------------------------------------------------
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """对原始数据进行去重、缺失值补全、异常值过滤。"""
    before = len(df)
    log.info("开始数据清洗，原始行数: %d", before)

    # --- 去重 ---
    dup_mask = df.duplicated()
    dup_count = dup_mask.sum()
    if dup_count:
        df = df.drop_duplicates().reset_index(drop=True)
        log.info("  去重: 删除 %d 条重复记录", dup_count)

    # --- 缺失值补全 ---
    na_before = df.isna().sum().sum()
    if na_before:
        for col in df.select_dtypes(include=[np.number]).columns:
            if df[col].isna().any():
                df[col] = df[col].fillna(df[col].median())
        for col in df.select_dtypes(exclude=[np.number]).columns:
            if df[col].isna().any():
                df[col] = df[col].fillna("未知")
        log.info("  缺失值补全: 共填充 %d 个空值（数值列用中位数，文本列用'未知'）", na_before)

    # --- 异常值过滤 ---
    anomaly_count = 0
    if "数量" in df.columns:
        neg = (df["数量"] <= 0).sum()
        df = df[df["数量"] > 0]
        anomaly_count += neg
    if "单价" in df.columns:
        upper = df["单价"].quantile(0.99)
        high = (df["单价"] > upper).sum()
        df = df[df["单价"] <= upper]
        anomaly_count += high
    if "折扣率" in df.columns:
        bad = ((df["折扣率"] < 0) | (df["折扣率"] > 0.8)).sum()
        df = df[(df["折扣率"] >= 0) & (df["折扣率"] <= 0.8)]
        anomaly_count += bad

    if anomaly_count:
        log.info("  异常值过滤: 共剔除 %d 条异常记录", anomaly_count)

    after = len(df)
    log.info("清洗完成，当前行数: %d（共减少 %d 行）", after, before - after)
    return df.reset_index(drop=True)

# ---------------------------------------------------------------------------
# 第三部分：格式转换 & 字段映射
# ---------------------------------------------------------------------------
FIELD_MAP = {
    "订单ID":   "order_id",
    "订单日期": "order_date",
    "客户名称": "customer",
    "产品类别": "category",
    "数量":     "qty",
    "单价":     "unit_price",
    "折扣率":  "discount",
    "销售区域": "region",
}

def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    """字段映射、类型标准化、派生字段计算。"""
    log.info("开始格式转换与字段映射")

    # --- 字段重命名 ---
    df = df.rename(columns=FIELD_MAP)
    log.info("  字段映射完成: %d 个字段已重命名", len(FIELD_MAP))

    # --- 类型标准化 ---
    if "order_date" in df.columns:
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    if "qty" in df.columns:
        df["qty"] = df["qty"].astype(int)
    if "unit_price" in df.columns:
        df["unit_price"] = df["unit_price"].round(2)
    if "discount" in df.columns:
        df["discount"] = df["discount"].round(4)

    # --- 派生字段：实付金额 = 数量 × 单价 × (1 - 折扣率) ---
    if all(c in df.columns for c in ["qty", "unit_price", "discount"]):
        df["actual_amount"] = (df["qty"] * df["unit_price"] * (1 - df["discount"])).round(2)
        log.info("  派生字段 'actual_amount' (实付金额) 已生成")

    # --- 月份维度 ---
    if "order_date" in df.columns:
        df["order_month"] = df["order_date"].dt.to_period("M").astype(str)

    log.info("转换完成: %d 行 × %d 列", len(df), len(df.columns))
    return df

# ---------------------------------------------------------------------------
# 第四部分：报表导出
# ---------------------------------------------------------------------------
def generate_summary(df: pd.DataFrame) -> str:
    """生成文本汇总统计并返回字符串。"""
    lines = []
    lines.append("=" * 50)
    lines.append("           业 务 数 据 汇 总 报 表")
    lines.append("=" * 50)
    lines.append(f"总订单数:        {len(df)}")
    lines.append(f"涵盖月份:        {df['order_month'].nunique() if 'order_month' in df.columns else 'N/A'}")
    lines.append(f"客户数:          {df['customer'].nunique() if 'customer' in df.columns else 'N/A'}")
    lines.append("")

    if "actual_amount" in df.columns:
        lines.append("--- 金额指标 ---")
        lines.append(f"订单总额(原价):  { (df['qty'] * df['unit_price']).sum():>12,.2f}")
        lines.append(f"实付总额:        {df['actual_amount'].sum():>12,.2f}")
        lines.append(f"平均折扣率:      {df['discount'].mean() * 100:>10.2f}%")
        lines.append(f"客单价(均值):    {df['actual_amount'].mean():>12,.2f}")

    if "region" in df.columns and "actual_amount" in df.columns:
        lines.append("")
        lines.append("--- 区域销售 TOP ---")
        region_stats = (
            df.groupby("region")["actual_amount"]
            .sum()
            .sort_values(ascending=False)
        )
        for region, amount in region_stats.items():
            lines.append(f"  {region:<8} {amount:>12,.2f}")

    if "category" in df.columns and "actual_amount" in df.columns:
        lines.append("")
        lines.append("--- 品类销售分布 ---")
        cat_stats = (
            df.groupby("category")["actual_amount"]
            .sum()
            .sort_values(ascending=False)
        )
        for cat, amount in cat_stats.items():
            lines.append(f"  {cat:<8} {amount:>12,.2f}")

    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)


def export_results(df: pd.DataFrame, output_path: str) -> str:
    """导出清洗并转换后的数据为 CSV 文件，同时输出统计报表。"""
    # 1. 写 CSV
    csv_path = Path(output_path).with_suffix(".csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    log.info("处理结果已导出: %s", csv_path)

    # 2. 写统计报表
    report_path = csv_path.with_suffix(".report.txt")
    report = generate_summary(df)
    report_path.write_text(report, encoding="utf-8")
    log.info("统计报表已导出: %s", report_path)
    log.info("%s", report)

    return str(csv_path)

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def run_pipeline(input_file: str, output_dir: str = "."):
    """执行完整 ETL 流水线。"""
    log.info("========== 业务数据自动化处理 启动 ==========")

    # 如果输入文件不存在，自动生成模拟数据
    if not Path(input_file).exists():
        log.warning("输入文件不存在，将自动生成模拟数据")
        input_file = generate_sample_data(output_dir)

    df_raw = read_source_file(input_file)
    df_clean = clean_data(df_raw)
    df_transformed = transform_data(df_clean)
    export_results(df_transformed, str(Path(output_dir) / "processed_data"))

    log.info("========== 处理完毕 ==========")

# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 首次运行会自动生成 sample_business_data.csv 并处理
    run_pipeline("sample_business_data.csv", output_dir=".")
