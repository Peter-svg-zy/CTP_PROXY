项目简述：本项目从0开始搭建CTP系统，通过订阅simnow行情数据合成k线传递至策略进行下单。

运行环境：python=3.8.x 

项目文件夹简述

CTP_API：上期技术提供的API接口文档，包含行情，交易接口以及回调接口。

StrategyFloder:策略文件夹，strategy1实现tick级高频交易,stragety2目前配置经典的Aberration中长线策略。

con_file：配置文件夹程序初始化阶段生成更新，包含ExchangeID(记录全市场合约对应交易所),productInfo.ini(记录产品的合约乘数以及最小变动价位)。

function_test_section:从简单到复杂，通过调用CTP_API接口实现各个小功能的文件夹，可直接单独调用运行。Global_Param.py保存全局变量，function.py功能函数文件，UserStruct.py结构体定义

交易流水：当订单状态发生改变触发写交易流水函数记录

实时数据：当k线数据传送到策略时，策略进行判断的同时进行本地保存。


项目框架参考：https://www.bilibili.com/video/BV1z541117Vd/?spm_id_from=333.337.search-card.all.click&vd_source=4b3bb0f26819d3587dc117e2cf9548f6
