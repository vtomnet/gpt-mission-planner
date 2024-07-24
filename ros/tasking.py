from enum import Enum
from typing import Tuple

from lxml import etree

"""
The enums below are based on string values found in the schema.xsd
"""
# This defines the tag types throughout the schema document
class ElementTags(str, Enum):
    ACTION = "Action"
    ACTIONTYPE = "ActionType"
    ATOMICTASKS = "AtomicTasks"
    CONTROLCONSTRUCT = "ControlConstruct"
    PARAMETERS = "Parameters"
    PRECONDITION = "Precondition"
    PRECONDITIONS = "Preconditions"
    SEQUENCE = "Sequence"
    TASKID = "TaskID"


class ActionType(str, Enum):
    MOVETOLOCATION = "moveToLocation"
    TAKETHERMALPICTURE = "takeThermalPicture"


class ParameterTypes(str, Enum):
    LATITUDE = "Latitude"
    LONGITUDE = "Longitude"


class Task:
    def __init__(self, name: str):
        self.name: str = name


class GoToLocation(Task):
    def __init__(self, lat: float, long: float, name: str = ActionType.MOVETOLOCATION):
        super().__init__(name)
        self.lat_tag: str = ParameterTypes.LATITUDE
        self.long_tag: str = ParameterTypes.LONGITUDE
        self.lat: float = lat
        self.long: float = long

    @staticmethod
    def parse_lat_long(action: etree._Element, namespace: str) -> Tuple[float, float]:
        mtl: etree._Element = action.find(namespace + ActionType.MOVETOLOCATION)
        if mtl is not None:
            lat: etree._Element = mtl.find(namespace + ParameterTypes.LATITUDE)
            long: etree._Element = mtl.find(namespace + ParameterTypes.LONGITUDE)

            if lat is not None and long is not None:
                return float(lat.text), float(long.text)
        else:
            return None, None


class TakePicture(Task):
    def __init__(
        self, number_of_pictures: int, name: str = ActionType.TAKETHERMALPICTURE
    ):
        super().__init__(name)
        self.number_of_pictures: int = number_of_pictures
