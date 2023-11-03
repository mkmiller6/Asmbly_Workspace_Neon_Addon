"""Module to manage fastapi models."""

from typing import List
from pydantic import BaseModel, Field
from .constants import *


class TimeZone(BaseModel):
    id: str
    offset: int


class CommonEvent(BaseModel):
    userLocale: str
    hostApp: str
    platform: str
    timeZone: TimeZone
    parameters: dict = {}
    formInputs: dict = {}


class AuthorizationEvent(BaseModel):
    userOAuthToken: str
    systemIdToken: str
    userIdToken: str


class DriveItem(BaseModel):
    id: str = None
    iconUrl: str = None
    mimeType: str = None
    title: str = None
    addonHasFileScopePermission: bool = False


class DriveEvent(BaseModel):
    selectedItems: List[DriveItem] = []
    activeCursorItem: DriveItem = None


class EditorEvent(BaseModel):
    """Docs, Sheets, slides """
    id: str = None
    title: str = None
    addonHasFileScopePermission: bool = False


class GmailEvent(BaseModel):
    messageId: str = None
    threadId: str = None
    accessToken: str = None
    toRecipients: List[str] = []
    ccRecipients: List[str] = []
    bccRecipients: List[str] = []


class Organizer(BaseModel):
    email: str = None


class Capabilities(BaseModel):
    canSeeAttendees: bool = None
    canAddAttendees: bool = None
    canSeeConferenceData: bool = None
    canSetConferenceData: bool = None


class Attendee(BaseModel):
    email: str = None
    optional: bool = None
    displayName: str = None
    organizer: bool = None
    # self: bool = None
    resource: bool = None
    responseStatus: str = None
    comment: str = None
    additionalGuests: int = None


class ConferenceSolution(BaseModel):
    iconUri: str = None
    key: dict = None
    name: str = None


class EntryPoint(BaseModel):
    accessCode: str = None
    entryPointFeatures: List[str] = None
    entryPointType: str = None
    label: str = None
    meetingCode: str = None
    passcode: str = None
    password: str = None
    pin: str = None
    regionCode: str = None
    uri: str = None


class ConferenceData(BaseModel):
    conferenceId: str = None
    conferenceSolution: ConferenceSolution = None
    entryPoints: List[EntryPoint] = None
    notes: str = None
    parameters: dict = None


class CalendarEvent(BaseModel):
    id: str = None   # the event id
    recurringEventId: str = None
    calendarId: str = None
    organizer: Organizer = None
    attendees: List[Attendee] = []
    conferenceData: ConferenceData = None
    capabilities: Capabilities = None


class GEvent(BaseModel):
    commonEventObject: CommonEvent
    authorizationEventObject: AuthorizationEvent
    drive: DriveEvent = None
    docs: EditorEvent = None
    sheets: EditorEvent = None
    slides: EditorEvent = None
    gmail: GmailEvent = None
    calendar: CalendarEvent = None


class Action(BaseModel):
    function: str


class OpenLink(BaseModel):
    url: str
    openAs: OpenAs = None
    onClose: OnClose = None


class OnClick(BaseModel):
    openLink: OpenLink = None
    action: Action = None
    openDynamicLinkAction: Action = None


class CardAction(BaseModel):
    actionLabel: str = None
    onClick: OnClick = None


class CardHeader(BaseModel):
    title: str = None
    subtitle: str = None
    image: str = None
    imageType: ImageStyle = None
    imageAltText: str = None


class KnownIcon(BaseModel):
    knownIcon: Icon


class Color(BaseModel):
    red: float = Field(..., ge=0, le=1)
    green: float = Field(..., ge=0, le=1)
    blue: float = Field(..., ge=0, le=1)
    alpha: float = None


class Button(BaseModel):
    text: str
    onClick: OnClick
    disabled: bool = None
    icon: KnownIcon = None
    color: Color = None


class FixedFooter(BaseModel):
    primaryButton: Button= None
    secondaryButton: Button = None


class ButtonList(BaseModel):
    buttons: list[Button]


