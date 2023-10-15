from openPathUpdateSingle import openPathUpdateSingle
from helpers import neon

import httpx
import json
import datetime
import os
import time
import pytz

from fastapi import FastAPI
from functools import lru_cache

from gapps import CardService
from gapps.cardservice import models

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.id_token import verify_oauth2_token, exceptions
from google.auth.transport import requests
from google.cloud import secretmanager
import google_crc32c

app = FastAPI(title='Neon Workspace Integration')

static_keys = json.loads(os.environ.get('static_keys'))

GCLOUD_PROJECT_ID = static_keys.get("project_id")
CLIENT_ID = static_keys.get("client_id")
GSUITE_DOMAIN_NAME = static_keys.get("gsuite_domain")
SERVICE_ACCT_EMAIL = static_keys.get("service_acct_email")
NEON_API_USER = static_keys.get("N_APIuser")
G_USER = static_keys.get("G_user")
G_PASS = static_keys.get("G_password")

def create_secret(client: secretmanager.SecretManagerServiceClient, project_id: str, secret_id: str, payload: str) -> secretmanager.CreateSecretRequest:
    """
    Create a new secret with the given name, then create a secret version. A secret is a logical wrapper
    around a collection of secret versions. Secret versions hold the actual
    secret material.
    """
    # Build the resource name of the parent project.
    parent = f"projects/{project_id}"

    # Create the secret.
    secret = client.create_secret(
        request={
            "parent": parent,
            "secret_id": secret_id,
            "secret": {"replication": {"automatic": {}}},
        }
    )

    # Convert the string payload into a bytes. This step can be omitted if you
    # pass in bytes instead of a str for the payload argument.
    payload_bytes = payload.encode("UTF-8")

    # Calculate payload checksum. Passing a checksum in add-version request
    # is optional.
    crc32c = google_crc32c.Checksum()
    crc32c.update(payload_bytes)

    # Add the secret version.
    version = client.add_secret_version(
        request={
            "parent": secret.name, 
            "payload": {
                "data": payload_bytes,
                "data_crc32c": int(crc32c.hexdigest(), 16),
                }
            }
    )

def verifyGoogleToken(token):
    try:
        # Specify the CLIENT_ID of the app that accesses the backend:
        idinfo = verify_oauth2_token(token, requests.Request(), CLIENT_ID)

        if idinfo['hd'] != GSUITE_DOMAIN_NAME:
            return False

        if idinfo.get('email') != SERVICE_ACCT_EMAIL:
            return False
        
    except ValueError:
        # Invalid token
        return False
    except exceptions.GoogleAuthError:
        return False
    
    return True

def decodeUser(token):
    response = verify_oauth2_token(token, requests.Request(), CLIENT_ID)

    userId = response.get('sub')

    return userId

@lru_cache()
async def getFromGmailEmail(gevent: models.GEvent, creds: Credentials):
    
    with build('gmail', 'v1', credentials=creds) as gmailClient:
        messageToken = gevent.gmail.accessToken
        messageId = gevent.gmail.messageId

        acctEmail = await gmailClient.user().messages().get(
            userId='me', 
            id=messageId, 
            accessToken=messageToken, 
            format='metadata', 
            metadataHeaders='From') \
                .execute().get('payload').get('headers')[0].get('value')
        
    return acctEmail


@lru_cache()
def getUserKeys(creds: Credentials, userId: str):

    with build('people', 'v1', credentials=creds) as peopleClient:
        user = peopleClient.people().get(
            resourceName='people/me',
            personFields='names'
        )
        firstName = user.get('names')[0].get('givenName').lower()

    client = secretmanager.SecretManagerServiceClient()

    secret_id = firstName + userId

    name = f"projects/{GCLOUD_PROJECT_ID}/secrets/{secret_id}/versions/latest"
    try:
        secret = client.access_secret_version(request={"name": name})
    except:
        return createErrorResponseCard("Secret not found. Please enter your access keys in settings.")

    # Verify payload checksum.
    crc32c = google_crc32c.Checksum()
    crc32c.update(secret.payload.data)
    if secret.payload.data_crc32c != int(crc32c.hexdigest(), 16):
        return createErrorResponseCard("Checksum failed.")
    
    payload = secret.payload.data.decode("UTF-8")

    keys = json.loads(payload)

    return keys

