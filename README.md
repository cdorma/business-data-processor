# 业务数据自动化处理工具

模拟企业数据清洗、转换和报表生成的 ETL 流水线工具。

## 功能

- 支持 CSV / Excel 文件读取
- 自动去重、缺失值补全、异常值过滤
- 字段映射与格式标准化，自动计算派生字段
- 生成文本统计报表并导出处理后的 CSV

## 快速开始

```bash
pip install pandas openpyxl
python business_data_processor.py
```

首次运行会自动生成模拟数据并处理，输出 `processed_data.csv` 和 `processed_data.report.txt`。

## 处理真实数据

```python
from business_data_processor import run_pipeline

run_pipeline("你的业务数据.csv", output_dir="./output")
```

## 清洗规则

| 步骤 | 规则 |
|------|------|
| 去重 | 移除完全重复的行 |
| 缺失值 | 数值列用中位数填充，文本列填"未知" |
| 异常值 | 剔除数量 ≤0、单价超过 99 分位数、折扣率超出 [0, 0.8] 的记录 |

## 输出文件

- `processed_data.csv` — 清洗并转换后的数据
- `processed_data.report.txt` — 汇总报表（总订单数、金额指标、区域/品类 TOP 排名）
