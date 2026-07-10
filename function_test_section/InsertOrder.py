import os
import sys
import time
import threading
import json
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# 路径修改完成后，再导入自定义模块
from CTP_API import thostmduserapi as mdapi
from CTP_API import thosttraderapi as tdapi
from StrategyFloder import Stragety1
import Global_Param as g
from function import *


"""实现下单功能，非常重要的章节"""


# 创建回调接口spi
class CFtdcMdSpi(mdapi.CThostFtdcMdSpi):
    def __init__(self, mduserapi):
        mdapi.CThostFtdcMdSpi.__init__(self)
        self.mduserapi = mduserapi

    # 当客户端与交易后台建立起通信连接时（还未登录前），该方法被调用
    def OnFrontConnected(self):
        loginfield = mdapi.CThostFtdcReqUserLoginField()
        loginfield.BrokerID = g.broker_id
        loginfield.UserID = g.investorID
        loginfield.Password = g.password

        ret = self.mduserapi.ReqUserLogin(loginfield, 0)  # 调用mduserapi的用户登录接口
        if ret == 0:
            print('发送用户登录行情请求成功')
        else:
            print('发送用户登录行情账户请求失败！')
            judge_ret(ret)

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        """用户登录的回调接口"""
        # 先判断 pRspInfo 是否为 None，防止登录成功时空指针异常
        if pRspInfo is not None and pRspInfo.ErrorID != 0:
            print('行情连接失败\n错误信息为：{}\n错误代码为：{}'.format(pRspInfo.ErrorMsg, pRspInfo.ErrorID))
        else:
            print('行情账户登录成功！')

        """行情订阅，调用mduserapi的SubscribeMarkData接口"""
        ret = self.mduserapi.SubscribeMarketData([id.encode('utf-8') for id in g.subID], len(g.subID))
        if ret == 0:
            print('获取行情订阅成功')
            # print(bIsLast)
        else:
            judge_ret(ret)

    def OnRspSubMarketData(self, pSpecificInstrument, pRspInfo, nRequestID, bIsLast):
        """SubscribeMarketData的回调接口，返回订阅合约代码，报错信息
           nRequestID：返回用户操作请求的ID，该ID 由用户在操作请求时指定这里是0
           bIsLast：指示该次返回是否为针对nRequestID的最后一次返回,返回值为True或者False"""
        if pRspInfo is not None and pRspInfo.ErrorID != 0:
            print('订阅行情失败\n错误信息为：{}\n错误代码为：{}'.format(pRspInfo.ErrorMsg, pRspInfo.ErrorID))
        else:
            print("订阅合约成功，合约为代码为：{}".format(pSpecificInstrument.InstrumentID))
        if bIsLast:
            print('传送数据至策略模块')
            t4 = Thread(target=get_data)
            t4.start()



    def OnRtnDepthMarketData(self,pDepthMarketData):
        """
        深度行情回传接口
        pDepthMarketData:行情结构提包含，InstrumentID,LastPrice
        :return:
        """
        # print('订阅合约为：{},最新价格为：{}'.format(pDepthMarketData.InstrumentID, pDepthMarketData.LastPrice))
        g.dataQueue.put(pDepthMarketData)

