import time
from threading import Thread
import datetime
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
import Global_Param as g

def init_subID():
    # 遍历所有策略，将所有策略的合约进行合并
    for strategy in g.strategy_map.values():
        g.subID = list(set(g.subID + strategy.subID))


# 获取数据并传递
def get_data():
    while True:
        pDepthMarketData = g.dataQueue.get()
        # 如果不是7*24小时数据，需要进行数据清理
        if '7*24' not in g.broker_name:
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            stamp = today + " " + pDepthMarketData.UpdateTime
            timeArray = time.strptime(stamp, "%Y-%m-%d %H:%M:%S")
            timeStamp = int(time.mktime(timeArray))
            now = int(time.time())
            now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 时间戳之差超过3分钟即认为是无效数据
            if abs(now - timeStamp) > 3 * 60:
                print(f"marketdata delay : ID:{pDepthMarketData.InstrumentID}, Stamp:{stamp}, Now:{now_time}")
                continue
        # if pDepthMarketData.InstrumentID == 'FG209':
        #     g.start = time.time()
        t3 = Thread(target=distribute_data, args=(pDepthMarketData,))
        t3.start()


# 判断需要给哪些策略传数据
def distribute_data(pDepthMarketData):
    for strategy in g.strategy_map.values():
        if pDepthMarketData.InstrumentID in strategy.subID:
            t1 = Thread(target=save_data, args=(strategy, pDepthMarketData,))
            t1.start()


def save_data(strategy, pDepthMarketData):
    # 上锁
    instrumentID = pDepthMarketData.InstrumentID
    strategy.specific_strategy_map[instrumentID].market_data_lock.acquire()

    strategy.specific_strategy_map[instrumentID].market_data = copy.copy(pDepthMarketData)
    # 解锁
    # strategy.specific_strategy_map[instrumentID].market_data_lock.release()

    # 调用策略中的行情事件
    t2 = Thread(target=strategy.specific_strategy_map[instrumentID].onQuote)
    t2.start()







def judge_ret(ret):
    if ret == -1:
        print('失败原因：网络连接失败')
    elif ret == -2:
        print('失败原因：表示未处理请求超过许可数')
    elif ret == -3:
        print('失败原因：表示每秒发送请求数超过许可数')
    else:
        print('失败原因：未知。\nret：{}'.format(ret))