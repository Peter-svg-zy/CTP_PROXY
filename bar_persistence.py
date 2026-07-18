"""K线 MySQL 持久化组件。"""

import configparser
import os
import re
import threading
from datetime import date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "con_file" / "database.ini"
INTERVAL_MAP = {
    "min": "1m",
    "min3": "3m",
    "min5": "5m",
    "min10": "10m",
    "min15": "15m",
    "min30": "30m",
    "min60": "1h",
    "min120": "2h",
    "min180": "3h",
    "min240": "4h",
    "day": "1d",
    "week": "1w",
    "month": "1M",
}


class BarPersistenceError(RuntimeError):
    """数据库配置或写入失败。"""


def _parse_bool(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _safe_identifier(value, field_name):
    """表名不能通过 SQL 参数传入，必须严格校验后再拼接。"""
    if not re.fullmatch(r"[A-Za-z0-9_]+", value or ""):
        raise BarPersistenceError("非法{}: {!r}".format(field_name, value))
    return value


def load_database_config(config_path=None):
    """读取本地 INI；环境变量可覆盖配置，便于生产环境注入密码。"""
    path = Path(config_path or os.getenv("CTP_DB_CONFIG", str(DEFAULT_CONFIG_PATH)))
    parser = configparser.ConfigParser()
    if path.exists():
        parser.read(str(path), encoding="utf-8")
    section = parser["mysql"] if parser.has_section("mysql") else {}

    def setting(name, env_name, default):
        return os.getenv(env_name, section.get(name, default))

    return {
        "enabled": _parse_bool(setting("enabled", "CTP_DB_ENABLED", "true")),
        "host": setting("host", "CTP_DB_HOST", "127.0.0.1"),
        "port": int(setting("port", "CTP_DB_PORT", "3306")),
        "user": setting("user", "CTP_DB_USER", "root"),
        "password": setting("password", "CTP_DB_PASSWORD", ""),
        "database": _safe_identifier(setting("database", "CTP_DB_NAME", "ctp_sys"), "数据库名"),
        "table": _safe_identifier(setting("table", "CTP_DB_TABLE", "bar_data"), "表名"),
        "charset": setting("charset", "CTP_DB_CHARSET", "utf8mb4"),
        "connect_timeout": int(setting("connect_timeout", "CTP_DB_CONNECT_TIMEOUT", "3")),
    }


def resolve_bar_time(bar):
    """获得K线开始时间，优先使用合成阶段保存的完整时间。"""
    bar_time = getattr(bar, "barTime", None)
    if isinstance(bar_time, datetime):
        return bar_time.replace(microsecond=0)

    raw_day = getattr(bar, "actionDay", None) or date.today().strftime("%Y%m%d")
    raw_day = str(raw_day).replace("-", "")
    try:
        bar_date = datetime.strptime(raw_day, "%Y%m%d").date()
    except ValueError:
        bar_date = date.today()

    update_time = getattr(bar, "updateTime", None)
    if update_time is None:
        raise BarPersistenceError("K线缺少 updateTime，无法确定 current_time")
    return datetime.combine(bar_date, update_time).replace(microsecond=0)


class MySQLBarWriter:
    """线程安全、延迟连接的单根K线写入器。"""

    def __init__(self, config_path=None):
        self.config = load_database_config(config_path)
        self.enabled = self.config["enabled"]
        self._connection = None
        self._lock = threading.Lock()

    def _connect(self):
        try:
            import pymysql
        except ImportError as exc:
            raise BarPersistenceError(
                "缺少 PyMySQL，请在 CTP_1 环境执行: python -m pip install PyMySQL"
            ) from exc

        self._connection = pymysql.connect(
            host=self.config["host"],
            port=self.config["port"],
            user=self.config["user"],
            password=self.config["password"],
            database=self.config["database"],
            charset=self.config["charset"],
            connect_timeout=self.config["connect_timeout"],
            read_timeout=self.config["connect_timeout"],
            write_timeout=self.config["connect_timeout"],
            autocommit=True,
        )

    def _ensure_connection(self):
        if self._connection is None:
            self._connect()
        else:
            self._connection.ping(reconnect=True)

    def _sql(self):
        table = self.config["table"]
        return (
            "INSERT INTO `{}` "
            "(`contract_name`, `exchange`, `interval`, `current_time`, "
            "`open_price`, `high_price`, `low_price`, `close_price`, `volume`, `open_interest`) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "`exchange`=VALUES(`exchange`), `open_price`=VALUES(`open_price`), "
            "`high_price`=VALUES(`high_price`), `low_price`=VALUES(`low_price`), "
            "`close_price`=VALUES(`close_price`), `volume`=VALUES(`volume`), "
            "`open_interest`=VALUES(`open_interest`)"
        ).format(table)

    def write(self, bar):
        """写入或更新一根K线；返回是否实际启用了数据库写入。"""
        if not self.enabled:
            return False

        values = (
            str(bar.instrumentID),
            str(getattr(bar, "exchangeID", None) or "UNKNOWN"),
            INTERVAL_MAP.get(str(bar.barType), str(bar.barType)),
            resolve_bar_time(bar),
            bar.openPrice,
            bar.highPrice,
            bar.lowPrice,
            bar.closePrice,
            max(int(bar.volume), 0),
            max(int(bar.openInterest), 0),
        )

        with self._lock:
            try:
                self._ensure_connection()
                with self._connection.cursor() as cursor:
                    cursor.execute(self._sql(), values)
            except Exception:
                self.close()
                # 连接中断时重建连接后仅重试一次，避免无限阻塞策略线程。
                self._connect()
                with self._connection.cursor() as cursor:
                    cursor.execute(self._sql(), values)
        return True

    def close(self):
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None

