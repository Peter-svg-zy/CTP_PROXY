import copy
import csv
import datetime
import os
import re
import sys
import time
from threading import Thread
import Global_Param as g
from CTP_API import thosttraderapi as tdapi
from CTP_API import thostmduserapi as mdapi
from UserStruct import *


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


# 保存数据并且调用策略进行判断
def save_data(strategy, pDepthMarketData):
    # 上锁
    instrumentID = pDepthMarketData.InstrumentID
    strategy.specific_strategy_map[instrumentID].market_data_lock.acquire()
    """ 一个策略大类中根据合约去细分架构的核心，对采集来的数据按照合约来进行分发后上不同的锁，不同合约不会相互影响 """
    strategy.specific_strategy_map[instrumentID].market_data = copy.copy(pDepthMarketData)
    # 解锁，在策略中进行解锁
    # strategy.specific_strategy_map[instrumentID].market_data_lock.release()

    # 调用策略中的行情事件
    t2 = Thread(target=strategy.specific_strategy_map[instrumentID].onQuote)
    t2.start()

# ********************* 下单指令，买开，卖开 ******************************
def insertOrder(code, BSType, volume, strategyID=0):
    orderfield = tdapi.CThostFtdcInputOrderField()
    orderfield.BrokerID = g.broker_id
    orderfield.ExchangeID = g.ExchangeID[code]
    orderfield.InstrumentID = code
    orderfield.UserID = g.investorID
    orderfield.InvestorID = g.investorID
    orderfield.VolumeTotalOriginal = volume

    # 【核心修改】根据买卖方向获取对手价作为限价
    if BSType in ('buyopen', 'buyclose', 'buyclosetoday'):
        actual_price = g.ask_price.get(code, 0)   # 字典中没有该code合约时，返回0这个默认值
        orderfield.Direction = tdapi.THOST_FTDC_D_Buy
        if BSType == 'buyopen':
            orderfield.CombOffsetFlag = '0'
        elif BSType == 'buyclose':
            orderfield.CombOffsetFlag = '1'
        else:
            orderfield.CombOffsetFlag = tdapi.THOST_FTDC_OF_CloseToday
    elif BSType in ('sellopen', 'sellclose', 'sellclosetoday'):
        actual_price = g.bid_price.get(code, 0)
        orderfield.Direction = tdapi.THOST_FTDC_D_Sell
        if BSType == 'sellopen':
            orderfield.CombOffsetFlag = '0'
        elif BSType == 'sellclose':
            orderfield.CombOffsetFlag = '1'
        else:
            orderfield.CombOffsetFlag = tdapi.THOST_FTDC_OF_CloseToday
    else:
        print('下单委托类型错误！停止下单！')
        return None, None

    # 【安全检查】对手价无效时拒绝发单，防止发出价格为0的废单
    if actual_price <= 0:
        print(f'⚠️ {code} 对手价无效({actual_price})，放弃下单！')
        return None, None

    # 当前单号
    orderRef = get_OrderRef()
    orderfield.OrderRef = str(orderRef)

    # 【核心修改】使用对手价限价单替代原市价单（全交易所通用）
    orderfield.LimitPrice = actual_price
    orderfield.OrderPriceType = tdapi.THOST_FTDC_OPT_LimitPrice
    orderfield.TimeCondition = tdapi.THOST_FTDC_TC_GFD

    # 触发条件
    orderfield.ContingentCondition = tdapi.THOST_FTDC_CC_Immediately
    # 成交量类型
    orderfield.VolumeCondition = tdapi.THOST_FTDC_VC_AV
    # 组合投机套保标志
    orderfield.CombHedgeFlag = "1"
    # GTD日期
    orderfield.GTDDate = ""
    # 最小成交量
    orderfield.MinVolume = 0
    # 强平原因
    orderfield.ForceCloseReason = tdapi.THOST_FTDC_FCC_NotForceClose
    # 自动挂起标志
    orderfield.IsAutoSuspend = 0
    # 补充必填字段，防止底层C++内存残留随机值导致报错
    orderfield.StopPrice = 0
    orderfield.IsSwapOrder = 0

    ret = g.tduserapi.ReqOrderInsert(orderfield, 0)
    if ret == 0:
        print('下单成功！')
        g.order_map[str(orderRef)] = orderInfo(orderRef, strategyID)
        # 记录实际发出的对手价，便于后续核对成交滑点
        g.order_map[str(orderRef)].orderPrice = actual_price
        g.order_map[str(orderRef)].instrumentID = code
        print(f"当前合约 {code} 的交易所代码为: [{g.ExchangeID[code]}]")
    else:
        print('下单失败！')
        judge_ret(ret)

    return ret, orderRef


