import copy
import csv
import datetime
import os
import re
import sys
import time
from threading import Thread

import psutil

from function_test_section import Global_Param as g
from CTP_API import thosttraderapi as tdapi
from CTP_API import thostmduserapi as mdapi
from function_test_section.UserStruct import *


def init_subID():
    # 遍历所有策略，将所有策略的合约进行合并
    for strategy in g.strategy_map.values():
        g.subID = list(set(g.subID + strategy.subID))

        # 如果策略需要订阅K线，方式：判断接收K线形态是否为空
        if strategy.subKlineType:
            # 订阅K线ID，用来判断哪些合约需要合并
            g.subKlineID = list(set(g.subKlineID + strategy.subID))
            g.subKlineType = list(set(g.subKlineType + strategy.subKlineType))
    for instrumentID in g.subKlineID:
        g.klineMin_map[instrumentID] = BarData()

    # print(g.klineMin_map)


# 获取tick并传递
def get_tick():
    """获取tick并传递（已移除诊断打印，增加前置脏数据过滤）"""
    while True:
        try:
            pDepthMarketData = g.tickQueue.get()
            # 🔑 前置过滤：拦截CTP初始化空包/心跳包，避免进入后续耗时解析
            update_time = getattr(pDepthMarketData, 'UpdateTime', '')
            if not update_time or len(str(update_time).strip()) < 5:
                continue

            instrument_id = getattr(pDepthMarketData, 'InstrumentID', '')
            if not instrument_id:
                continue

            # 非7*24小时环境进行时间校验
            if '7*24' not in g.broker_name:
                try:
                    raw_time = str(update_time).strip()
                    clean_time = ''.join(c for c in raw_time if c.isprintable())

                    today = datetime.datetime.now().strftime('%Y-%m-%d')
                    stamp = f"{today} {clean_time}"

                    timeArray = time.strptime(stamp, "%Y-%m-%d %H:%M:%S")
                    timeStamp = int(time.mktime(timeArray))
                    now = int(time.time())

                    # 延迟超过60秒的过期Tick直接丢弃
                    if abs(now - timeStamp) > 60:
                        print(f"[WARN] Tick delay: {instrument_id}, Clean={stamp}", flush=True)
                        continue

                except (ValueError, OverflowError, TypeError):
                    # 解析失败说明是脏数据，静默跳过
                    continue

            # ✅ 核心分发（无任何打印，极致性能）
            distribute_tick(pDepthMarketData)
        except Exception as e:
            import traceback
            err = f"[FATAL] get_tick crashed: {repr(e)}\n{traceback.format_exc()}"
            print(err, flush=True)
            break


def distribute_tick(pDepthMarketData):
    """判断需要给哪些策略传tick，以及哪些合约需要合成min1 K线"""
    # 交易账户未登录时不处理
    if not g.tdLogin_flag:
        return
    instrument_id = pDepthMarketData.InstrumentID
    g.ask_price[instrument_id]=pDepthMarketData.AskPrice1
    g.bid_price[instrument_id]=pDepthMarketData.BidPrice1
    # 🔑 直接使用 Global_Param.py 中的全局线程池
    for strategy in g.strategy_map.values():
        if instrument_id in strategy.subID:
            g.save_data_pool.submit(save_tick, strategy, pDepthMarketData)


    # K线合成同样复用全局线程池
    if instrument_id in g.subKlineID:
        g.save_data_pool.submit(tick_to_Kline, pDepthMarketData)

def save_tick(strategy, pDepthMarketData):
    # 上锁
    instrumentID = pDepthMarketData.InstrumentID
    strategy.specific_strategy_map[instrumentID].market_data_lock.acquire()
    strategy.specific_strategy_map[instrumentID].market_data = copy.copy(pDepthMarketData)


    # 调用策略中的行情事件
    t2 = Thread(target=strategy.specific_strategy_map[instrumentID].onQuote)
    t2.start()


