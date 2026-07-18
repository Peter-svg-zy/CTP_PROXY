# K线 CSV 及 MySQL 持久化改造说明

## 1. 改造结果

本次改造保留了 Strategy2 原有的“完整分钟K线逐根追加到本地 CSV”行为，并在同一根K线处理流程中增加 MySQL 入库。

当前数据流如下：

```text
CTP深度行情回调
  -> tickQueue
  -> get_tick / distribute_tick
  -> tick_to_Kline（合成1分钟K线）
  -> klineQueue
  -> get_Bar / distribute_Kline
  -> Strategy2.onBar
       1. 追加实时数据/{合约}_bar.csv
       2. INSERT ... ON DUPLICATE KEY UPDATE 写入 ctp_sys.bar_data
       3. 更新内存滑动窗口并运行 Aberration
```

CSV 或 MySQL 单侧失败时会分别输出警告。MySQL 故障不会阻止 CSV 保存、指标计算和策略运行；`onBar` 使用 `finally` 释放K线锁，避免异常导致合约后续K线永久阻塞。

## 2. 项目结构梳理

```text
CTP_PROXY/
├─ CTP_API/                         CTP行情、交易API封装及Windows/Linux动态库
├─ StrategyFloder/
│  ├─ Stragety1.py                 策略1（Tick策略）
│  └─ Stragety2.py                 策略2（1分钟K线、CSV、MySQL、Aberration）
├─ function_test_section/
│  ├─ sub_bar.py                   当前行情+交易综合启动入口
│  ├─ function.py                  Tick分发、K线合成、K线分发、下单和日志函数
│  ├─ UserStruct.py                MarketData、BarData、买卖类型等数据结构
│  ├─ Global_Param.py              队列、线程池、策略表、订阅表及账户全局状态
│  └─ 其他 *.py                    行情登录、交易登录、查询和功能测试入口
├─ con_file/
│  ├─ database.ini                 本机MySQL配置（已被Git忽略）
│  ├─ database.ini.example         可提交的数据库配置模板
│  ├─ ExchangeID.json              合约与交易所映射
│  └─ productInfo.ini              品种乘数、价位及手续费等信息
├─ 实时数据/                        全量已完成K线CSV
├─ 交易流水/                        各策略、各合约成交流水CSV
├─ bar_persistence.py              新增的MySQL K线持久化组件
├─ requirements.txt                Python依赖声明
├─ Global_Param.py                 旧入口使用的另一份全局配置
└─ Aberration.py / pure_test.py    示例和策略逻辑测试代码
```

注意：仓库中的策略文件名实际为 `Stragety2.py`，不是 `Strategy2.py`。本次沿用原文件名，避免破坏现有导入。

## 3. MySQL字段映射

本次代码直接适配本机已经存在的 `ctp_sys.bar_data`：

| bar_data字段 | 来源 | 说明 |
|---|---|---|
| `contract_name` | `BarData.instrumentID` | 合约代码 |
| `exchange` | Tick的`ExchangeID`，为空时查`ExchangeID.json` | 不再错误使用表默认的CFFEX |
| `interval` | `BarData.barType` | `min`映射成`1m`，其他周期也定义了映射 |
| `current_time` | `ActionDay + updateTime` | 已对齐的K线开始时间 |
| `open_price` | `openPrice` | 开盘价 |
| `high_price` | `highPrice` | 最高价 |
| `low_price` | `lowPrice` | 最低价 |
| `close_price` | `closePrice` | 收盘价 |
| `volume` | `volume` | 本根K线成交量 |
| `open_interest` | `openInterest` | K线结束前最新持仓量 |

表中唯一键为：

```sql
UNIQUE KEY uk_bar (contract_name, interval, current_time)
```

写入使用 `INSERT ... ON DUPLICATE KEY UPDATE`。同一合约、周期和开始时间的K线重复到达时不会新增重复行，而会刷新 OHLC、成交量和持仓量。

`lastVolume` 是合成K线时使用的累计成交量基准，现有表没有对应字段，因此只保留在 CSV，不写入 MySQL。

## 4. 本次文件修改

### 新增文件

- `bar_persistence.py`
  - 加载 INI 和环境变量配置。
  - 延迟建立 PyMySQL 连接并复用连接。
  - 写入前执行 `ping(reconnect=True)`。
  - 第一次写入失败时关闭连接、重连并仅重试一次。
  - 校验数据库名和表名，避免动态标识符造成SQL注入。
  - 将内部周期名称转换成表所需的 `1m`、`5m`、`1h` 等格式。
- `con_file/database.ini.example`
  - 不含密码的配置模板。
- `con_file/database.ini`
  - 当前机器的实际连接配置；已加入 `.gitignore`，不得提交。
- `requirements.txt`
  - 锁定 `PyMySQL==1.1.2`；该版本声明支持 Python 3.8，并已在本机 `CTP_1` 环境实测。
- `.gitignore`
  - 忽略含本地凭据的 `con_file/database.ini`。

### 修改文件

- `StrategyFloder/Stragety2.py`
  - CSV路径改为基于项目根目录的绝对路径，不再依赖启动目录。
  - 初始化 `MySQLBarWriter`，每根完整K线追加CSV后写入MySQL。
  - CSV的“当前时间”改为K线开始时间，而不是 `onBar` 执行时的系统时间。
  - CSV、MySQL异常分别隔离。
  - 使用 `finally` 确保释放 `kline_lock`。