# 撤单
def cancelOrder(orderRef):
    orderfield = tdapi.CThostFtdcInputOrderActionField()
    orderfield.BrokerID = g.broker_id
    orderfield.UserID = g.investorID
    orderfield.InvestorID = g.investorID

    orderfield.FrontID = g.frontID
    orderfield.SessionID = g.sessionID
    orderfield.InstrumentID = g.order_map[str(orderRef)].instrumentID

    # print(f'g.frontID:{g.frontID}')
    # print(f'g.sessionID:{g.sessionID}')
    # print(f'g.order_map[orderRef].instrumentID:{g.order_map[str(orderRef)].instrumentID}')

    # 当前单号
    orderfield.OrderRef = str(orderRef)

    # 操作标志
    orderfield.ActionFlag = '0'

    ret = g.tduserapi.ReqOrderAction(orderfield, 0)
    if ret == 0:
        print('发送撤单成功！')
    else:
        print('发送撤单失败！')
        judge_ret(ret)
    return ret


# 判断发送请求失败原因
def judge_ret(ret):
    if ret == -1:
        print('失败原因：网络连接失败')
    elif ret == -2:
        print('失败原因：表示未处理请求超过许可数')
    elif ret == -3:
        print('失败原因：表示每秒发送请求数超过许可数')
    else:
        print('失败原因：未知。\nret：{}'.format(ret))


# 获取最大保单引用
def get_OrderRef():
    g.maxOrderRef += 1
    return g.maxOrderRef - 1


# 将数据写入csv中,w代表删除原有的写入，w+代表读写，a代表追写，a+代表读+追写
def write_to_csv(file_name, method, content):
    """

    @param file_name:
    @param method: w代表删除原有的写入，w+代表读写，a代表追写，a+代表读+追写
    @param content: 注意！！！，内容为一个列表，即：需要用[]括起来，如['1',str(a)]
    """
    # with open(file_name, 'a') as f:
    # 1. 创建文件对象
    f = open(file_name, method, newline='')
    # 2. 基于文件对象构建 csv写入对象
    csv_writer = csv.writer(f)
    # 4. 写入csv文件内容
    csv_writer.writerow(content)
    # 5. 关闭文件
    f.close()


def get_file_name(path, ext):
    """
    获取指定路径下，指定格式的所有文件名
    @param path: 路径，如：上一层 '../'
    @param ext: 指定后缀
    """
    listallfile = os.listdir(path)
    listfile = []

    # 获取指定格式的文件
    for i in listallfile:
        if ext in i:
            listfile.append(i)
    return listfile[:]


# 创建交易流水
def create_tradeLogFile():
    # 遍历所有策略，将所有策略的合约进行合并
    content = ['自然日', '交易日', '时间', '标的', '方向', '委托价', '成交价', '成交量', '平仓盈亏', '手续费']
    path = './交易流水/'
    for strategy in g.strategy_map.values():
        for subID in strategy.subID:
            file_name = 'strategy{}_{}.csv'.format(strategy.strategyID, subID)
            # 判断文件是否存在
            if file_name not in get_file_name(path, '.csv'):
                write_to_csv(path + file_name, 'w', content)