# tick合成为K线
def tick_to_Kline(pDepthMarketData):
    instrumentID = pDepthMarketData.InstrumentID
    # if instrumentID == 'm2209':
        # print(pDepthMarketData.UpdateTime + '.' + str(pDepthMarketData.UpdateMillisec))
        # print(pDepthMarketData.LastPrice)

    st = pDepthMarketData.UpdateTime.split(':')
    # print(st)
    # 如果tick的分钟数 等于K线的分钟数，则不是新的分钟线
    if int(st[1]) == g.klineMin_map[instrumentID].updateTime.minute:
        newMinitue = False
    else:
        newMinitue = True

        # 防止开启程序后第一次推送
        if g.klineMin_map[instrumentID].instrumentID != '':
            # print(pDepthMarketData.InstrumentID)
            # print_object(g.klineMin_map[pDepthMarketData.InstrumentID])
            # g.klineMin_map[instrumentID].closePrice = pDepthMarketData.LastPrice

            # 注意Volume字段是累计成交量，所以这个时间段内成交量为该值与上一时间段末成交量的差值
            # 成交量 = max（当前累计成交 - 上一刻成交， 0）
            g.klineMin_map[instrumentID].volume = max(pDepthMarketData.Volume - g.klineMin_map[instrumentID].lastVolume, 0)
            g.klineQueue.put(copy.deepcopy(g.klineMin_map[instrumentID]))
            print("合成K线传送到队列,k线收盘价为{}".format(g.klineMin_map[instrumentID].closePrice))
    # 如果是新1分钟，生成一个新k线变量，CBarData结构体中有OHLC,time等K线字段
    if newMinitue:
        g.klineMin_map[instrumentID] = BarData()
        g.klineMin_map[instrumentID].barType = bt.min
        g.klineMin_map[instrumentID].instrumentID = instrumentID
        g.klineMin_map[instrumentID].exchangeID = (
            getattr(pDepthMarketData, 'ExchangeID', '')
            or g.ExchangeID.get(instrumentID, '')
        )
        g.klineMin_map[instrumentID].actionDay = getattr(pDepthMarketData, 'ActionDay', '')
        g.klineMin_map[instrumentID].tradingDay = getattr(pDepthMarketData, 'TradingDay', '')
        g.klineMin_map[instrumentID].updateTime = datetime.time(int(st[0]), int(st[1]), 0, 0)
        raw_action_day = str(g.klineMin_map[instrumentID].actionDay or '').replace('-', '')
        try:
            bar_date = datetime.datetime.strptime(raw_action_day, '%Y%m%d').date()
        except ValueError:
            bar_date = datetime.date.today()
        g.klineMin_map[instrumentID].barTime = datetime.datetime.combine(
            bar_date, g.klineMin_map[instrumentID].updateTime
        )
        g.klineMin_map[instrumentID].volume = 0
        g.klineMin_map[instrumentID].openInterest = pDepthMarketData.OpenInterest
        g.klineMin_map[instrumentID].openPrice = pDepthMarketData.LastPrice
        g.klineMin_map[instrumentID].highPrice = pDepthMarketData.LastPrice
        g.klineMin_map[instrumentID].lowPrice = pDepthMarketData.LastPrice
        g.klineMin_map[instrumentID].closePrice = pDepthMarketData.LastPrice

        g.klineMin_map[instrumentID].lastVolume = pDepthMarketData.Volume
    else:
        # 如果不是新1分钟，更新相关数据
        g.klineMin_map[instrumentID].highPrice = max(g.klineMin_map[instrumentID].highPrice, pDepthMarketData.LastPrice)
        g.klineMin_map[instrumentID].lowPrice = min(g.klineMin_map[instrumentID].lowPrice, pDepthMarketData.LastPrice)
        g.klineMin_map[instrumentID].closePrice = pDepthMarketData.LastPrice
        # 持仓量
        g.klineMin_map[instrumentID].openInterest = pDepthMarketData.OpenInterest


# 获取K线并传递
def get_Bar():
    while True:
        kline = g.klineQueue.get()
        # 订阅合约成功后会有几个合约名为空的合约，需清理掉
        if str(kline.instrumentID) == '':
            continue
        # 如果不是7*24小时数据，需要进行数据清理
        if '7*24' not in g.broker_name:
            today = datetime.datetime.now().strftime('%Y-%m-%d')
            stamp = today + " " + str(kline.updateTime)
            timeArray = time.strptime(stamp, "%Y-%m-%d %H:%M:%S")
            timeStamp = int(time.mktime(timeArray))
            now = int(time.time())
            now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 时间戳之差超过1分钟即认为是无效数据
            if abs(now - timeStamp) > 120:
                print(f"marketdata delay : ID:{kline.instrumentID}, Stamp:{stamp}, Now:{now_time}")
                continue
        # if kline.InstrumentID == 'FG209':
        #     g.start = time.time()
        # print("开始分发策略至k线")
        t3 = Thread(target=distribute_Kline, args=(kline,))
        # print(id(t3))
        t3.start()


