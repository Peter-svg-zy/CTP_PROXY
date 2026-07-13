# 使用说明，4替换为策略序号
import os
import sys
import threading
import datetime

import pandas as pd

sys.path.append(os.path.dirname(os.path.split(os.getcwd())[0] + r"\ "))
import Global_Param as g
from function_test_section.UserStruct import *
from function_test_section.function import *

# 策略固定参数
PERIOD = 88
NUM_STD = 2
TRADE_VOLUME = 1  # 每次交易手数


# 策略2
class strategy2(object):

    def __init__(self):
        # 订阅的合约
        self.subID = ['rb2610']
        # 订阅的K线 (Aberration通常使用较长周期，这里保留15分钟线，也可根据需要调整)
        self.subKlineType = [bt.min15]
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

            # 历史K线数据容器，用于计算指标
            self.save_to_csv = pd.DataFrame(
                columns=['合约名称', '开盘价', '最高价', '最低价', '收盘价', '成交量', '持仓量', '上一刻成交量',
                         '当前时间'])

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
            print('这是策略2 - Aberration')
            print(f"合约: {self.barData.instrumentID}, 周期: {self.barData.barType}")

            # 将新K线数据追加到 DataFrame
            data_list = [
                self.barData.instrumentID, self.barData.openPrice, self.barData.highPrice,
                self.barData.lowPrice, self.barData.closePrice, self.barData.volume,
                self.barData.openInterest, self.barData.lastVolume,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            ]

            new_row = pd.DataFrame([data_list], columns=self.save_to_csv.columns)
            self.save_to_csv = pd.concat([self.save_to_csv, new_row], ignore_index=True)

            # 可选：保存K线到本地CSV
            # self.save_to_csv.to_csv('../实时数据/{}_bar.csv'.format(self.barData.instrumentID))

            # 执行策略逻辑 (此时 kline_lock 仍处于锁定状态，保证线程安全)
            self.Aberration()

            # 释放K线锁
            self.kline_lock.release()