#Creates a general error reponse card with inputed error text
def createErrorResponseCard(errorText: str):
    cardSection1TextParagraph1 = CardService.TextParagraph(text=errorText)

    cardSection1 = CardService.CardSection(widget=cardSection1TextParagraph1)

    card = CardService.CardBuilder(section=[cardSection1])

    responseCard = card.build()

    return responseCard

#Gets full Neon account from an email address
#Output fields:
#179 is WaiverDate
#182 is Facility Tour Date
def getNeonAcctByEmail(accountEmail: str, N_APIkey: str, N_APIuser: str) -> dict:
    searchFields = f'''
    [
        {{
            "field": "Email",
            "operator": "EQUAL",
            "value": "{accountEmail}"
        }}
    ]
    '''

    outputFields = f'''
    [
        "Account ID",
        "First Name",
        "Last Name",
        "Email 1",
        "Membership Start Date",
        182,
        179
    ]
    '''

    response = neon.postAccountSearch(searchFields, outputFields, N_APIkey, N_APIuser)

    searchResults = response.get("searchResults")

    return searchResults

#Pushes card to front of stack with Neon ID of account with associated email address, otherwise tell user there
#are no Neon accounts associated with that email
@app.post('/getNeonId')
async def getNeonId(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    try:
        creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
    except:
        errorText = "<b>Error:</b> Credentials not found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    apiKeys = getUserKeys(creds, userId)
    
    acctEmail = await getFromGmailEmail(gevent, creds)

    searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    if len(searchResult) == 1:
        accountName = searchResult[0]["First Name"] + \
            ' ' + searchResult[0]["Last Name"]
        accountID = searchResult[0]["Account ID"]

        cardSection1DecoratedText1 = CardService.DecoratedText(
            top_label=accountName,
            text=accountID,
            wrap_text=False
        )

        cardSection1 = CardService.CardSection(widget=cardSection1DecoratedText1)

        responseCard = CardService.CardBuilder(section=[cardSection1]).build()

        return responseCard
    elif len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    else:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

#Create the class home page and push to front of stack
@app.post('/classHomePage')
def classHomePage(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    nowInMs = int(time.time() * 1000)

    cardHeader1 = CardService.CardHeader(
        title="Classes",
        image_style=CardService.ImageStyle.CIRCLE
    )

    cardSection1TextInput1 = CardService.TextInput(
        field_name="className",
        title="Class Name",
        multiline=False,
    )

    cardSection1DatePicker1 = CardService.DatePicker(
        field_name = "startDate",
        title= "Start Date",
        value_in_ms_since_epoch = nowInMs
    )

    cardSection1DatePicker2 = CardService.DatePicker(
        field_name = "endDate",
        title= "End Date",
        value_in_ms_since_epoch = nowInMs
    )

    cardSection1ButtonList1Button1Action1 = CardService.Action(
        function_name = app.url_path_for('searchClasses'),
    )

    cardSection1ButtonList1Button1 = CardService.TextButton(
        text="Search",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action=cardSection1ButtonList1Button1Action1
    )
        
    cardSection1ButtonList1 = CardService.ButtonSet(
        button=cardSection1ButtonList1Button1
    )

    cardSection1 = CardService.CardSection(
        header="Add Registration",
        widget=cardSection1TextInput1,
        widget=cardSection1DatePicker1,
        widget=cardSection1DatePicker2,
        widget=cardSection1ButtonList1,
    )

    cardSection2DecoratedText1Icon1 = CardService.IconImage(
        icon=CardService.Icon.TICKET,
    )
        
    cardSection2DecoratedText1Button1Action1 = CardService.Action(
        function_name = app.url_path_for('getAcctRegClassCancel'),
    )

    cardSection2DecoratedText1Button1 = CardService.TextButton(
        text="Cancel",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action=cardSection2DecoratedText1Button1Action1
    )

    cardSection2DecoratedText1 = CardService.DecoratedText(
        text="Cancel a Registration",
        start_icon=cardSection2DecoratedText1Icon1,
        button=cardSection2DecoratedText1Button1,
    )

    cardSection2 = CardService.CardSection(
        widget=cardSection2DecoratedText1
    )

    cardSection3DecoratedText1Icon1 = CardService.IconImage(
        icon=CardService.Icon.DOLLAR,
    )

    cardSection3DecoratedText1Button1Action1 = CardService.Action(
        function_name = app.url_path_for('getAcctRegClassRefund'),
    )

    cardSection3DecoratedText1Button1 = CardService.TextButton(
        text="Refund",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action=cardSection3DecoratedText1Button1Action1
    )

    cardSection3DecoratedText1 = CardService.DecoratedText(
        text="Refund a Registration",
        start_icon=cardSection3DecoratedText1Icon1,
        button=cardSection3DecoratedText1Button1,
    )

    cardSection3 = CardService.CardSection(
        widget=cardSection3DecoratedText1
    )

    card = CardService.CardBuilder(
        header=cardHeader1,
        sections=[cardSection1, cardSection2, cardSection3],
        name = "classHomePage"
    )

    return card.build()

#Push a card to the front of the stack that has all future classes of the searched Event Name. If a date is picked, 
#only classes on that date will be returned.
#Every event is returned as its own widget with corresponding button. Clicking that button invokes /classReg to register 
#the account for that class
@app.post('/searchClasses')
def searchClasses(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    try:
        creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
    except:
        errorText = "<b>Error:</b> Credentials not found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    apiKeys = getUserKeys(creds, userId)
    
    if gevent.commonEventObject.formInputs["className"]["stringInputs"]["value"][0]:
        eventName = gevent.commonEventObject.formInputs["className"]["stringInputs"]["value"][0]
    else:
        errorText = "<b>Error:</b> Event name is required."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    if gevent.commonEventObject.formInputs["startDate"]["dateInput"]["msSinceEpoch"] and gevent.commonEventObject.formInputs["endDate"]["dateInput"]["msSinceEpoch"]:
        #This will give UTC time - need to convert to CST
        eventStartDateUTC = datetime.datetime.utcfromtimestamp(gevent.commonEventObject.formInputs["classDatePicker"]["dateInput"]["msSinceEpoch"])
        eventStartDate = eventStartDateUTC.astimezone(tz = pytz.timezone("America/Chicago")).isoformat()

        eventEndDateUTC = datetime.datetime.utcfromtimestamp(gevent.commonEventObject.formInputs["endDate"]["dateInput"]["msSinceEpoch"])
        eventEndDate = eventEndDateUTC.astimezone(tz = pytz.timezone("America/Chicago")).isoformat()

        searchFields = [
        {
            "field": "Event Name",
            "operator": "CONTAIN",
            "value": eventName
        },
        {
            "field": "Event Start Date",
            "operator": "GREATER_AND_EQUAL",
            "value": eventStartDate
        },
        {
            "field": "Event End Date",
            "operator": "LESS_AND_EQUAL",
            "value": eventEndDate
        }]
    
    elif gevent.commonEventObject.formInputs["startDate"]["dateInput"]["msSinceEpoch"]:
        eventStartDateUTC = datetime.datetime.utcfromtimestamp(gevent.commonEventObject.formInputs["startDate"]["dateInput"]["msSinceEpoch"])
        eventStartDate = eventStartDateUTC.astimezone(tz = pytz.timezone("America/Chicago")).isoformat()

        searchFields = [
        {
            "field": "Event Name",  
            "operator": "CONTAIN",
            "value": eventName
        },
        {
            "field": "Event Start Date",
            "operator": "GREATER_AND_EQUAL",
            "value": eventStartDate
        }
        ]

    elif gevent.commonEventObject.formInputs["endDate"]["dateInput"]["msSinceEpoch"]:
        eventEndDateUTC = datetime.datetime.utcfromtimestamp(gevent.commonEventObject.formInputs["endDate"]["dateInput"]["msSinceEpoch"])
        eventEndDate = eventEndDateUTC.astimezone(tz = pytz.timezone("America/Chicago")).isoformat()
        eventStartDate = datetime.date.today().isoformat()

        searchFields = [
        {
            "field": "Event Name",
            "operator": "CONTAIN",
            "value": eventName
        },
        {
            "field": "Event End Date",
            "operator": "LESS_AND_EQUAL",
            "value": eventEndDate
        },
        {
            "field": "Event Start Date",
            "operator": "GREATER_AND_EQUAL",
            "value": eventStartDate
        }
        ]
    else:
        eventStartDate = datetime.date.today().isoformat()

        searchFields = [
        {
            "field": "Event Name",
            "operator": "CONTAIN",
            "value": eventName
        },
        {
            "field": "Event Start Date",
            "operator": "GREATER_AND_EQUAL",
            "value": eventStartDate
        }]

    searchFields = json.dumps(searchFields)
    outputFields = [
        "Event ID",
        "Event Name",
        "Event Start Date",
        "Event Start Time"
    ]
    outputFields = json.dumps(outputFields)
    try:
        classResults = neon.postEventSearch(searchFields, outputFields, apiKeys["N_APIkey"], apiKeys["N_APIuser"])
    except:
        errorText = "<b>Error:</b> Unable to find classes. Check your authentication or use the Neon website."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    if len(classResults["searchResults"] > 0):
        responseCard = {
            "renderActions": {
                "action": {
                    "navigations": [
                        {
                            "pushCard": {
                                "sections": [
                                    {
                                        "collapsible": False,
                                        "uncollapsible_widgets_count": 1,
                                        "widgets": []
                                    }
                                ]
                            }
                        }]
                }
            }
        }
        for result in classResults["searchResults"]:
            newWidget = {
                            "decorated_text": {
                                "top_label": result["Event ID"],
                                "text": result["Event Name"],
                                "bottom_label": result["Event Start Date"],
                                "wrap_text": True,
                                "button": {
                                    "text": "Register",
                                    "on_click": {
                                        "action": {
                                            "function": app.url_path_for('classReg')
                                        }
                                    }
                                }
                            }
                        }

            responseCard["renderActions"]["action"]["navigations"][0]["pushCard"]["sections"][0]["widgets"].append(newWidget)
        return responseCard
    else:
        errorText = "No classes found. Check your spelling or try a different date."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    

#Registers the active gmail user for the selected class with a $0 price. Pulls the eventID from the bottom label of the
#previous card
@app.post('/classReg')
async def classReg(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    try:
        creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
    except:
        errorText = "<b>Error:</b> Credentials not found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    apiKeys = getUserKeys(creds, userId)
    
    acctEmail = await getFromGmailEmail(gevent, creds)

    searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    eventID = gevent.commonEventObject.formInputs.get('decorated_txt_top_label')

    if len(searchResult) == 0:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    elif len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    else:
        accountFirstName = searchResult[0]["First Name"]
        accountLastName = searchResult[0]["Last Name"]
        accountID = searchResult[0]["Account ID"]
        try:
            neon.postEventRegistration(accountID, eventID, accountFirstName, accountLastName)
        except:
            errorText = "<b>Error:</b> Registration failed. Use Neon to register individual."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
        
        cardSection1Paragraph1 = CardService.TextParagraph(text="<b>Successfully registered</b>")

        cardSection1 = CardService.CardSection(widget=cardSection1Paragraph1)

        card = CardService.CardBuilder(section=[cardSection1])

        responseCard = card.build()

        return responseCard
        

#Pushes card to front of stack showing all classes the user is currrently registered for. Each class is shown
# as its own widget with a corresponding button to cancel the registration for that class.
@app.post('/getAcctRegClassCancel')
def getAcctRegClassCancel(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    try:
        creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
    except:
        errorText = "<b>Error:</b> Credentials not found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    apiKeys = getUserKeys(creds, userId)
    
    acctEmail = getFromGmailEmail(gevent, creds)

    searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    if len(searchResult) == 1:
        neonID = searchResult[0]['Account ID']
        try:
            classDict = json.loads(neon.getAccountEventRegistrations(neonID, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER))
        except:
            errorText = "<b>Error:</b> Unable to find classes. Account may not have registered for any classes. Alternaively, check your authentication or use the Neon website."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
        today = datetime.datetime.today()
        upcomingClasses = []
        for event in classDict["eventRegistrations"]:
            registrationID = event["id"]
            eventID = event["eventId"]
            regStatus = event["tickets"][0]["attendees"][0]["registrationStatus"]
            eventInfo = neon.getEvent(eventID)
            eventDate = datetime.datetime.fromisoformat(eventInfo["eventDates"]["startDate"]).date()
            eventName = eventInfo["name"]
            if eventDate - today >= 0 and regStatus == "SUCCEEDED":
                upcomingClasses.append({"regID":registrationID, "eventID":eventID, "eventName":eventName, "startDate": eventInfo["eventDates"]["startDate"]})
        
        if not len(upcomingClasses):
            errorText = "No upcoming classes found."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
        
        widgets = []

        cardHeader1 = CardService.Header(
            title = "Cancel Classes",
            image_style = CardService.ImageStyle.CIRCLE,
        )

        iter = enumerate(upcomingClasses)
    
        for _, upcomingClass in iter:
            cardSection1DecoratedText1Button1Action1 = CardService.Action(
                function_name = app.url_path_for('classCancel'),
            )
            cardSection1DecoratedText1Button1 = CardService.TextButton(
                text = "Cancel",
                text_button_style=CardService.TextButtonStyle.TEXT,
                action = cardSection1DecoratedText1Button1Action1
            )
            cardSection1DecoratedText1 = CardService.DecoratedText(
                text = upcomingClass["eventName"],
                top_label = upcomingClass["regID"],
                buttom_label = upcomingClass["startDate"],
                wrap_text = True,
                button = cardSection1DecoratedText1Button1,
            )

            widgets.append(cardSection1DecoratedText1)

            if iter.__next__:
                cardSection1Divider1 = CardService.Divider()
                widgets.append(cardSection1Divider1)

        cardSection1 = CardService.CardSection(
            header = "Upcoming Classes",
            widgets = widgets,
        )            

        card = CardService.CardBuilder(
            header = cardHeader1,
            sections = [cardSection1],
            name = "cancelClassListCard"
        )

        return card.build()    
                
    elif len(searchResult) >1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    else:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    
#TODO:
#@app.post('/getAcctRegClassRefund')

#Cancels user's registration in class. RegistrationID for given registration is pulled from top label of widget on 
# /getAcctRegClassCancel card
@app.post('/classCancel')
def classCancel(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    regId = gevent.commonEventObject.formInputs.get('decorated_txt_top_label')
    className = gevent.commonEventObject.formInputs.get('decorated_txt')
    classDate = gevent.commonEventObject.formInputs.get('decorated_txt_bottom_label')

    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    os.environ[f"current_class_id_{userId}"] = regId

    cardSection1TextParagraph1 = CardService.TextParagraph(
        text = f"Are you sure you want to cancel the registration for {className} on {classDate}?"
    )

    cardSection1ButtonList1Button1Action1 = CardService.Action(
        function_name = app.url_path_for('classCancelConfirm'),
    )

    cardSection1ButtonList1Button1 = CardService.TextButton(
        text = "Yes",
        text_button_style=CardService.TextButtonStyle.TEXT,
        action = cardSection1ButtonList1Button1Action1
    )

    cardSection1ButtonList1Button2Action1 = CardService.Action(
        function_name = popCard(),
    )
    
    cardSection1ButtonList1Button2 = CardService.TextButton(
        text = "No",
        text_button_style=CardService.TextButtonStyle.TEXT,
        action = cardSection1ButtonList1Button2Action1
    )
    
    cardSection1ButtonList1 = CardService.ButtonSet(
        buttons = [cardSection1ButtonList1Button1, cardSection1ButtonList1Button2]
    )

    cardSection1 = CardService.CardSection(
        header = "Confirmation",
        widgets = [cardSection1TextParagraph1, cardSection1ButtonList1]
    )

    card = CardService.CardBuilder(
        section=[cardSection1],
        name = "classCancelCard"
    )

    return card.build()

@app.post('/classCancelConfirm')
def classCancelConfirm(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    try:
        creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
    except:
        errorText = "<b>Error:</b> Credentials not found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    userId = decodeUser(gevent.authorizationEventObject.userIdToken)
    
    regId = os.environ[f"current_class_id_{userId}"]

    apiKeys = getUserKeys(creds, userId)

    try:
        cancelResponse = neon.cancelClass(regId, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)
    except:
        errorText = "<b>Error:</b> Cancelation failed. Check your authentication or use the Neon website."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    if cancelResponse.status_code in range(200, 300):
        cardSection1TextParagraph1 = CardService.TextParagraph(
            text = f"Successfully canceled registration."
        )

        cardSection1ButtonList1Button1Action1 = CardService.Action(
            function_name = popToClassPage(),
        )

        cardSection1ButtonList1Button1 = CardService.TextButton(
            text = "Return to Class Page",
            text_button_style=CardService.TextButtonStyle.TEXT,
            action = cardSection1ButtonList1Button1Action1
        )

        cardSection1ButtonList1Button2Action1 = CardService.Action(
            function_name = popToHome(),
        )
        
        cardSection1ButtonList1Button2 = CardService.TextButton(
            text = "Return to Home Page",
            text_button_style=CardService.TextButtonStyle.TEXT,
            action = cardSection1ButtonList1Button2Action1
        )
        
        cardSection1ButtonList1 = CardService.ButtonSet(
            buttons = [cardSection1ButtonList1Button1, cardSection1ButtonList1Button2]
        )

        cardSection1 = CardService.CardSection(
            header = "Confirmed",
            widgets = [cardSection1TextParagraph1, cardSection1ButtonList1]
        )

        card = CardService.CardBuilder(
            section=[cardSection1],
            name = "classCancelConfirmationCard"
        )
 
        return card.build()
    else:
        errorText = f"<b>Error:</b> Cancelation failed with status code {cancelResponse.status_code}. Use Neon to cancel registration."
        responseCard = createErrorResponseCard(errorText)
        return responseCard



def popCard():

    popOneCard = CardService.Navigation().popCard()

    response = CardService.ActionResponseBuilder(
        navigation = popOneCard
    )

    return response


def popToClassPage():
    returnToClassPage = CardService.Navigation().popToNamedCard(
        card_name  = "classHomePage"
    )

    response = CardService.ActionResponseBuilder(
        navigation = returnToClassPage,
        state_changed = True
    )

    return response 


def popToHome():
    returnToHome = CardService.Navigation().popToRoot()

    response = CardService.ActionResponseBuilder(
        navigation = returnToHome,
        state_changed = True
    )

    return response

#@app.post('/classRefund')

@app.post('/checkAccess')
def checkAccess(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    try:
        creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
    except:
        errorText = "<b>Error:</b> Credentials not found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    apiKeys = getUserKeys(creds, userId)
    
    acctEmail = getFromGmailEmail(gevent, creds)

    searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    if len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    elif len(searchResult) == 0:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    neonID = searchResult[0]['Account ID']
    accountName = searchResult[0]["First Name"] + \
        ' ' + searchResult[0]["Last Name"]
    
    waiverBoolean = False
    if searchResult[0]['WaiverDate']:
        waiverBoolean = True

    orientBoolean = False
    if searchResult[0]['FacilityTourDate']:
        orientBoolean = True

    memBoolean = False
    if searchResult[0]['Membership Start Date']:
        memBoolean = True

    cardSection1SelectionInput1 = CardService.SelectionInput(
        field_name = "currentAccessRequirements",
        title = "Current Access Requirements",
        type = CardService.SelectionInputType.CHECK_BOX,
        item = [
            {
                "text": "Waiver",
                "value": "1",
                "selected": waiverBoolean
            },
            {
                "text": "Orientation/Facility Tour",
                "value": "2",
                "selected": orientBoolean
            },
            {
                "text": "Active Membership",
                "value": "3",
                "selected": memBoolean
            }
        ]
    )

    cardSection1 = CardService.CardSection(
        widget = cardSection1SelectionInput1,
        header = f"{accountName} - {neonID}"
    )

    card = CardService.CardBuilder(
        section=[cardSection1]
    )

    return card.build()

@app.post('/updateOP')
def updateOP(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    try:
        creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
    except:
        errorText = "<b>Error:</b> Credentials not found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    apiKeys = getUserKeys(creds, userId)
    
    acctEmail = getFromGmailEmail(gevent, creds)

    searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    if len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    elif len(searchResult) == 0:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    neonID = searchResult[0]['Account ID']

    if not searchResult[0]['WaiverDate'] or not searchResult[0]['FacilityTourDate'] or not searchResult[0]['Membership Start Date']:
        errorText = "Account has not completed all access requirements. Use the Check Access button to find out what's missing."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    openPathUpdateSingle(neonID)

    cardSection1TextParagraph1 = CardService.TextParagraph(
        text = "Account Openpath has been updated."
    )

    cardSection1 = CardService.CardSection(
        widgets = [cardSection1TextParagraph1]
    )

    card = CardService.CardBuilder(
        section=[cardSection1]
    )

    responseCard = card.build()

    return responseCard

@app.post('/settings')
def settings(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    cardSection1TextInput1 = CardService.TextInput(
        field_name = "neonAPIKey",
        title = "Neon API Key",
        multiline = False
    )

    cardSection1TextInput2 = CardService.TextInput(
        field_name = "openPathAPIUser",
        title = "OpenPath API User",
        multiline = False
    )

    cardSection1TextInput3 = CardService.TextInput(
        field_name = "openPathAPIKey",
        title = "Openpath API Key",
        multiline = False
    )

    cardSection1ButtonList1Button1Action1 = CardService.Action(
        function_name = app.url_path_for('submitSettings')
    )

    cardSection1ButtonList1Button1 = CardService.TextButton(
        text = "Submit",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList1Button1Action1
    )

    cardSection1ButtonList1 = CardService.ButtonSet(
        button = [cardSection1ButtonList1Button1]
    )

    cardSection1 = CardService.CardSection(
        widgets = [cardSection1TextInput1, cardSection1TextInput2, cardSection1TextInput3, cardSection1ButtonList1],
        header = "API Keys"
    )

    card = CardService.CardBuilder(
        section = [cardSection1]
    )

    responseCard = card.build()

    return responseCard

@app.post('/submitSettings')
def submitSettings(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    try:
        creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
    except:
        errorText = "<b>Error:</b> Credentials not found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    with build('people', 'v1', credentials=creds) as peopleClient:
        user = peopleClient.people().get(
            resourceName='people/me',
            personFields='names'
        )
        firstName = user.get('names')[0].get('givenName').lower()
    
    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    neonAPIKey = gevent.commonEventObject.formInputs.get('neonAPIKey')
    openPathAPIUser = gevent.commonEventObject.formInputs.get('openPathAPIUser')
    openPathAPIKey = gevent.commonEventObject.formInputs.get('openPathAPIKey')

    # Take submitted API info, create a json object with it, and submit to Google Secret Manager
    # as a new secret, or secret version if the secret already exists. If the secret already exists,
    # delete the old secret version.

    newSecretVersion = {
        "N_APIkey": neonAPIKey,
        "O_APIuser": openPathAPIUser,
        "O_APIkey": openPathAPIKey,
    }

    jsonSecretVersion = json.dumps(newSecretVersion)

    client = secretmanager.SecretManagerServiceClient()

    secret_id = firstName + userId

    name = f"projects/{GCLOUD_PROJECT_ID}/secrets/{secret_id}/versions/latest"

    try:
        secret = client.access_secret_version(request={"name": name})

        # Verify payload checksum.
        crc32c = google_crc32c.Checksum()
        crc32c.update(secret.payload.data)
        if secret.payload.data_crc32c != int(crc32c.hexdigest(), 16):
            return createErrorResponseCard("Checksum failed.")
        currentSecret = True
    except:
        currentSecret = False

    if currentSecret:
        path = client.secret_path(GCLOUD_PROJECT_ID, secret_id)

        client.delete_secret(request={"name": path})
        
    create_secret(client, GCLOUD_PROJECT_ID, secret_id, jsonSecretVersion)

    cardSection1TextParagraph1 = CardService.TextParagraph(
        text = "API Keys Updated."
    )

    cardSection1 = CardService.CardSection(
        widgets = [cardSection1TextParagraph1]
    )

    card = CardService.CardBuilder(
        section=[cardSection1]
    )

    responseCard = card.build()

    return responseCard

#@app.post('/contextualHome')

#@app.post('/home')