# 判断需要给哪些策略传Kline
def distribute_Kline(kline):
    # 交易账户登录成功后，传递数据
    if not g.tdLogin_flag:

        return
    for strategy in g.strategy_map.values():
        if kline.instrumentID in strategy.subID and kline.barType in strategy.subKlineType:
            t1 = Thread(target=save_Kline, args=(strategy, kline,))
            t1.start()


def save_Kline(strategy, kline):
    instrumentID = kline.instrumentID
    # print("开始上锁")
    strategy.specific_strategy_map[instrumentID].kline_lock.acquire()    # k线数据上锁，k线数据保存使用python字典内存完全够用，目前不需要用到redis
    strategy.specific_strategy_map[instrumentID].barData = kline

    # 调用策略中的行情事件
    # print("******开始调用k线Onbar*********")
    t2 = Thread(target=strategy.specific_strategy_map[instrumentID].onBar, )
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

    if orderRef in g.order_map.keys():
        orderfield.InstrumentID = g.order_map[str(orderRef)].instrumentID
    else:
        print(f'订单{orderRef}不在订单库中，请检查！')
        return -9

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
    path = '../交易流水/'
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
    # # 打印逐笔持仓明细
    # print(g.positionDetail_map)
    # for objName in g.positionDetail_map.keys():
    #     print(objName)
    #     print_object(g.positionDetail_map[objName])
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
            # 平多今
            if pTrade.OffsetFlag == '3' and pTrade.Direction == '1':
                # 获取今日多仓
                for positionName in positionName_list:
                    if '今' in positionName and '多' in positionName:
                        positionDetail = g.positionDetail_map[positionName]
                        break
            # 平空今
            if pTrade.OffsetFlag == '3' and pTrade.Direction == '0':
                # 获取今日持仓
                for positionName in positionName_list:
                    if '今' in positionName and '空' in positionName:
                        positionDetail = g.positionDetail_map[positionName]
                        break
            # 平昨, 多
            elif pTrade.OffsetFlag == '4' and pTrade.Direction == '1':
                # 获取昨日持仓
                for positionName in positionName_list:
                    if '昨' in positionName and '多' in positionName:
                        positionDetail = g.positionDetail_map[positionName]
                        break
            # 平昨， 空
            elif pTrade.OffsetFlag == '4' and pTrade.Direction == '0':
                # 获取昨日持仓
                for positionName in positionName_list:
                    if '昨' in positionName and '空' in positionName:
                        positionDetail = g.positionDetail_map[positionName]
                        break

        # 如果不是上期所或者能源中心
        else:
            # 平多
            if pTrade.Direction == '1':
                # 卖
                for positionName in positionName_list:
                    if '多' in positionName:
                        positionDetail = g.positionDetail_map[positionName]
                        break
            # 平空
            elif pTrade.Direction == '0':
                # 买
                for positionName in positionName_list:
                    if '空' in positionName:
                        positionDetail = g.positionDetail_map[positionName]
                    break
            # positionName = positionName_list[0]
            # positionDetail = g.positionDetail_map[positionName]
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
    write_to_csv('../交易流水/strategy{}_{}.csv'.format(strategyID, pTrade.InstrumentID), 'a', content)

    print('写完交易流水')
    # # 打印逐笔持仓明细
    # print(g.positionDetail_map)
    # for objName in g.positionDetail_map.keys():
    #     print(objName)
    #     print_object(g.positionDetail_map[objName])

    # # 全部成交
    # if g.order_map[pTrade.OrderRef].OrderStatus == '0':
    #     del g.order_map[pTrade.OrderRef]


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


def print_object_map(obj_map):
    # 逐个打印字典中保存的类中的变量
    print(obj_map)
    for objName in obj_map.keys():
        print(objName)
        print_object(obj_map[objName])


