import os
import sys
import time
import threading
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import  Global_Param as g


class strategy1:
    def __init__(self):
        # 策略编号
        self.strategyID = 1
        self.subId=['hc2610','fu2609','au2608']
        self.specific_strategy_map = {}
        for instrumentID in self.subID:
            self.specific_strategy_map[instrumentID] = strategy1.specific_strategy(instrumentID) #au2608 : <strategy.....> 合约名：对应策略
            #print(self.specific_strategy_map)



    class specific_strategy(object):
        def __init__(self, instrumentID):
            # 策略数据
            # self.market_data = MarketData()
            self.market_data = None
            # 策略数据锁
            self.market_data_lock = threading.Lock()
            # 策略合约名称
            self.instrumentID = instrumentID
            #策略开仓信号
            self.open_flag = 0

















