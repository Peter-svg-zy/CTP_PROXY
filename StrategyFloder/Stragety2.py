
import os
import sys
import threading

import pandas as pd

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from bar_persistence import MySQLBarWriter, resolve_bar_time
from function_test_section import Global_Param as g
from function_test_section.UserStruct import *
from function_test_section.function import *

# 策略固定参数
PERIOD = 88 # 窗口内单元数
NUM_STD = 2 # 标准差
TRADE_VOLUME = 1  # 每次交易手数
# 【内存安全阈值】保留的K线最大行数，足以满足 PERIOD=88 的指标计算需求
MAX_KLINE_ROWS = PERIOD + 10


# 策略2
class strategy2(object):

    def __init__(self):
        # 订阅的合约
        self.subID = ['rb2610']
        # 订阅的K线
        self.subKlineType = [bt.min]  # 这里先以1分钟K线为例
        self.specific_strategy_map = {}
        for instrumentID in self.subID:
            self.specific_strategy_map[instrumentID] = strategy2.specific_strategy(instrumentID)
        # 策略编号
        self.strategyID = 2

    class specific_strategy(object):
        def __init__(self, instrumentID):
            # 策略数据
            self.market_data = None
            # K线数据
            self.barData = None
            # 策略数据锁
            self.market_data_lock = threading.Lock()
            # K线线程锁
            self.kline_lock = threading.Lock()
            # 策略合约名称
            self.instrumentID = instrumentID

            # 策略状态
            self.position = 0  # 0: 无持仓, 1: 多头, -1: 空头

            # 【内存容器】仅用于实时指标计算，会被截断
            self.save_to_csv = pd.DataFrame(
                columns=['合约名称', '开盘价', '最高价', '最低价', '收盘价', '成交量', '持仓量', '上一刻成交量',
                         '当前时间'])

            # 【新增】本地CSV文件路径及表头写入标志
            self.csv_path = os.path.join(PROJECT_ROOT, '实时数据', f'{instrumentID}_bar.csv')
            self._csv_header_written = os.path.exists(self.csv_path) and os.path.getsize(self.csv_path) > 0

            # MySQL延迟连接写入器：首次收到完整K线时才连接数据库
            self.mysql_writer = MySQLBarWriter()

        def calculate_bollinger(self, close_series, period, num_std):
            """计算布林带指标"""
            middle_band = close_series.rolling(window=period).mean()
            std = close_series.rolling(window=period).std()
            upper_band = middle_band + num_std * std
            lower_band = middle_band - num_std * std
            return middle_band, upper_band, lower_band

        def Aberration(self):
            """Aberration策略的实现，调用function中的insertorder模拟市价单指令进行下单"""
            # 至少需要 PERIOD + 1 根K线才能计算指标和获取上一根K线的值
            if len(self.save_to_csv) < PERIOD + 1:
                return

            # 获取收盘价序列
            close = self.save_to_csv['收盘价']

            # 计算当前布林带指标
            mid, upper, lower = self.calculate_bollinger(close, PERIOD, NUM_STD)

            # 获取当前K线和上一根K线的数据
            current_close = close.iloc[-1]
            prev_upper = upper.iloc[-2]
            prev_lower = lower.iloc[-2]
            prev_mid = mid.iloc[-2]

            # 防止指标计算出现 NaN
            if pd.isna(prev_upper) or pd.isna(prev_lower) or pd.isna(prev_mid):
                return

            code = self.barData.instrumentID

            # ================= 交易逻辑 =================

            # 1. 无持仓状态
            if self.position == 0:
                # 突破上轨做多 (买开)
                if current_close >= prev_upper:
                    print(f"[{code}] 突破上轨 {prev_upper:.2f}，当前价 {current_close:.2f}，执行买开")
                    insertOrder(code, bs.buyOpen, TRADE_VOLUME, self.strategyID)
                    self.position = 1

                # 突破下轨做空 (卖开)
                elif current_close <= prev_lower:
                    print(f"[{code}] 跌破下轨 {prev_lower:.2f}，当前价 {current_close:.2f}，执行卖开")
                    insertOrder(code, bs.sellOpen, TRADE_VOLUME, self.strategyID)
                    self.position = -1

            # 2. 持仓多头状态
            elif self.position == 1:
                # 从上而下突破均线卖平
                if current_close <= prev_mid:
                    print(f"[{code}] 跌破中轨 {prev_mid:.2f}，当前价 {current_close:.2f}，多单平仓")
                    insertOrder(code, bs.sellClose, TRADE_VOLUME, self.strategyID)
                    self.position = 0

            # 3. 持仓空头状态
            elif self.position == -1:
                # 从下而上突破均线买平
                if current_close >= prev_mid:
                    print(f"[{code}] 突破中轨 {prev_mid:.2f}，当前价 {current_close:.2f}，空单平仓")
                    insertOrder(code, bs.buyClose, TRADE_VOLUME, self.strategyID)
                    self.position = 0

        def onQuote(self):
            self.market_data_lock.release()

        def onBar(self):
            try:
                print('这是策略2 - Aberration')
                print(f"合约: {self.barData.instrumentID}, 周期: {self.barData.barType}")

                # CSV沿用原字段结构，“当前时间”改为准确的K线开始时间。
                bar_time = resolve_bar_time(self.barData)
                data_list = [
                    self.barData.instrumentID, self.barData.openPrice, self.barData.highPrice,
                    self.barData.lowPrice, self.barData.closePrice, self.barData.volume,
                    self.barData.openInterest, self.barData.lastVolume,
                    bar_time.strftime("%Y-%m-%d %H:%M:%S")
                ]
                new_row = pd.DataFrame([data_list], columns=self.save_to_csv.columns)

                try:
                    os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
                    new_row.to_csv(
                        self.csv_path,
                        mode='a',
                        header=not self._csv_header_written,
                        index=False
                    )
                    self._csv_header_written = True
                except Exception as exc:
                    print(f"[警告] K线写入CSV失败: {exc}")

                try:
                    self.mysql_writer.write(self.barData)
                except Exception as exc:
                    # 数据库异常不能影响内存指标计算和交易策略运行。
                    print(f"[警告] K线写入MySQL失败: {exc}")

                self.save_to_csv = pd.concat([self.save_to_csv, new_row], ignore_index=True)
                if len(self.save_to_csv) > MAX_KLINE_ROWS:
                    self.save_to_csv = self.save_to_csv.tail(MAX_KLINE_ROWS).reset_index(drop=True)

                self.Aberration()
            finally:
                # 即使CSV、数据库或策略计算异常，也必须释放锁。
                self.kline_lock.release()