- `function_test_section/UserStruct.py`
  - `BarData` 新增 `barTime`、`actionDay`、`tradingDay`。
- `function_test_section/function.py`
  - 合成新K线时保存交易所、ActionDay、TradingDay和完整K线开始时间。
  - 核心模块改为明确的包导入。
- `function_test_section/Global_Param.py`
  - `productInfo.ini` 与 `ExchangeID.json` 改为基于项目位置的绝对路径。
- `function_test_section/sub_bar.py`、`StrategyFloder/Stragety1.py`
  - 明确引用同一份 `function_test_section.Global_Param`，避免因启动目录不同产生两套队列和全局状态。

说明：`StrategyFloder/Stragety1.py` 在改造前已有 `release_lock()` 改为 `release()` 的本地修改，本次予以保留；本次只调整了该文件的全局配置导入。

## 5. 数据库配置

本机实际配置文件为：

```text
con_file/database.ini
```

配置格式参考：

```ini
[mysql]
enabled = true
host = 127.0.0.1
port = 3306
user = root
password = 请填写本机密码
database = ctp_sys
table = bar_data
charset = utf8mb4
connect_timeout = 3
```

支持以下环境变量覆盖 INI，生产部署时建议用环境变量传递密码：

```text
CTP_DB_CONFIG
CTP_DB_ENABLED
CTP_DB_HOST
CTP_DB_PORT
CTP_DB_USER
CTP_DB_PASSWORD
CTP_DB_NAME
CTP_DB_TABLE
CTP_DB_CHARSET
CTP_DB_CONNECT_TIMEOUT
```

关闭数据库入库但继续保存CSV：

```ini
enabled = false
```

## 6. 环境与运行方式

已确认 Conda 环境：

```text
环境名：CTP_1
Python：3.8.10
Python路径：C:\Users\29405\.conda\envs\CTP_1\python.exe
PyMySQL：已安装（conda list显示1.1.2）
MySQL：8.0.46，服务MySQL80正常运行
```

启动现有综合入口：

```powershell
conda activate CTP_1
cd D:\CTPprogram\CTP_PROXY\function_test_section
python sub_bar.py
```

项目当前只有在交易账户登录成功、`tdLogin_flag=True` 后才会分发 Tick 和 K线，这是原有逻辑，未改变。

## 7. 验证方法

程序收到跨分钟Tick并生成完整K线后，可在MySQL中执行：

```sql
SELECT
    contract_name,
    exchange,
    `interval`,
    `current_time`,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    open_interest,
    created_at
FROM ctp_sys.bar_data
ORDER BY `current_time` DESC
LIMIT 20;
```

MySQL中的 `interval` 和 `current_time` 可能被解析为关键字或内置函数，手写 SQL 时应像上面一样使用反引号。

CSV位于：

```text
D:\CTPprogram\CTP_PROXY\实时数据\{合约代码}_bar.csv
```

## 8. 已完成测试

1. 使用 `CTP_1` Python 对全部改动模块执行 `py_compile`，通过。
2. 从项目根目录导入并实例化 Strategy2，MySQL写入器和CSV绝对路径正确。
3. 使用真实本地 MySQL 写入合成K线两次：最终只有1行，收盘价被第二次写入更新，幂等行为正确。
4. 读取测试行确认字段映射正确：`CODEX_TEST / SHFE / 1m / 2000-01-01 09:30:00`。
5. 精确删除测试行后确认 `bar_data` 恢复为0行。
6. 使用模拟Tick跨分钟合成K线，确认交易所、ActionDay、TradingDay、K线时间、OHLC、成交量和持仓量正确。
7. 模拟MySQL异常，确认CSV仍写入且K线锁正常释放。

### Python 3.8 专项兼容性检查

- 使用项目实际解释器 Python 3.8.10 编译全部7个新增或修改的Python模块，全部通过。
- 实际导入 `bar_persistence`、Strategy2、K线结构、行情入口及分发函数，全部通过。
- 未使用 Python 3.9 的内置泛型写法（如 `list[str]`）、Python 3.10 的联合类型与模式匹配（如 `X | None`、`match/case`），也未使用 Python 3.11 的 `tomllib` 等接口。
- PyMySQL 1.1.2 的包元数据要求为 `Python >=3.8`；当前环境中的 pandas 2.0.3、psutil 7.2.2 也已在 Python 3.8.10 下实际导入成功。

## 9. 当前边界

- 只有“已完成”的分钟K线会在下一分钟首个Tick到来时进入队列；程序退出时仍在形成中的最后一根K线不会强制落盘。这是现有K线合成机制的边界。
- MySQL短暂断线会自动重连并重试一次；若数据库长时间不可用，该期间K线仍完整保存在CSV，但不会自动从CSV补录数据库。
- 当前仅 Strategy2 订阅并持久化1分钟K线；后续其他策略需要入库时，可直接复用 `MySQLBarWriter`。
- 当前持仓状态 `position` 只存在于进程内，程序重启后会回到0；这与K线持久化无关，但实盘运行前建议另行实现持仓恢复与账户持仓核对。