# 更新逐笔持仓明细
def updatePositionDetail(ExchangeID, Direction, InstrumentID, Volume, OpenPrice, OpenDate):
    # 如果不是上期所和能源中心，命名为：au2206_多，
    if ExchangeID != 'SHFE' and ExchangeID != 'INE':
        positionDirection = ''
        if Direction == '0':
            positionDirection = '多'
        elif Direction == '1':
            positionDirection = '空'
        positionDetailName = '{}_{}'.format(InstrumentID, positionDirection)

        # 如果该合约第一次出现，则创建持仓明细类，否则不用，直接添加参数即可
        if positionDetailName not in g.positionDetail_map.keys():
            g.positionDetail_map[positionDetailName] = positionDetailInfo()
        # g.positionDetail_map[positionDetailName].position_list.insert(0, copy.copy(pInvestorPositionDetail))
        # 在开仓价列表中添加开仓价
        for i in range(int(Volume)):
            g.positionDetail_map[positionDetailName].openPrice_list.insert(0, round(OpenPrice, 2))

    # 如果是上期所或者能源中心，命名为：昨_au2206_多
    elif ExchangeID == 'SHFE' or ExchangeID == 'INE':
        positionDirection = ''
        if Direction == '0':
            positionDirection = '多'
        elif Direction == '1':
            positionDirection = '空'
        positionDate = ''
        # 开仓日期指开仓时的交易日期
        if OpenDate == g.tradingDay:
            positionDate = '今'
        elif OpenDate != g.tradingDay:
            positionDate = '昨'
        # print(f'OpenDate:{OpenDate}')
        # print(f'g.tradingDay:{g.tradingDay}')
        positionDetailName = '{}_{}_{}'.format(positionDate, InstrumentID,
                                               positionDirection)
        # 如果该合约第一次出现，则创建持仓明细类，否则不用，之间添加参数即可
        if positionDetailName not in g.positionDetail_map.keys():
            g.positionDetail_map[positionDetailName] = positionDetailInfo()
        # g.positionDetail_map[positionDetailName].position_list.insert(0, copy.copy(pInvestorPositionDetail))
        # print(g.positionDetail_map[positionDetailName].position_list[])
        for i in range(int(Volume)):
            g.positionDetail_map[positionDetailName].openPrice_list.insert(0, round(OpenPrice, 2))


# 更新今天逐笔持仓明细
def updateTodayPositionDetail(ExchangeID, Direction, OffsetFlag, InstrumentID, Volume, OpenPrice, OpenDate):
    if OffsetFlag != '0':
        return
    # 如果不是上期所和能源中心，命名为：au2206_多，
    if ExchangeID != 'SHFE' and ExchangeID != 'INE':
        positionDirection = ''
        if Direction == '0':
            positionDirection = '多'
        elif Direction == '1':
            positionDirection = '空'
        positionDetailName = '{}_{}'.format(InstrumentID, positionDirection)

        # 如果该合约第一次出现，则创建持仓明细类，否则不用，直接添加参数即可
        if positionDetailName not in g.positionDetail_map.keys():
            g.positionDetail_map[positionDetailName] = positionDetailInfo()
        # g.positionDetail_map[positionDetailName].position_list.insert(0, copy.copy(pInvestorPositionDetail))
        # 在开仓价列表最后添加开仓价
        for i in range(int(Volume)):
            g.positionDetail_map[positionDetailName].openPrice_list.append(round(OpenPrice, 2))

    # 如果是上期所或者能源中心，命名为：昨_au2206_多
    elif ExchangeID == 'SHFE' or ExchangeID == 'INE':
        positionDirection = ''
        if Direction == '0':
            positionDirection = '多'
        elif Direction == '1':
            positionDirection = '空'
        positionDate = ''
        # 开仓日期指开仓时的交易日期
        if OpenDate == g.tradingDay:
            positionDate = '今'
        elif OpenDate != g.tradingDay:
            positionDate = '昨'
        # print(f'OpenDate:{OpenDate}')
        # print(f'g.tradingDay:{g.tradingDay}')
        positionDetailName = '{}_{}_{}'.format(positionDate, InstrumentID, positionDirection)
        # 如果该合约第一次出现，则创建持仓明细类，否则不用，之间添加参数即可
        if positionDetailName not in g.positionDetail_map.keys():
            g.positionDetail_map[positionDetailName] = positionDetailInfo()
        # g.positionDetail_map[positionDetailName].position_list.insert(0, copy.copy(pInvestorPositionDetail))
        # print(g.positionDetail_map[positionDetailName].position_list[])
        for i in range(int(Volume)):
            g.positionDetail_map[positionDetailName].openPrice_list.append(round(OpenPrice, 2))

# 记录资源占用情况
def process_monitor():
    cpu_percent = round(g.process.cpu_percent(None), 2)
    mem_percent = round(g.process.memory_percent(), 2)
    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    mem = round(g.process.memory_info().rss / 1024 / 1024, 2)
    content = [now_time, cpu_percent, mem, mem_percent]
    write_to_csv('../资源占用.csv', 'a', content)

def initProcessMonitor():
    content = ['当前时间', 'CPU使用（%）', '内存使用（MB）', '内存占用（%）']
    write_to_csv('../资源占用.csv', 'w', content)
    pid = os.getpid()
    g.process = psutil.Process(pid)

