from enum import Enum

"""
The enums below are based on string values found in the schema.xsd
"""
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


class TakePicture(Task):
    def __init__(
        self, number_of_pictures: int, name: str = ActionType.TAKETHERMALPICTURE
    ):
        super().__init__(name)
        self.number_of_pictures: int = number_of_pictures
