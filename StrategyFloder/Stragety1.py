import os
import sys
import time
import threading
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import  Global_Param as g
from function_test_section.UserStruct import *



class strategy1:
    def __init__(self):
        # 策略编号
        self.strategyID = 1
        self.subKlineType = []
        self.subID=['hc2610','fu2609','au2608']
        self.specific_strategy_map = {}
        for instrumentID in self.subID:
            self.specific_strategy_map[instrumentID] = strategy1.specific_strategy(instrumentID) #au2608 : <strategy.....> 合约名：对应策略
            #print(self.specific_strategy_map)

    def Aberration(self):
        """本类下所有合约调用的策略"""
        pass


    class specific_strategy(object):
        def __init__(self, instrumentID):
            # 策略数据(tick)
            self.market_data = MarketData()
            self.market_data = None
            # 保存K线数据
            self.bar_data = None
            # 策略数据锁
            self.market_data_lock = threading.Lock()
            # K线线程锁
            self.kline_lock = threading.Lock()
            # 策略合约名称
            self.instrumentID = instrumentID
            #策略开仓信号
            self.open_flag = 0
        def onQuote(self):
           #strategy1.Aberration()
           # print(f'策略1：{self.market_data.InstrumentID}')
           self.market_data_lock.release_lock()

