# 写入交易流水
def writeToTradeLogFile(pTrade):
    # 报单回报里的报单价格数据不对
    # orderPrice = g.order_map[pTrade.OrderRef].pOrder.LimitPrice
    orderPrice = g.order_map[pTrade.OrderRef].orderPrice

    strategyID = g.order_map[pTrade.OrderRef].strategyID
    fee = calculate_Commissionrate(pTrade)
    # 判断交易方向
    dirction = ''
    if pTrade.Direction == '0':
        dirction += '买'
    elif pTrade.Direction == '1':
        dirction += '卖'
    if pTrade.OffsetFlag == '0':
        dirction += '开'
    elif pTrade.OffsetFlag == '1':
        dirction += '平'
    elif pTrade.OffsetFlag == '2':
        dirction += '平（强平）'
    elif pTrade.OffsetFlag == '3':
        dirction += '平（今）'
    elif pTrade.OffsetFlag == '4':
        dirction += '平（昨）'

    # 计算平仓盈亏
    profit = '平仓盈亏'
    # 开仓
    if pTrade.OffsetFlag == '0':
        profit = 0
    # 平仓（包括平仓，平今，平昨等）
    else:
        positionDetail = None
        positionName_list = []
        # 获取该品种的持仓
        for positionName in g.positionDetail_map.keys():
            if pTrade.InstrumentID in positionName:
                positionName_list.append(positionName)
        # 如果是上期所或者能源中心需要判断是平今还是平昨
        if pTrade.ExchangeID == 'SHFE' or pTrade.ExchangeID == 'INE':
            # 平今
            if pTrade.OffsetFlag == '3':
                # 获取今日持仓
                for positionName in positionName_list:
                    if '今' in positionName:
                        positionDetail = g.positionDetail_map[positionName]
                        break
            # 平昨
            if pTrade.OffsetFlag == '4':
                # 获取昨日持仓
                for positionName in positionName_list:
                    if '昨' in positionName:
                        positionDetail = g.positionDetail_map[positionName]
                        break
        # 如果不是上期所或者能源中心
        else:
            positionName = positionName_list[0]
            positionDetail = g.positionDetail_map[positionName]
        # print(positionName_list)
        # print(positionDetail)
        # print(positionDetail.openPrice_list)
        #
        # print(positionDetail.openPrice_list[0:int(pTrade.Volume)])
        # print(round(float(pTrade.Price), 4))
        # product = del_num(pTrade.InstrumentID)
        # print(float(g.productInfo[product]["合约乘数"]))
        # print(pTrade.Direction)

        # 计算持仓盈亏
        profit = 0
        if pTrade.Direction == '0':
            # dirction += '买'
            product = del_num(pTrade.InstrumentID)
            for openPrice in positionDetail.openPrice_list[0:int(pTrade.Volume)]:
                profit += (openPrice - round(float(pTrade.Price), 4)) * round(float(g.productInfo[product]["合约乘数"]), 1)
        elif pTrade.Direction == '1':
            # dirction += '卖'
            product = del_num(pTrade.InstrumentID)
            for openPrice in positionDetail.openPrice_list[0:int(pTrade.Volume)]:
                profit += (round(float(pTrade.Price), 4) - openPrice) * round(float(g.productInfo[product]["合约乘数"]), 1)
        # 更新持仓
        g.positionDetail_map[positionName].openPrice_list = positionDetail.openPrice_list[int(pTrade.Volume):]
        # print(len(g.positionDetail_map[positionName].openPrice_list))
        # print(profit)

    # print(f'手续费：{fee}')
    content = [pTrade.TradeDate, pTrade.TradingDay, pTrade.TradeTime, pTrade.InstrumentID, dirction,
               orderPrice, pTrade.Price, pTrade.Volume, round(profit, 0), fee]
    write_to_csv('./交易流水/strategy{}_{}.csv'.format(strategyID, pTrade.InstrumentID), 'a', content)

    del g.order_map[pTrade.OrderRef]


def red_print(content):
    print(f'\033[0;0;31m{content}\033[0m')


def del_num(content):
    res = re.sub('\d', '', content)
    return res


# 计算手续费
def calculate_Commissionrate(pTrade):
    # 产品
    product = del_num(pTrade.InstrumentID)
    # 数量
    volume = pTrade.Volume
    # 合约乘数
    volumeMultiple = float(g.productInfo[product]["合约乘数"])
    # 开仓手续费率
    OpenRatioByMoney = float(g.productInfo[product]["开仓手续费率"])
    # 开仓手续费
    openRatioByVolume = float(g.productInfo[product]["开仓手续费"])
    # 平仓手续费率
    closeRatioByMoney = float(g.productInfo[product]["平仓手续费率"])
    # 平仓手续费
    closeRatioByVolume = float(g.productInfo[product]["平仓手续费"])
    # 平今手续费率
    closeTodayRatioByMoney = float(g.productInfo[product]["平今手续费率"])
    # 平今手续费
    closeTodayRatioByVolume = float(g.productInfo[product]["平今手续费"])

    fee = '手续费'

    # 这个信号是根据下单来决定的，填的平仓，实际平的是今仓，但是回报里是平仓，会按照平仓进行计算，有的时候会造成错误
    # 比如，m合约，平今手续费0.1，平昨是0.2
    # 开仓
    if pTrade.OffsetFlag == '0':
        fee = volume * (pTrade.Price * volumeMultiple * OpenRatioByMoney + openRatioByVolume)
        pass
    # 平仓
    elif pTrade.OffsetFlag == '1':
        fee = volume * (pTrade.Price * volumeMultiple * closeRatioByMoney + closeRatioByVolume)
        pass
    # 强平
    elif pTrade.OffsetFlag == '2':
        pass
    # 平今
    elif pTrade.OffsetFlag == '3':
        fee = volume * (pTrade.Price * volumeMultiple * closeTodayRatioByMoney + closeTodayRatioByVolume)
        pass
    # 平昨
    elif pTrade.OffsetFlag == '4':
        fee = volume * (pTrade.Price * volumeMultiple * closeRatioByMoney + closeRatioByVolume)
        pass

    return fee


# 打印类内成员
def print_object(obj):
    print('\n'.join(['%s:%s' % item for item in obj.__dict__.items()]))