class TextParagraph(BaseModel):
    text: str


class SelectionItem(BaseModel):
    text: str = ''
    value: str = None
    selected: bool = False


class DateTimePicker(BaseModel):
    name: str = None
    label: str = None
    type: DateTimePickerType = None
    valueMsEpoch: int = None
    timezoneOffsetDate: int = None
    onChangeAction: Action = None


class Image(BaseModel):
    imageUrl: str
    altText: str = None
    onClick: OnClick = None


class SwitchControl(BaseModel):
    name: str = None
    value: str = None
    selected: bool = False
    onChangeAction: Action = None
    controlType: SwitchControlType = None


class DecoratedText(BaseModel):
    text: str 
    bottomLabel: str = None
    topLabel: str = None
    switchControl: SwitchControl = None
    icon: KnownIcon = None
    button: Button = None
    onClick: OnClick = None
    imageType: ImageStyle = None
    wrapText: bool = None


class SelectionInput(BaseModel):
    name: str
    on_change_action: Action = None
    items: list[SelectionItem] = None
    type: SelectionInputType = None
    label: str = None


class SuggestionItem(BaseModel):
    text: str = None


class Suggestion(BaseModel):
    items: list[SuggestionItem] = []


class TextInput(BaseModel):
    name: str
    label: str = None
    hintText: str = None
    value: str = None
    type: TextInputStyle = None
    onChangeAction: Action = None
    initialSuggestions: list[Suggestion] = None
    autoCompleteAction: Action = None
    multipleSuggestions: bool = None


class Widget(BaseModel):
    textParagraph: TextParagraph = None
    image: Image = None
    decoratedText: DecoratedText = None
    buttonList: ButtonList = None
    textInput: TextInput = None
    selectionInput: SelectionInput = None
    dateTimePicker: DateTimePicker = None
    horizontalAlignment: HorizontalAlignment = None
    divider: dict = {}


class Section(BaseModel):
    header: str = None
    collapsible: bool = None
    widgets: list[Widget]
    uncollapsibleWidgetsCount: int = None


class Card(BaseModel):
    header: CardHeader = None
    sections: list[Section]
    cardActions: CardAction = None
    name: str = None
    fixedFooter: FixedFooter = None
    displayStyle: DisplayStyle = None
    peekCardHeader: CardHeader = None


class Notification(BaseModel):
    text: str = None


class Navigations(BaseModel):
    pushCard: Card = None
    updateCard: Card = None
    popToCard: str = None
    popToRoot: bool = None
    pop: bool = None


class Action(BaseModel):
    notification: Notification = None
    navigations: Navigations = None
    link: OpenLink = None

class InsertContent(BaseModel):
    content: str = None
    contentType: ContentType = None


class UpdateBody(BaseModel):
    type:  UpdateDraftBodyType = None
    insertContents: list[InsertContent] = []


class UpdateSubject(BaseModel):
    subject: str = None


class Recipient(BaseModel):
    email: str = None


class UpdateToRecipients(BaseModel):
    toRecipients: list[Recipient] = []


class UpdateCcRecipients(BaseModel):
    ccRecipients: list[Recipient] = []


class UpdateBccRecipients(BaseModel):
    bccRecipients: list[Recipient] = []


class UpdateDraftActionMarkup(BaseModel):
    updateBody: UpdateBody = None
    updateSubject: UpdateSubject = None
    updateToRecipients: UpdateToRecipients = None
    updateCcRecipients: UpdateCcRecipients = None
    updateBccRecipients: UpdateBccRecipients = None


class OpenCreatedDraftActionMarkup(BaseModel):
    draftId: str = None
    draftThreadId: str = None


class GmailAction(BaseModel):
    updateDraftActionMarkup: UpdateDraftActionMarkup = None
    openCreatedDraftActionMarkup: OpenCreatedDraftActionMarkup = None


class HostAppAction(BaseModel):
    gmailAction: GmailAction = None


class RenderActions(BaseModel):
    action: Action = None
    hostAppAction: HostAppAction = None

