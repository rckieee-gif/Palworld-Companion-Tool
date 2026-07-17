import logging
import sys
class TimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        from time import strftime, gmtime
        return strftime('%I:%M:%S %p', gmtime(record.created))
_LOG_FORMAT = '[%(asctime)s] [%(levelname)s] %(message)s'
_DEBUG_FORMAT = '[%(asctime)s] [%(levelname)s] %(message)s [%(funcName)s:%(lineno)d]'
_LOGGED = False
def setup_logging(level=logging.INFO, debug=False, debug_log=False, quiet=False):
    global _LOGGED
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else level)
    if not _LOGGED and (not quiet):
        if not any((isinstance(h, logging.StreamHandler) and h.stream is sys.stderr for h in root.handlers)):
            handler = logging.StreamHandler(sys.stderr)
            handler.setLevel(logging.DEBUG if debug else level)
            handler.setFormatter(TimeFormatter(_LOG_FORMAT))
            root.addHandler(handler)
    if debug_log:
        fh = logging.FileHandler('palworld-companion-tools-debug.log', mode='w', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(TimeFormatter(_DEBUG_FORMAT))
        root.addHandler(fh)
    _LOGGED = True
from . import compressor, archive, gvas, json_tools, core, paltypes, rawdata, _cityhash
