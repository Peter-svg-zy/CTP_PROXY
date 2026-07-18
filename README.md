# CTP_PROXY 项目说明

## 1. 项目简介

基于上期技术 CTP API 的 Python 量化交易示例项目，包含行情连接、交易连接、Tick分发、分钟K线合成、策略执行、委托下单、成交记录、持仓查询以及K线持久化等功能。

项目当前的主要运行链路位于 `function_test_section`，其中 `sub_bar.py` 同时初始化行情和交易接口，并加载 Strategy1、Strategy2。Strategy2 使用实时Tick合成1分钟K线，执行 Aberration（布林带突破）逻辑，同时将完整K线追加到本地CSV并写入MySQL。

当前已验证的运行环境：

```text
操作系统：Windows
Conda环境：CTP_1
Python：3.8.10（64位）
CTP API：项目内置Windows .pyd/.dll及Linux .so
MySQL：8.0.46
MySQL驱动：PyMySQL 1.1.2
```

## 2. 项目目录

```text
CTP_PROXY/
├─ CTP_API/
│  ├─ thostmduserapi.py / _thostmduserapi.pyd
│  ├─ thosttraderapi.py / _thosttraderapi.pyd
│  ├─ thostmduserapi_se.dll
│  ├─ thosttraderapi_se.dll
│  ├─ linux/                         Linux版本动态库和Python接口
│  └─ CTP接口头文件及官方帮助文档
│
├─ StrategyFloder/
│  ├─ Stragety1.py                  Strategy1：Tick事件示例策略
│  └─ Stragety2.py                  Strategy2：K线、Aberration及持久化
│
├─ function_test_section/
│  ├─ sub_bar.py                    当前行情+交易综合启动入口
│  ├─ function.py                   Tick/K线分发、K线合成、下单、日志等
│  ├─ Global_Param.py               当前主链路使用的全局状态和队列
│  ├─ UserStruct.py                 MarketData、BarData、订单和持仓结构
│  ├─ login_md.py / Md_data.py      行情登录及行情测试
│  ├─ td_login.py                   交易登录测试
│  ├─ td_order*.py                  报单测试
│  ├─ td_query*.py                  产品和合约查询测试
│  ├─ queryInvserPosition.py        持仓查询测试
│  └─ K线CSV及MySQL持久化改造说明.md  K线持久化专项说明
│
├─ con_file/
│  ├─ productInfo.ini               品种乘数、最小价位、手续费等信息
│  ├─ ExchangeID.json               合约代码与交易所映射
│  ├─ database.ini                  本机MySQL配置，已被Git忽略
│  ├─ database.ini.example          可提交的数据库配置模板
│  └─ *.con                         CTP API会话和订阅状态文件
│
├─ 实时数据/                         各合约完整K线CSV
├─ 交易流水/                         各策略、各合约成交记录CSV
├─ bar_persistence.py               MySQL K线持久化组件
├─ requirements.txt                 新增依赖声明
├─ Global_Param.py / function.py    旧版或其他入口使用的根目录模块
├─ Aberration.py / Aber_strategy.py Aberration示例代码
├─ pure_test.py                     策略逻辑示例测试
└─ README.md                        本文档
```

## 3. 核心运行架构

### 3.1 初始化

综合入口 `function_test_section/sub_bar.py` 中的 `CTP_T` 负责：

1. 创建 Strategy1 和 Strategy2，并保存到 `g.strategy_map`。
2. 合并所有策略需要订阅的合约及K线周期。
3. 初始化各合约的分钟K线容器。
4. 创建成交记录CSV和资源监控结构。
5. 分别连接CTP行情前置和交易前置。

当前策略订阅情况：

| 策略 | 策略编号 | 合约 | 数据类型 | 主要功能 |
|---|---:|---|---|---|
| Strategy1 | 1 | `au2608` | Tick | Tick策略框架示例 |
| Strategy2 | 2 | `rb2610` | Tick + 1分钟K线 | Aberration、CSV、MySQL |

合约代码目前直接写在策略构造函数中，切换合约时需要修改对应策略的 `subID`。

### 3.2 行情与K线数据流

```text
CTP OnRtnDepthMarketData
  -> g.tickQueue
  -> get_tick
  -> distribute_tick
       ├─ save_tick -> strategy.onQuote
       └─ tick_to_Kline
             -> g.klineQueue（分钟切换时推送上一根完整K线）
             -> get_Bar
             -> distribute_Kline
             -> save_Kline
             -> Strategy2.onBar
                  ├─ 追加CSV
                  ├─ 写入MySQL
                  └─ 执行Aberration
```

