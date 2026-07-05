import os
import sys
import time
import threading

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# 路径修改完成后，再导入自定义模块
from CTP_API import thostmduserapi as mdapi
import Global_Param as g
from function import *

"""实现获取合约行情功能"""


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
        g.subID = ['rb2610', 'hc2610']
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

    def OnRtnDepthMarketData(self,pDepthMarketData):
        """
        深度行情回传接口
        pDepthMarketData:行情结构提包含，InstrumentID,LastPrice
        :return:
        """
        print('订阅合约为：{},最新价格为：{}'.format(pDepthMarketData.InstrumentID, pDepthMarketData.LastPrice))



class CTP_Md(object):
    def __init__(self, **kwargs):
        pass

    def connect_to_md(self):
        self.mduserapi = mdapi.CThostFtdcMdApi_CreateFtdcMdApi('../con_file/')  # 创建api实例
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



if __name__ == '__main__':
    ctp_md = CTP_Md()
    ctp_md.connect_to_md()

    # --- 在这里继续执行你的后续业务代码 ---
    print("CTP 行情线程已启动，主线程继续执行...")
    # 你的其他业务逻辑...

    # 保持主线程存活，防止程序直接退出
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("程序手动退出")
