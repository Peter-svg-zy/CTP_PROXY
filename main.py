from CTP_API import thostmduserapi as tdapi
from CTP_API import thostmduserapi as mdapi
import Global_Param as g
from function import *

#创建回调接口spi
class CFtdcMdSpi(mdapi.CThostFtdcMdSpi):
    def __init__(self, mduserapi):
        mdapi.CThostFtdcMdSpi.__init__(self)
        self.mduserapi =mduserapi
    # 当客户端与交易后台建立起通信连接时（还未登录前），该方法被调用
    def OnFrontConnected(self):
        loginfield = mdapi.CThostFtdcReqUserLoginField()
        loginfield.BrokerID = g.broker_id
        loginfield.UserID = g.investorID
        loginfield.Password =g.password

        ret= self.mduserapi.ReqUserLogin(loginfield,0)
        if ret == 0:
            print('发送用户登录行情请求成功')
        else:
            print('发送用户登录行情账户请求失败！')
            judge_ret(ret)

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        if pRspInfo.ErrorID != 0 and pRspInfo != None:
            print('行情连接失败\n错误信息为：{}\n错误代码为：{}'.format(pRspInfo.ErrorMsg, pRspInfo.ErrorID))
        else:
            print('行情账户登录成功！')

            g.subID = ["FG266", "SA266", 'au2609', 'sc2609']
            # 订阅行情
            ret = self.mduserapi.SubscribeMarketData([id.encode('utf-8') for id in g.subID],
                                                     len(g.subID))
            if ret == 0:
                print('发送订阅合约请求成功！')
            else:
                print('发送订阅合约请求失败！')
                judge_ret(ret)


class CTP_MdLogin:
    def __init__(self, **kwargs):
        def connect_to_md():
            self.mduserapi=mdapi.CThostFtdcMdApi_CreateFtdcMdApi('./con_file')#创建api实例
            self.mduserspi=None #spi实例
            g.mduserapi=self.mduserapi
            g.mduserspi=self.mduserapi