Tick累计成交量会转换成本根分钟K线成交量；OHLC和持仓量在分钟内随Tick更新。只有收到下一分钟的第一个Tick后，上一根分钟K线才被视为完成并推送。

项目当前在 `tdLogin_flag=True` 后才分发Tick和K线，因此只连接行情而未成功登录交易账户时，不会执行策略和K线持久化。

### 3.3 全局状态

当前主链路统一使用 `function_test_section.Global_Param`，其中保存：

- 行情和交易API实例。
- 策略、委托、持仓及持仓明细字典。
- Tick队列和K线队列。
- 当前分钟K线容器。
- 合约订阅集合与K线周期集合。
- 买一、卖一对手价字典。
- 行情处理线程池。
- 交易日、FrontID、SessionID、OrderRef等会话信息。

根目录仍存在另一份 `Global_Param.py`。当前综合入口和两个策略已明确引用 `function_test_section.Global_Param`，以免不同启动目录产生两套互不相通的队列和状态。

## 4. Strategy2策略说明

Strategy2 位于 `StrategyFloder/Stragety2.py`，当前固定参数为：

```text
订阅合约：rb2610
K线周期：1分钟
布林带周期：88
标准差倍数：2
每次下单数量：1手
内存K线最大行数：98
```

### 4.1 Aberration逻辑

- 无持仓时：
  - 当前收盘价大于等于上一根K线对应的布林上轨，买开。
  - 当前收盘价小于等于上一根K线对应的布林下轨，卖开。
- 持有多仓时：
  - 当前收盘价小于等于上一根中轨，卖平。
- 持有空仓时：
  - 当前收盘价大于等于上一根中轨，买平。

至少需要89根K线才能同时计算88周期指标并读取上一根指标值。内存DataFrame只保留最近98根K线，完整历史由CSV和MySQL保存。

### 4.2 下单方式

`insertOrder` 根据方向使用对手价限价单：

- 买入使用卖一价 `AskPrice1`。
- 卖出使用买一价 `BidPrice1`。
- 对手价不存在或小于等于0时拒绝发单。
- 委托类型为限价、当日有效、立即触发。

Strategy2 的 `position` 是策略进程内的简化状态，并不是从CTP账户持仓实时恢复的结果。

## 5. K线持久化

### 5.1 本地CSV

完整K线按合约追加到：

```text
实时数据/{合约代码}_bar.csv
```

当前字段：

```text
合约名称, 开盘价, 最高价, 最低价, 收盘价,
成交量, 持仓量, 上一刻成交量, 当前时间
```

其中“当前时间”表示K线开始时间，由CTP的 `ActionDay` 与对齐后的分钟时间组成，不是CSV写入时的系统时间。

### 5.2 MySQL

MySQL写入由根目录的 `bar_persistence.py` 实现，默认目标为：

```text
数据库：ctp_sys
表：bar_data
```

主要字段映射：

| MySQL字段 | K线属性 |
|---|---|
| `contract_name` | `instrumentID` |
| `exchange` | `exchangeID` |
| `interval` | `barType`，`min`转换为`1m` |
| `current_time` | `barTime` |
| `open_price` | `openPrice` |
| `high_price` | `highPrice` |
| `low_price` | `lowPrice` |
| `close_price` | `closePrice` |
| `volume` | `volume` |
| `open_interest` | `openInterest` |

依赖唯一键：

```sql
UNIQUE KEY uk_bar (contract_name, interval, current_time)
```

写入采用 `INSERT ... ON DUPLICATE KEY UPDATE`。同一合约、周期和K线开始时间重复写入时更新原行，不产生重复K线。

数据库连接为延迟创建并复用。每次写入前检查连接，断线时重连；第一次失败后重建连接并重试一次。数据库持续不可用时只输出警告，不阻止CSV和策略运行。

更详细的改造和测试记录见：

```text
function_test_section/K线CSV及MySQL持久化改造说明.md
```

## 6. 配置说明

### 6.1 CTP账户和前置地址

当前主链路的账户、Broker、行情前置和交易前置配置位于：

```text
function_test_section/Global_Param.py
```

至少需要配置：

- `investorID`
- `password`
- `broker_id`
- `market_server_front`
- `trade_server_front`
- `appID`
- `authcode`

不要将真实账户密码提交到版本库。生产环境建议将敏感信息迁移到本地配置文件或环境变量。

### 6.2 MySQL配置

复制模板并填写本机连接信息：

```powershell
Copy-Item con_file\database.ini.example con_file\database.ini
```

配置格式：

```ini
[mysql]
enabled = true
host = 127.0.0.1
port = 3306
user = root
password = 本机数据库密码
database = ctp_sys
table = bar_data
charset = utf8mb4
connect_timeout = 3
```