class CTraderSpi(tdapi.CThostFtdcTraderSpi):
    def __init__(self, tduserapi):
        tdapi.CThostFtdcTraderSpi.__init__(self)
        self.tduserapi = tduserapi

    # 连接前台
    def OnFrontConnected(self):
        print("开始建立交易连接")
        authfield = tdapi.CThostFtdcReqAuthenticateField()
        authfield.BrokerID = g.broker_id
        authfield.UserID = g.investorID
        authfield.AppID = g.appID
        authfield.AuthCode = g.authcode
        ret = self.tduserapi.ReqAuthenticate(authfield, 0)
        if ret == 0:
            print('发送穿透式认证请求成功！')
        else:
            print('发送穿透式认证请求失败！')
            judge_ret(ret)

    # 穿透式认证响应
    def OnRspAuthenticate(self, pRspAuthenticateField, pRspInfo, nRequestID, bIsLast):
        if pRspInfo.ErrorID != 0 and pRspInfo != None:
            print('穿透式认证失败\n错误信息为：{}\n错误代码为：{}'.format(pRspInfo.ErrorMsg, pRspInfo.ErrorID))
        else:
            print('穿透式认证成功！')

            # 发送登录请求
            loginfield = tdapi.CThostFtdcReqUserLoginField()
            loginfield.BrokerID = g.broker_id

            loginfield.UserID = g.investorID
            loginfield.Password = g.password

            ret = self.tduserapi.ReqUserLogin(loginfield, 0)
            if ret == 0:
                print('发送登录交易账户成功！')
            else:
                print('发送登录交易账户失败！')
                judge_ret(ret)

    # 用户登录结果返回
    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        if pRspInfo.ErrorID != 0 and pRspInfo != None:
            print('登录交易账户失败\n错误信息为：{}\n错误代码为：{}'.format(pRspInfo.ErrorMsg, pRspInfo.ErrorID))
        else:
            print('登录交易账户成功！')

        # 保存数据用于下单
        g.frontID = pRspUserLogin.FrontID
        g.sessionID = pRspUserLogin.SessionID
        g.maxOrderRef = int(pRspUserLogin.MaxOrderRef)

        # 保存交易日
        g.tradingDay = pRspUserLogin.TradingDay

        pSettlementInfoConfirm = tdapi.CThostFtdcSettlementInfoConfirmField()
        pSettlementInfoConfirm.BrokerID = g.broker_id
        pSettlementInfoConfirm.InvestorID = g.investorID
        ret = self.tduserapi.ReqSettlementInfoConfirm(pSettlementInfoConfirm, 0)
        if ret == 0:
            print('发送结算单确认请求成功！')
        else:
            print('发送结算单确认请求失败！')
            judge_ret(ret)

    # 结算单结果确认
    def OnRspSettlementInfoConfirm(self, pSettlementInfoConfirm, pRspInfo, nRequestID, bIsLast):
        if pRspInfo.ErrorID != 0 and pRspInfo != None:
            print('结算单确认失败\n错误信息为：{}\n错误代码为：{}'.format(pRspInfo.ErrorMsg, pRspInfo.ErrorID))
        else:
            print('结算单确认成功！')

        # print("OnRspSettlementInfoConfirm")
        # print("ErrorID=", pRspInfo.ErrorID)
        # print("ErrorMsg=", pRspInfo.ErrorMsg)
        # # ReqorderfieldInsert(self.tduserapi)
        # print("send ReqorderfieldInsert ok")

    def OnRspQryProduct(self, pProduct, pRspInfo, nRequestID, bIsLast):
        # if pRspInfo.ErrorID != 0 and pRspInfo != None:
        #     print('查询产品失败\n错误信息为：{}\n错误代码为：{}'.format(pRspInfo.ErrorMsg, pRspInfo.ErrorID))
        # else:
        #     print('查询产品成功！')
        #     print(f'{pProduct}')
        # 修改值
        try:
            sec = pProduct.ProductID
            opt = '合约乘数'
            # 需要判断section是否存在，如果不存在会报错，option不需要检查是否存在
            if not g.productInfo.has_section(sec):
                g.productInfo.add_section(sec)
            g.productInfo.set(sec, opt, str(pProduct.VolumeMultiple))

            opt = '最小变动价位'
            g.productInfo.set(sec, opt, str(pProduct.PriceTick))

            if bIsLast:
                g.productInfo.write(open(g.productInfo_fileName, "w", encoding='utf-8'))
                print('查询产品成功！')
        except Exception as e:
            print(e)

        # print('产品名称：{}，交易所名称{}'.format(pProduct.ProductID, pProduct.ExchangeID))

    """*********************************************************************"""
    def OnRspQryInstrument(self, pInstrument, pRspInfo, nRequestID, bIsLast):
        """
         查询合约信息的回调接口
         参数  pInstrument：为合约信息结构体包含InstrumentID，ExchangeID
              pRspInfo： 报错信息结构体
        """
        # try:
        #     if pRspInfo.ErrorID != 0 and pRspInfo != None:
        #         print('查询合约失败\n错误信息为：{}\n错误代码为：{}'.format(pRspInfo.ErrorMsg, pRspInfo.ErrorID))
        #     else:
        #         print('查询合约成功！')
        # except Exception as e:
        #     # 'NoneType' object has no attribute 'ErrorID'
        #     # 可能是接口转换时有问题，但是影响不大
        #     # print(e)
        #     red_print(e)
        print("合约代码为{}，对应的交易所为{}".format(pInstrument.InstrumentID,pInstrument.ExchangeID))

        g.ExchangeID[pInstrument.InstrumentID] = pInstrument.ExchangeID
        if bIsLast:
            with open('../con_file/ExchangeID.json', 'w', newline='\n', encoding='utf-8') as f:
                # json.dump(ExchangeID, f, ensure_ascii=False)
                data = json.dumps(g.ExchangeID, indent=4, ensure_ascii=False)
                f.write(data)
            print('查询合约完成')



