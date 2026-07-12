# 使用说明，4替换为策略序号
import os
import sys
import threading

import pandas as pd

sys.path.append(os.path.dirname(os.path.split(os.getcwd())[0] + r"\ "))
import Global_Param as g
from function_test_section.UserStruct import *
from function_test_section.function import *


# 策略4
class strategy2(object):

    def __init__(self):
        # 订阅的合约
        self.subID = ['rb2610']
        # 订阅的K线
        self.subKlineType = [bt.min, bt.min15]
        self.specific_strategy_map = {}
        for instrumentID in self.subID:
            self.specific_strategy_map[instrumentID] = strategy2.specific_strategy(instrumentID)
        # 策略编号
        self.strategyID = 2

    class specific_strategy(object):
        def __init__(self, instrumentID):
            # 策略数据
            # self.market_data = MarketData()
            self.market_data = None
            # K线数据
            self.barData = None
            # 策略数据锁
            self.market_data_lock = threading.Lock()
            # K线线程锁
            self.kline_lock = threading.Lock()
            # 策略合约名称
            self.instrumentID = None

            self.save_to_csv = pd.DataFrame(columns=['合约名称', '开盘价', '最高价', '最低价', '收盘价', '成交量', '持仓量','上一刻成交量', '当前时间'])

        def onQuote(self):

            self.market_data_lock.release()

        def onBar(self):
            print('这是策略2')
            print(self.barData.instrumentID)
            print_object(self.barData)

            data_list = [self.barData.instrumentID, self.barData.openPrice, self.barData.highPrice, self.barData.lowPrice, self.barData.closePrice,
                         self.barData.volume, self.barData.openInterest, self.barData.lastVolume, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")]
            self.save_to_csv = pd.concat(
                [self.save_to_csv, pd.DataFrame([data_list, ], columns=['合约名称', '开盘价', '最高价', '最低价', '收盘价', '成交量', '持仓量','上一刻成交量', '当前时间'])],
                ignore_index=True)
            self.save_to_csv.to_csv('../实时数据/{}_bar.csv'.format(self.barData.instrumentID))
            self.kline_lock.release_lock()