`con_file/database.ini` 已加入 `.gitignore`。程序也支持用以下环境变量覆盖INI：

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

将 `enabled` 设置为 `false` 可以关闭MySQL入库并继续保存CSV。

## 7. 环境准备

项目要求使用 Python 3.8.x。当前已实测环境为 Python 3.8.10：

```powershell
conda activate CTP_1
python --version
python -m pip check
```

预期输出应包含：

```text
Python 3.8.10
No broken requirements found.
```

安装或确认MySQL依赖：

```powershell
python -m pip install -r requirements.txt
```

`requirements.txt` 当前锁定：

```text
PyMySQL==1.1.2
```

项目还使用 pandas 和 psutil；当前 `CTP_1` 环境已验证的版本分别为 pandas 2.0.3、psutil 7.2.2。

Windows下需要确保Python位数与 `CTP_API/*.pyd` 一致，并确保CTP动态库可以被加载。

## 8. 启动方法

当前代码中的部分交易流水和CTP会话路径仍以 `function_test_section` 为工作目录设计，因此建议使用以下方式启动：

```powershell
conda activate CTP_1
Set-Location D:\CTPprogram\CTP_PROXY\function_test_section
python sub_bar.py
```

启动顺序：

1. 构造 Strategy1、Strategy2，合并订阅合约。
2. 连接行情前置并登录、订阅行情。
3. 连接交易前置，完成认证、登录和结算确认。
4. 交易账户登录标志置为True后开始分发Tick。
5. 跨分钟时生成完整K线并传递到Strategy2。
6. Strategy2追加CSV、写入MySQL并计算交易信号。

使用 `Ctrl+C` 结束主程序。

## 9. 数据验证

查看最近入库K线：

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

`interval` 和 `current_time` 在MySQL中可能被当作关键字或内置函数，手写SQL时应使用反引号。

同时核对：

```text
实时数据/rb2610_bar.csv
交易流水/strategy2_rb2610.csv
```

## 10. 已验证内容

- 使用 `CTP_1` 的 Python 3.8.10 编译全部新增和修改模块，语法通过。
- 未使用Python 3.9以上才支持的内置泛型、联合类型或模式匹配语法。
- Strategy2、K线结构、行情入口和MySQL组件可在Python 3.8.10中导入。
- 成功连接本地MySQL 8.0.46和 `ctp_sys.bar_data`。
- 同一测试K线写入两次后只保留一行，第二次数据正确覆盖。
- 测试数据已清理，未留在 `bar_data` 中。
- 模拟跨分钟Tick后，K线时间、交易所、OHLC、成交量和持仓量正确。
- 模拟MySQL不可用时，CSV继续写入且K线锁正常释放。
- `pip check` 未发现依赖冲突。

## 11. 已知边界与风险

1. 只有收到下一分钟首个Tick时，上一根K线才会完成；程序退出时正在形成的最后一根K线不会强制保存。
2. MySQL长时间不可用期间，CSV仍会保存，但当前没有自动从CSV补录数据库的任务。
3. Strategy2的持仓状态只保存在内存，重启后归零，未与真实账户持仓自动同步。
4. 策略在报单请求成功发出后立即修改内存持仓状态，没有等待实际成交回报确认。
5. 合约代码和策略参数当前硬编码在策略文件中，没有独立策略配置文件。
6. 数据处理使用线程池并继续创建分发线程，高行情量下需要进一步评估线程数量、队列积压和顺序一致性。
7. 1分钟K线使用本地Tick实时合成，不包含程序启动前的历史K线。
8. 数据库故障虽然不会中止策略，但一次连接和重试可能使单根K线处理等待最多数秒。
9. 根目录仍存在旧版同名模块，新增功能应优先修改 `function_test_section` 主链路，避免维护两套实现。
10. 当前代码包含模拟账户配置结构，切换实盘前必须重新核对前置地址、认证参数、交易所平今/平昨规则、手续费和风险控制。

## 12. 后续建议

- 将CTP账户信息、订阅合约和策略参数迁移到不提交的配置文件。
- 启动时查询账户真实持仓并恢复各策略状态。
- 根据成交回报而不是报单请求更新策略持仓。
- 增加程序退出时当前未完成K线的可选保存机制。
- 增加CSV到MySQL的补录工具和定时一致性检查。
- 为K线合成、交易时段、跨夜ActionDay、重复Tick和累计成交量回退增加自动化测试。
- 将日志统一到 `logging`，增加日志级别、滚动文件和错误追踪。
- 清理或归档根目录的旧版重复模块，统一唯一正式入口。
- 实盘前增加单日亏损、最大仓位、最大下单频率、异常行情过滤和紧急停机机制。
