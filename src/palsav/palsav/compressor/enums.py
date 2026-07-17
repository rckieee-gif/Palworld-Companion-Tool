from enum import Enum
class SaveType(Enum):
    CNK = 48
    PLM = 49
    PLZ = 50
    @staticmethod
    def is_valid(save_type: int) -> bool:
        return save_type in (SaveType.PLZ.value, SaveType.PLM.value, SaveType.CNK.value)
class MagicBytes(Enum):
    PLZ = b'PlZ'
    PLM = b'PlM'
    CNK = b'CNK'
    @staticmethod
    def is_valid(magic: bytes) -> bool:
        return magic in (MagicBytes.PLZ.value, MagicBytes.PLM.value, MagicBytes.CNK.value)