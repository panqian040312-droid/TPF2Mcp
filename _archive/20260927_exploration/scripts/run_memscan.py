"""启动内存扫描（中文参数走代码，避免 shell 编码问题）。"""
import sys

sys.argv = [
    "mem_scan.py",
    "",  # 空 -> 自动查找 TransportFever2.exe
    "--balance", "113613132814",
    "--lines", "224503,98983,15164",
    "--names", "京广客运,JY客运,JI线路",
]
import mem_scan  # noqa: E402

mem_scan.main()
