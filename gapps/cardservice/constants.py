""" """
from enum import Enum

class DateTimePickerType(Enum):
    DATE_ONLY = 'DATE_ONLY'
    DATE_AND_TIME = 'DATE_AND_TIME'
    TIME_ONLY = 'TIME_ONLY'

class BorderType(Enum):
    NO_BORDER = 'NO_BORDER'
    STROKE = 'STROKE'


class ComposedEmailType(Enum):
    REPLY_AS_DRAFT = 'REPLY_AS_DRAFT'
    STANDALONE_DRAFT = 'STANDALONE_DRAFT'


class ContentType(Enum):
    TEXT = 'TEXT'
    MUTABLE_HTML = 'MUTABLE_HTML'
    IMMUTABLE_HTML = 'IMMUTABLE_HTML'
    UNSPECIFIED_CONTENT_TYPE = 'UNSPECIFIED_CONTENT_TYPE'


class DisplayStyle(Enum):
    PEEK = 'PEEK'
    REPLACE = 'REPLACE'


class GridItemLayout(Enum):
    TEXT_BELOW = 'TEXT_BELOW'
    TEXT_ABOVE = 'TEXT_ABOVE'


class HorizontalAlignment(Enum):
    START = 'START'
    CENTER = 'CENTER'
    END = 'END'


class Icon(Enum):
    NONE = 'NONE'
    AIRPLANE = 'AIRPLANE'
    BOOKMARK = 'BOOKMARK'
    BUS = 'BUS'
    CAR = 'CAR'
    CLOCK = 'CLOCK'
    CONFIRMATION_NUMBER_ICON = 'CONFIRMATION_NUMBER_ICON'
    DOLLAR = 'DOLLAR'
    DESCRIPTION = 'DESCRIPTION'
    EMAIL = 'EMAIL'
    EVENT_PERFORMER = 'EVENT_PERFORMER'
    EVENT_SEAT = 'EVENT_SEAT'
    FLIGHT_ARRIVAL = 'FLIGHT_ARRIVAL'
    FLIGHT_DEPARTURE = 'FLIGHT_DEPARTURE'
    HOTEL = 'HOTEL'
    HOTEL_ROOM_TYPE = 'HOTEL_ROOM_TYPE'
    INVITE = 'INVITE'
    MAP_PIN = 'MAP_PIN'
    MEMBERSHIP = 'MEMBERSHIP'
    MULTIPLE_PEOPLE = 'MULTIPLE_PEOPLE'
    OFFER = 'OFFER'
    PERSON = 'PERSON'
    PHONE = 'PHONE'
    RESTAURANT_ICON = 'RESTAURANT_ICON'
    SHOPPING_CART = 'SHOPPING_CART'
    STAR = 'STAR'
    STORE = 'STORE'
    TICKET = 'TICKET'
    TRAIN = 'TRAIN'
    VIDEO_CAMERA = 'VIDEO_CAMERA'
    VIDEO_PLAY = 'VIDEO_PLAY'


class ImageCropType(Enum):
    SQUARE = 'SQUARE'
    CIRCLE = 'CIRCLE'
    RECTANGLE_CUSTOM = 'RECTANGLE_CUSTOM'
    RECTANGLE_4_3 = 'RECTANGLE_4_3'


class ImageStyle(Enum):
    SQUARE = 'SQUARE'
    CIRCLE = 'CIRCLE'


class LoadIndicator(Enum):
    SPINNER = 'SPINNER'
    NONE = 'NONE'


class OnClose(Enum):
    NOTHING = 'NOTHING'
    RELOAD = 'RELOAD'


class OpenAs(Enum):
    FULL_SIZE = 'FULL_SIZE'
    OVERLAY = 'OVERLAY'


class SelectionInputType(Enum):
    CHECK_BOX = 'CHECK_BOX'
    RADIO_BUTTON = 'RADIO_BUTTON'
    DROPDOWN = 'DROPDOWN'


class SwitchControlType(Enum):
    SWITCH = 'SWITCH'
    CHECK_BOX = 'CHECK_BOX'


class TextButtonStyle(Enum):
    FILLED = 'FILLED'
    TEXT = 'TEXT'


class TextInputStyle(Enum):
    SINGLE_LINE = 'SINGLE_LINE'
    MULTIPLE_LINE = 'MULTIPLE_LINE'


class UpdateDraftBodyType(Enum):
    IN_PLACE_INSERT = 'IN_PLACE_INSERT'
    INSERT_AT_START = 'INSERT_AT_START'
    INSERT_AT_END = 'INSERT_AT_END'
    UNSPECIFIED_ACTION_TYPE = 'UNSPECIFIED_ACTION_TYPE'
    REPLACE = 'REPLACE'
