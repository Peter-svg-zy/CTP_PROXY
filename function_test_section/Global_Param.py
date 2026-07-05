import configparser
import json
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
# 账户信息
# simnow
import pandas as pd
#
# broker_name = 'simnow模拟'
# investorID = ''
# password = ''
# broker_id = '9999'
# market_server_front = 'tcp://182.254.243.31:30011'
# trade_server_front = 'tcp://182.254.243.31:30001'
# appID = 'simnow_client_test'
# authcode = '0000000000000000'
# productInfo_fileName = './con_file/productInfo.ini'

broker_name = 'simnow模拟7*24小时'
investorID = '264168'
password = 'zy20010528@'
broker_id = '9999'
market_server_front = 'tcp://182.254.243.31:40011'
trade_server_front = 'tcp://182.254.243.31:40001'
appID = 'simnow_client_test'
authcode = '0000000000000000'
productInfo_fileName = './con_file/productInfo.ini'

# broker_name = 'ws'
# investorID = '02'
# password = '156'
# broker_id = '9999'
# market_server_front = 'ws://127.0.0.1:5253'
# trade_server_front = 'tcp://180.168.146.187:10201'
# appID = 'simnow_client_test'
# authcode = '0000000000000000'
# productInfo_fileName = './con_file/productInfo.ini'


# 其他信息
subID = []
# 查询信号，用于检查是否查询完成，true代表正在查询
qry_flag = True

# 下单必要元素
frontID = None  # 前置编号
sessionID = None  # 会话编号
maxOrderRef = None  # 最大报单引用

# 策略字典
strategy_map = {}
# 订单字典
order_map = {}
# 持仓字典
position_map = {}
# 详细持仓字典
positionDetail_map = {}

# 交易日
tradingDay = None

# 线程池
save_data_pool = ThreadPoolExecutor(5)

# 其他
tduserapi = None
tduserspi = None

mduserapi = None
mduserspi = None

# 合约交易所
ExchangeID = {}

# 合约手续费和保证金等
productInfo = configparser.ConfigParser()
productInfo.read(productInfo_fileName, encoding='utf-8')

# 读取json文件
try:
    with open('../con_file/ExchangeID.json', 'r', encoding='utf8') as f:
        ExchangeID = json.load(f)
# 如果有错误则创建文件
except Exception as e:
    print('读取ExchangeID.json失败！\n失败原因：{}\n已创建空白文件'.format(e))
    with open('../con_file/ExchangeID.json', 'w', newline='\n', encoding='utf-8') as f:
        # json.dump(ExchangeID, f, ensure_ascii=False)
        data = json.dumps(ExchangeID, indent=4, ensure_ascii=False)
        f.write(data)

# 数据队列
dataQueue = Queue()

# 计算数据传送时间
start = None
end = None