class CTP_T(object):
    def __init__(self, **kwargs):
          g.strategy_map[1] = Stragety1.strategy1()
          init_subID()

    def connect_to_md(self):
        self.mduserapi = mdapi.CThostFtdcMdApi_CreateFtdcMdApi('../con_file/')  # 创建mdapi实例
        self.mduserspi = CFtdcMdSpi(self.mduserapi)  # spi实例
        g.mduserapi = self.mduserapi
        g.mduserspi = self.mduserspi

        # 登录行情前置服务器
        self.mduserapi.RegisterFront(g.market_server_front)
        # 将spi注册给api
        self.mduserapi.RegisterSpi(self.mduserspi)
        # API正式启动，dll底层会自动去连上面注册的地址
        self.mduserapi.Init()

        # 将 Join() 放入独立线程，专门用于维持 CTP 网络通信
        ctp_thread = threading.Thread(target=self.mduserapi.Join)
        ctp_thread.daemon = True  # 设置为守护线程，主线程退出时它也会自动退出
        ctp_thread.start()

    def connect_to_td(self):
        self.tduserapi = tdapi.CThostFtdcTraderApi_CreateFtdcTraderApi('../con_file/')
        # 创建SPI实例。CTraderSpi是继承自头文件中CThostFtdcTraderSpi的类型，
        # 用于收从CTP的回复，可以重写父类中的函数来实现自己的逻辑
        self.tduserspi = CTraderSpi(self.tduserapi)

        # 保存api和spi
        g.tduserapi = self.tduserapi
        g.tduserspi = self.tduserspi

        # 将创建的SPI实例注册进实例，这样该API实例发出的请求对应的回报就会回调到对应的SPI实例的函数
        self.tduserapi.RegisterSpi(self.tduserspi)

        # 订阅共有流与私有流。订阅方式主要有三种，分为断点续传，重传和连接建立开始传三种。
        # TERT_RESTART：从本交易日开始重传。
        # TERT_RESUME：从上次收到的续传。
        # TERT_QUICK：只传送登录后的内容。
        self.tduserapi.SubscribePrivateTopic(tdapi.THOST_TERT_QUICK)
        self.tduserapi.SubscribePublicTopic(tdapi.THOST_TERT_QUICK)

        # 注册前置地址，是指将CTP前置的IP地址注册进API实例内
        self.tduserapi.RegisterFront(g.trade_server_front)

        # API启动，init之后就会启动一个内部线程读写，并去连CTP前置
        self.tduserapi.Init()

    def qryInstrument(self):
        """
        查询合约对应的交易信息接口，回调接口（OnRspQryInstrument）返回对应合约的交易所代码，产品代码等。
        """
        queryFile = tdapi.CThostFtdcQryInstrumentField() # 构建查询接口文件
        ret=self.tduserapi.ReqQryInstrument(queryFile,0) #只填文件和0参数，对合约进行全量查询
        if ret == 0:
            print("查询合约请求成功")
        else:
            print("查询合约请求失败")
            judge_ret(ret)
            while ret != 0:
                queryFile = tdapi.CThostFtdcQryInstrumentField()
                ret = self.tduserapi.ReqQryInstrument(queryFile, 0)
                print('正在查询合约...')
                time.sleep(5)
        time.sleep(1)
    def queryProduct(self):
        """
        查询合约对应的产品信息接口，对应回调接口 OnRspQryProduct，返回合约乘数，最小变动价位等
        """
        queryFile = tdapi.CThostFtdcQryProductField()
        ret =self.tduserapi.ReqQryProduct(queryFile,0)  # 空文件参数查询所有产品
        if ret == 0:
            print("查询产品请求成功")
        else:
            print("查询产品请求失败")
            judge_ret(ret)
            while ret != 0:
                queryFile = tdapi.CThostFtdcQryProductField()
                ret = self.tduserapi.ReqQryProduct(queryFile, 0)
                print('正在查询产品...')
                time.sleep(5)
        time.sleep(1)





if __name__ == '__main__':
    ctp_T = CTP_T()
    ctp_T.connect_to_td()
    # --- 在这里继续执行你的后续业务代码 ---
    time.sleep(3)
    ctp_T.queryProduct()

    # 你的其他业务逻辑...

    # 保持主线程存活，防止程序直接退出
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("程序手动退出")
