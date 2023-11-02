from openPathUpdateSingle import openPathUpdateSingle
from helpers import neon

import httpx
import json
import datetime
import os
import time
import pytz
import uvicorn
import re
import neonUtil

from fastapi import FastAPI
from functools import lru_cache

from gapps import cardservice as CardService
from gapps.cardservice import models
from gapps.cardservice import utilities
from gapps.cardservice.api import SelectionItem

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

dev = False

if dev:
    BASE_URL = os.environ.get('BASE_URL')
    GCLOUD_PROJECT_ID = "gmail-neon-op-integration"

    client = secretmanager.SecretManagerServiceClient()

    secret_id = "static_keys"

    static_keys = None
    if keys := os.environ.get("secret_id", None):
        static_keys = json.loads(keys)

    if not isinstance(static_keys, dict):

        name = f"projects/{GCLOUD_PROJECT_ID}/secrets/{secret_id}/versions/latest"

        secret = client.access_secret_version(request={"name": name})

        # Verify payload checksum.
        crc32c = google_crc32c.Checksum()
        crc32c.update(secret.payload.data)
        if secret.payload.data_crc32c != int(crc32c.hexdigest(), 16):
            raise Exception("Checksum failed.")
        
        payload = secret.payload.data.decode("UTF-8")

        static_keys = json.loads(payload)

    os.environ["static_keys"] = payload

else:
    static_keys = json.loads(os.environ.get('static_keys'))
    BASE_URL = static_keys.get("base_url")

GCLOUD_PROJECT_ID = static_keys.get("project_id")
CLIENT_ID = static_keys.get("client_id")
GSUITE_DOMAIN_NAME = static_keys.get("gsuite_domain")
SERVICE_ACCT_EMAIL = static_keys.get("service_acct_email")
NEON_API_USER = static_keys.get("N_APIuser")
G_USER = static_keys.get("G_user")
G_PASS = static_keys.get("G_password")

def create_secret(client: secretmanager.SecretManagerServiceClient, 
                  project_id: str, 
                  secret_id: str, 
                  payload: str) -> secretmanager.CreateSecretRequest:
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
        # TODO: add Cloud Run client ID as audience of verify function when deployed to Cloud Run
        idinfo = verify_oauth2_token(token, requests.Request())

        if idinfo.get('email') != SERVICE_ACCT_EMAIL:
            return False
        
    except ValueError:
        # Invalid token
        return False
    except exceptions.GoogleAuthError:
        return False

    return True

def decodeUser(token):
    # TODO: add Cloud Run client ID as audience of verify function when deployed to Cloud Run
    response = verify_oauth2_token(token, requests.Request())

    userId = response.get('sub')

    return userId


def getFromGmailEmail(gevent: models.GEvent, creds: Credentials):
    
    with build('gmail', 'v1', credentials=creds) as gmailClient:
        messageToken = gevent.gmail.accessToken
        messageId = gevent.gmail.messageId

        acctEmail = gmailClient.users().messages().get(
            userId='me', 
            id=messageId, 
            #accessToken=messageToken, 
            format='metadata', 
            metadataHeaders='From') \
                .execute().get('payload').get('headers')[0].get('value')
    

    email = re.search("<(.*?)>", acctEmail).group(1)
    return email


@lru_cache()
def getUserKeys(creds: Credentials, userId: str):

    with build('people', 'v1', credentials=creds) as peopleClient:
        user = peopleClient.people().get(
            resourceName='people/me',
            personFields='names'
        ).execute()
    firstName = user.get('names')[0].get('givenName').lower()

    secret_id = firstName + '_' + userId

    if keys := os.environ.get("secret_id", None):
        return json.loads(keys)

    client = secretmanager.SecretManagerServiceClient()

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

    os.environ["secret_id"] = json.dumps(keys)

    return keys

#Creates a general error reponse card with inputed error text
def createErrorResponseCard(errorText: str):
    cardSection1TextParagraph1 = CardService.TextParagraph(text=errorText)

    cardSection1 = CardService.CardSection(widget=[cardSection1TextParagraph1])

    card = CardService.CardBuilder(section=[cardSection1])

    responseCard = card.build()

    nav = CardService.Navigation().pushCard(responseCard)

    navAction = CardService.ActionResponseBuilder(
        navigation = nav
    ).build()

    return navAction

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
    if not apiKeys.get("N_APIkey"):
        return apiKeys

    acctEmail = getFromGmailEmail(gevent, creds)

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

        cardSection1 = CardService.CardSection(widget=[cardSection1DecoratedText1])

        responseCard = CardService.CardBuilder(section=[cardSection1]).build()

        return {"renderActions": responseCard}
    elif len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. \
            Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
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
        title="Account Classes Home",
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
        function_name = BASE_URL + app.url_path_for('searchClasses'),
    )

    cardSection1ButtonList1Button1 = CardService.TextButton(
        text="Search",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action=cardSection1ButtonList1Button1Action1
    )
        
    cardSection1ButtonList1 = CardService.ButtonSet(
        button=[cardSection1ButtonList1Button1]
    )

    cardSection1 = CardService.CardSection(
        header="Add Registration",
        widget=[cardSection1TextInput1, 
                cardSection1DatePicker1, 
                cardSection1DatePicker2, 
                cardSection1ButtonList1
                ],
    )
        
    cardSection2DecoratedText1Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('getAcctRegClassRefund'),
    )

    cardSection2DecoratedText1 = CardService.DecoratedText(
        text="Cancel and refund a registration",
        on_click_action=cardSection2DecoratedText1Button1Action1,
    )

    cardSection2 = CardService.CardSection(
        widget=[cardSection2DecoratedText1]
    )

    card = CardService.CardBuilder(
        header=cardHeader1,
        section=[cardSection1, cardSection2],
        name = "classHomePage"
    )

    responseCard = card.build()

    responseCard["action"]["navigations"][0]["pushCard"]["sections"][1]["widgets"][0]["decoratedText"]["startIcon"] = \
        {"knownIcon": "DOLLAR"}
    responseCard["action"]["navigations"][0]["pushCard"]["sections"][1]["widgets"][0]["horizontalAlignment"] = "CENTER"
    
    return {"renderActions":responseCard}

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
    if not apiKeys.get("N_APIkey"):
        return apiKeys

    if gevent.commonEventObject.formInputs["className"]["stringInputs"]["value"][0]:
        eventName = gevent.commonEventObject.formInputs["className"]["stringInputs"]["value"][0]
    else:
        errorText = "<b>Error:</b> Event name is required."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    if gevent.commonEventObject.formInputs["startDate"]["dateInput"]["msSinceEpoch"] and \
        gevent.commonEventObject.formInputs["endDate"]["dateInput"]["msSinceEpoch"]:
        #This will give UTC time - need to convert to CST
        eventStartDateUTC = datetime.datetime.utcfromtimestamp(
            gevent.commonEventObject.formInputs["startDate"]["dateInput"]["msSinceEpoch"]/1000
            )
        eventStartDate = eventStartDateUTC.date().isoformat()

        eventEndDateUTC = datetime.datetime.utcfromtimestamp(
            gevent.commonEventObject.formInputs["endDate"]["dateInput"]["msSinceEpoch"]/1000
            )
        eventEndDate = eventEndDateUTC.date().isoformat()

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
        eventStartDateUTC = datetime.datetime.utcfromtimestamp(
            gevent.commonEventObject.formInputs["startDate"]["dateInput"]["msSinceEpoch"]/1000
            )
        eventStartDate = eventStartDateUTC.date().isoformat()

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
        eventEndDateUTC = datetime.datetime.utcfromtimestamp(
            gevent.commonEventObject.formInputs["endDate"]["dateInput"]["msSinceEpoch"]/1000
            )
        eventEndDate = eventEndDateUTC.date().isoformat()
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
        "Event Start Time",
        "Event Capacity",
        "Registrants"
    ]
    outputFields = json.dumps(outputFields)
    try:
        classResults = neon.postEventSearch(searchFields, outputFields, apiKeys["N_APIkey"], NEON_API_USER)
    except:
        errorText = "<b>Error:</b> Unable to find classes. Check your authentication or use the Neon website."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    if len(classResults["searchResults"]) > 0:
        classes = classResults["searchResults"]
        classes.sort(key=lambda x: x["Event Start Date"])
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
                                        "widgets": [],
                                        "header": "Upcoming Classes"
                                    }
                                ]
                            }
                        }]
                }
            }
        }
        for result in classes:
            maxAttendees = result["Event Capacity"]
            event = neon.getEventRegistrants(result['Event ID'], apiKeys["N_APIkey"], NEON_API_USER)
            currentAttendees = neon.getEventRegistrantCount(event["eventRegistrations"])
            disabled = False
            text = "Register"
            if int(currentAttendees) == int(maxAttendees):
                disabled = True
                text = "Full"
            newWidget = {
                            "decorated_text": {
                                "top_label": result["Event ID"],
                                "text": f"{result['Event Name']} ({currentAttendees}/{maxAttendees})",
                                "bottom_label": result["Event Start Date"],
                                "wrap_text": True,
                                "button": {
                                    "text": text,
                                    "on_click": {
                                        "action": {
                                            "function": BASE_URL + app.url_path_for('classReg'),
                                            "parameters": [{
                                                "key": "eventID",
                                                "value": result["Event ID"]
                                        }]
                                        }
                                    },
                                    "disabled": disabled
                                }
                            }
                        }

            responseCard["renderActions"]["action"]["navigations"][0] \
                ["pushCard"]["sections"][0]["widgets"].append(newWidget)
        return responseCard
    else:
        errorText = "No classes found. Check your spelling or try a different date."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    

# Registers the active gmail user for the selected class with a $0 price. Pulls the eventID from the bottom label of the
# previous card
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
    if not apiKeys.get("N_APIkey"):
        return apiKeys

    acctEmail = getFromGmailEmail(gevent, creds)

    searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    eventID = gevent.commonEventObject.parameters.get('eventID')

    if len(searchResult) == 0:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    elif len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. \
            Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    accountFirstName = searchResult[0]["First Name"]
    accountLastName = searchResult[0]["Last Name"]
    accountID = searchResult[0]["Account ID"]

    try:
        neon.postEventRegistration(accountID, 
                                   eventID, 
                                   accountFirstName, 
                                   accountLastName, 
                                   N_APIkey=apiKeys['N_APIkey'], 
                                   N_APIuser=NEON_API_USER
                                   )
    except:
        errorText = "<b>Error:</b> Registration failed. Use Neon to register individual."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    cardSection1Paragraph1 = CardService.TextParagraph(text="<b>Successfully registered</b>")

    cardSection1 = CardService.CardSection(widget=[cardSection1Paragraph1])

    card = CardService.CardBuilder(section=[cardSection1])

    responseCard = card.build()

    return {"renderActions": responseCard}
    

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
    if not apiKeys.get("N_APIkey"):
        return apiKeys

    acctEmail = getFromGmailEmail(gevent, creds)

    searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    if len(searchResult) == 1:
        neonID = searchResult[0]['Account ID']
        try:
            classDict = neon.getAccountEventRegistrations(neonID, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)
        except:
            errorText = "<b>Error:</b> Unable to find classes. Account may not have registered for any classes. \
                Alternaively, check your authentication or use the Neon website."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
        today = datetime.date.today()
        upcomingClasses = []
        for event in classDict["eventRegistrations"]:
            registrationID = event["id"]
            eventID = event["eventId"]
            regStatus = event["tickets"][0]["attendees"][0]["registrationStatus"]
            eventInfo = neon.getEvent(eventID, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)
            eventDate = datetime.datetime.fromisoformat(eventInfo["eventDates"]["startDate"]).date()
            eventName = eventInfo["name"]
            if eventDate - today >= datetime.timedelta(days=0) and regStatus == "SUCCEEDED":
                upcomingClasses.append({"regID":registrationID, 
                                        "eventID":eventID, 
                                        "eventName":eventName, 
                                        "startDate": eventInfo["eventDates"]["startDate"]
                                        })
        
        if not len(upcomingClasses):
            errorText = "No upcoming classes found."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
        
        temp_widgets = []

        cardHeader1 = CardService.CardHeader(
            title = "Cancel Classes"
        )

        iter = enumerate(upcomingClasses)
    
        for _, upcomingClass in iter:
            cardSection1DecoratedText1Button1Action1 = CardService.Action(
                function_name = BASE_URL + app.url_path_for('classCancel'),
                parameters = {
                    "regID": upcomingClass["regID"],
                    "eventID": upcomingClass["eventID"],
                    "startDate": upcomingClass["startDate"],
                    "eventName": upcomingClass["eventName"],
                    "neonID": neonID
                }
            )
            cardSection1DecoratedText1Button1 = CardService.TextButton(
                text = "Cancel",
                text_button_style=CardService.TextButtonStyle.TEXT,
                on_click_action = cardSection1DecoratedText1Button1Action1
            )
            cardSection1DecoratedText1 = CardService.DecoratedText(
                text = upcomingClass["eventName"],
                top_label = upcomingClass["regID"],
                bottom_label = upcomingClass["startDate"],
                wrap_text = True,
                button = cardSection1DecoratedText1Button1
            )

            temp_widgets.append(cardSection1DecoratedText1)

            if iter.__next__:
                cardSection1Divider1 = CardService.Divider()
                temp_widgets.append(cardSection1Divider1)

        cardSection1 = CardService.CardSection(
            header = "Upcoming Classes",
            widget = temp_widgets,
        )            

        card = CardService.CardBuilder(
            header = cardHeader1,
            section = [cardSection1],
            name = "cancelClassListCard"
        )

        responseCard = card.build()

        return {"renderActions": responseCard} 
                
    elif len(searchResult) >1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. \
            Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    else:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
@app.post('/getAcctRegClassRefund')
def getAcctRegClassRefund(gevent: models.GEvent):
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
    if not apiKeys.get("N_APIkey"):
        return apiKeys

    acctEmail = getFromGmailEmail(gevent, creds)

    searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    if len(searchResult) == 1:
        neonID = searchResult[0]['Account ID']
        try:
            classDict = neon.getAccountEventRegistrations(neonID, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)
        except:
            errorText = "<b>Error:</b> Unable to find classes. Account may not have registered for any classes. \
                Alternaively, check your authentication or use the Neon website."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
        today = datetime.date.today()
        upcomingClasses = []
        for event in classDict["eventRegistrations"]:
            registrationID = event["id"]
            eventID = event["eventId"]
            regStatus = event["tickets"][0]["attendees"][0]["registrationStatus"]
            eventInfo = neon.getEvent(eventID, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)
            eventDate = datetime.datetime.fromisoformat(eventInfo["eventDates"]["startDate"]).date()
            eventName = eventInfo["name"]
            if eventDate - today >= datetime.timedelta(days=0) and regStatus == "SUCCEEDED":
                upcomingClasses.append({"regID":registrationID, 
                                        "eventID":eventID, 
                                        "eventName":eventName, 
                                        "startDate": eventInfo["eventDates"]["startDate"]
                                        })
        
        if not len(upcomingClasses):
            errorText = "No upcoming classes found."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
        
        upcomingClasses.sort(key=lambda x: x["startDate"])
        
        temp_widgets = []

        cardHeader1 = CardService.CardHeader(
            title = "Cancel and Refund Classes"
        )

        iter = enumerate(upcomingClasses)
    
        for _, upcomingClass in iter:
            cardSection1DecoratedText1Button1Action1 = CardService.Action(
                function_name = BASE_URL + app.url_path_for('classRefund'),
                parameters = {
                    "regID": upcomingClass["regID"],
                    "eventID": upcomingClass["eventID"],
                    "startDate": upcomingClass["startDate"],
                    "eventName": upcomingClass["eventName"],
                    "neonID": neonID
                }
            )
            cardSection1DecoratedText1Button1 = CardService.TextButton(
                text = "Refund",
                text_button_style=CardService.TextButtonStyle.TEXT,
                on_click_action = cardSection1DecoratedText1Button1Action1
            )
            cardSection1DecoratedText1 = CardService.DecoratedText(
                text = upcomingClass["eventName"],
                top_label = upcomingClass["regID"],
                bottom_label = upcomingClass["startDate"],
                wrap_text = True,
                button = cardSection1DecoratedText1Button1
            )

            temp_widgets.append(cardSection1DecoratedText1)

            if iter.__next__:
                cardSection1Divider1 = CardService.Divider()
                temp_widgets.append(cardSection1Divider1)

        cardSection1 = CardService.CardSection(
            header = "Upcoming Classes",
            widget = temp_widgets,
        )            

        card = CardService.CardBuilder(
            header = cardHeader1,
            section = [cardSection1],
            name = "refundClassListCard"
        )

        responseCard = card.build()

        return {"renderActions": responseCard} 
                
    elif len(searchResult) >1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. \
            Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    else:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

#Cancels user's registration in class. 
@app.post('/classCancel')
def classCancel(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    regId = gevent.commonEventObject.parameters.get('regID')
    eventID = gevent.commonEventObject.parameters.get('eventID')
    className = gevent.commonEventObject.parameters.get('eventName')
    classDate = gevent.commonEventObject.parameters.get('startDate')
    neonId = gevent.commonEventObject.parameters.get('neonID')

    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    cardSection1TextParagraph1 = CardService.TextParagraph(
        text = f"Are you sure you want to cancel the registration for {className} on {classDate}?"
    )

    cardSection1ButtonList1Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('classCancelConfirm'),
        parameters = {
            "regID": regId,
            "eventID": eventID,
            "neonID": neonId
        }
    )

    cardSection1ButtonList1Button1 = CardService.TextButton(
        text = "Yes",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList1Button1Action1
    )

    cardSection1ButtonList1Button2Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('popCard'),
    )
    
    cardSection1ButtonList1Button2 = CardService.TextButton(
        text = "No",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList1Button2Action1
    )
    
    cardSection1ButtonList1 = CardService.ButtonSet(
        button = [cardSection1ButtonList1Button1, cardSection1ButtonList1Button2]
    )

    cardSection1 = CardService.CardSection(
        header = "Confirmation",
        widget = [cardSection1TextParagraph1, cardSection1ButtonList1]
    )

    card = CardService.CardBuilder(
        section=[cardSection1],
        name = "classCancelCard"
    )

    responseCard = card.build()

    return {"renderActions": responseCard}

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
    
    #regId = os.environ[f"current_class_id_{userId}"]
    regId = gevent.commonEventObject.parameters.get('regID')
    eventID = gevent.commonEventObject.parameters.get('eventID')
    neonId = gevent.commonEventObject.parameters.get('neonID')

    apiKeys = getUserKeys(creds, userId)
    if not apiKeys.get("N_APIkey"):
        return apiKeys

    try:
        cancelResponse = neon.cancelClass(regId, 
                                          eventId = eventID, 
                                          neonId = neonId, 
                                          N_APIkey=apiKeys['N_APIkey'], 
                                          N_APIuser=NEON_API_USER
                                          )
    except:
        errorText = "<b>Error:</b> Cancelation failed. Check your authentication or use the Neon website."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    if cancelResponse.status_code in range(200, 300):
        cardSection1TextParagraph1 = CardService.TextParagraph(
            text = f"Successfully canceled registration."
        )

        cardSection1ButtonList1Button1Action1 = CardService.Action(
            function_name = BASE_URL + app.url_path_for('popToClassPage'),
        )

        cardSection1ButtonList1Button1 = CardService.TextButton(
            text = "Return to Class Page",
            text_button_style=CardService.TextButtonStyle.TEXT,
            on_click_action = cardSection1ButtonList1Button1Action1
        )

        cardSection1ButtonList1Button2Action1 = CardService.Action(
            function_name = BASE_URL + app.url_path_for('popToHome'),
        )
        
        cardSection1ButtonList1Button2 = CardService.TextButton(
            text = "Return to Home Page",
            text_button_style=CardService.TextButtonStyle.TEXT,
            on_click_action = cardSection1ButtonList1Button2Action1
        )
        
        cardSection1ButtonList1 = CardService.ButtonSet(
            button = [cardSection1ButtonList1Button1, cardSection1ButtonList1Button2]
        )

        cardSection1 = CardService.CardSection(
            header = "Confirmed",
            widget = [cardSection1TextParagraph1, cardSection1ButtonList1]
        )

        card = CardService.CardBuilder(
            section=[cardSection1],
            name = "classCancelConfirmationCard"
        )

        responseCard = card.build()
 
        return {"renderActions": responseCard}
    else:
        errorText = f"<b>Error:</b> Cancelation failed with status code {cancelResponse.status_code}. \
            Use Neon to cancel registration."
        responseCard = createErrorResponseCard(errorText)
        return responseCard


@app.post('/popCard')
def popCard():

    popOneCard = CardService.Navigation().popCard()

    response = CardService.ActionResponseBuilder(
        navigation = popOneCard
    )

    return response.build()

@app.post('/popToClassPage')
def popToClassPage():
    returnToClassPage = CardService.Navigation().popToNamedCard(
        card_name  = "classHomePage"
    )

    response = CardService.ActionResponseBuilder(
        navigation = returnToClassPage,
        state_changed = True
    )

    return response.build()

@app.post('/popToHome')
def popToHome():
    returnToHome = CardService.Navigation().popToRoot()

    response = CardService.ActionResponseBuilder(
        navigation = returnToHome,
        state_changed = True
    )

    return response.build()

@app.post('/classRefund')
def classRefund(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    regId = gevent.commonEventObject.parameters.get('regID')
    eventID = gevent.commonEventObject.parameters.get('eventID')
    className = gevent.commonEventObject.parameters.get('eventName')
    classDate = gevent.commonEventObject.parameters.get('startDate')
    neonId = gevent.commonEventObject.parameters.get('neonID')

    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    cardSection1TextParagraph1 = CardService.TextParagraph(
        text = f"Are you sure you want to cancel the registration for {className} on {classDate} and issue a refund?"
    )

    cardSection1ButtonList1Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('classRefundConfirm'),
        parameters = {
            "regID": regId,
            "eventID": eventID,
            "neonID": neonId
        }
    )

    cardSection1ButtonList1Button1 = CardService.TextButton(
        text = "Yes",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList1Button1Action1
    )

    cardSection1ButtonList1Button2Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('popCard'),
    )
    
    cardSection1ButtonList1Button2 = CardService.TextButton(
        text = "No",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList1Button2Action1
    )
    
    cardSection1ButtonList1 = CardService.ButtonSet(
        button = [cardSection1ButtonList1Button1, cardSection1ButtonList1Button2]
    )

    cardSection1 = CardService.CardSection(
        header = "Confirmation",
        widget = [cardSection1TextParagraph1, cardSection1ButtonList1]
    )

    card = CardService.CardBuilder(
        section=[cardSection1],
        name = "classRefundCard"
    )

    responseCard = card.build()

    return {"renderActions": responseCard}

@app.post('/classRefundConfirm')
def classRefundConfirm(gevent: models.GEvent):
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
    
    regId = gevent.commonEventObject.parameters.get('regID')
    eventID = gevent.commonEventObject.parameters.get('eventID')
    neonId = gevent.commonEventObject.parameters.get('neonID')

    apiKeys = getUserKeys(creds, userId)
    if not apiKeys.get("N_APIkey"):
        return apiKeys

    try:
        cancelResponse = neon.refundClass(eventId = eventID, 
                                          neonId = neonId, 
                                          N_APIkey=apiKeys['N_APIkey'], 
                                          N_APIuser=NEON_API_USER
                                          )
    except:
        errorText = "<b>Error:</b> Cancellation failed. Check your authentication or use the Neon website."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    if cancelResponse.status_code in range(200, 300):
        cardSection1TextParagraph1 = CardService.TextParagraph(
            text = f"Successfully cancelled and refunded registration."
        )

        cardSection1ButtonList1Button1Action1 = CardService.Action(
            function_name = BASE_URL + app.url_path_for('popToClassPage'),
        )

        cardSection1ButtonList1Button1 = CardService.TextButton(
            text = "Return to Class Page",
            text_button_style=CardService.TextButtonStyle.TEXT,
            on_click_action = cardSection1ButtonList1Button1Action1
        )

        cardSection1ButtonList1Button2Action1 = CardService.Action(
            function_name = BASE_URL + app.url_path_for('popToHome'),
        )
        
        cardSection1ButtonList1Button2 = CardService.TextButton(
            text = "Return to Home Page",
            text_button_style=CardService.TextButtonStyle.TEXT,
            on_click_action = cardSection1ButtonList1Button2Action1
        )
        
        cardSection1ButtonList1 = CardService.ButtonSet(
            button = [cardSection1ButtonList1Button1, cardSection1ButtonList1Button2]
        )

        cardSection1 = CardService.CardSection(
            header = "Confirmed",
            widget = [cardSection1TextParagraph1, cardSection1ButtonList1]
        )

        card = CardService.CardBuilder(
            section=[cardSection1],
            name = "classRefundConfirmationCard"
        )

        responseCard = card.build()
 
        return {"renderActions": responseCard}
    else:
        errorText = f"<b>Error:</b> Cancellation failed with status code {cancelResponse.status_code}. \
            Use Neon to cancel registration."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

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
    if not apiKeys.get("N_APIkey"):
        return apiKeys

    waiverBoolean = False
    orientBoolean = False
    memBoolean = False
    searchResult = None

    if isinstance(gevent.commonEventObject.formInputs.get('checkAccess'), dict) and \
        gevent.commonEventObject.formInputs.get('checkAccess').get('stringInputs').get('value')[0]:
        input = gevent.commonEventObject.formInputs.get('checkAccess').get('stringInputs').get('value')[0]
        if input.isdigit():
            neonID = int(input)
            acct = neonUtil.getMemberById(neonID, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)
            if acct.get('WaiverDate'):
                waiverBoolean = True
            if acct.get('FacilityTourDate'):
                orientBoolean = True
            if acct.get('Membership Start Date'):
                memBoolean = True
            accountName = acct["fullName"]
        else:
            searchResult = getNeonAcctByEmail(input, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    else:
        acctEmail = getFromGmailEmail(gevent, creds)
        searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)


    if searchResult is not None:

        if len(searchResult) > 1:
            errorText = "<b>Error:</b> Multiple Neon accounts found. \
                Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
        elif len(searchResult) == 0:
            errorText = "<b>Error:</b> No Neon accounts found."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
    
        neonID = searchResult[0]['Account ID']
        accountName = searchResult[0]["First Name"] + \
            ' ' + searchResult[0]["Last Name"]
        
        if searchResult[0]['WaiverDate']:
            waiverBoolean = True

        if searchResult[0]['FacilityTourDate']:
            orientBoolean = True

        if searchResult[0]['Membership Start Date']:
            memBoolean = True

    cardSection1SelectionInput1Selection1 = SelectionItem(
        text = "Waiver",
        value = "1",
        selected = waiverBoolean
    )

    cardSection1SelectionInput1Selection2 = SelectionItem(
        text = "Orientation/Facility Tour",
        value = "2",
        selected = orientBoolean
    )

    cardSection1SelectionInput1Selection3 = SelectionItem(
        text = "Active Membership",
        value = "3",
        selected = memBoolean
    )

    cardSection1SelectionInput1 = CardService.SelectionInput(
        field_name = "currentAccessRequirements",
        title = "Current Access Requirements",
        type = CardService.SelectionInputType.CHECK_BOX,
        item = [cardSection1SelectionInput1Selection1, 
                cardSection1SelectionInput1Selection2, 
                cardSection1SelectionInput1Selection3
                ]
    )

    cardSection1 = CardService.CardSection(
        widget = [cardSection1SelectionInput1],
        header = f"{accountName} - {neonID}"
    )

    card = CardService.CardBuilder(
        section=[cardSection1]
    )

    responseCard = card.build()

    return {"renderActions": responseCard}

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
    if not apiKeys.get("N_APIkey") or not apiKeys.get("O_APIkey") or not apiKeys.get("O_APIuser"):
        return apiKeys

    cardSection1TextParagraph1 = CardService.TextParagraph(
        text = "Account Openpath has been updated."
    )

    cardSection1 = CardService.CardSection(
        widget = [cardSection1TextParagraph1]
    )

    card = CardService.CardBuilder(
        section=[cardSection1]
    )

    builtCard = card.build()

    nav = CardService.Navigation().pushCard(builtCard)

    navAction = CardService.ActionResponseBuilder(
        navigation = nav
    )

    responseCard = navAction.build()

    if isinstance(gevent.commonEventObject.formInputs.get('updateOpenpath'), dict) and \
        gevent.commonEventObject.formInputs.get('updateOpenpath').get('stringInputs').get('value')[0]:
        input = gevent.commonEventObject.formInputs.get('updateOpenpath').get('stringInputs').get('value')[0]
        if input.isdigit():
            acct = neonUtil.getMemberById(int(input), N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)
            if not acct.get('WaiverDate') or not acct.get('FacilityTourDate') or not acct.get('Membership Start Date'):
                errorText = "Account has not completed all access requirements. \
                    Use the Check Access button to find out what's missing."
                responseCard = createErrorResponseCard(errorText)
                return responseCard
            openPathUpdateSingle(int(input), 
                                 N_APIkey=apiKeys['N_APIkey'], 
                                 N_APIuser=NEON_API_USER, 
                                 O_APIkey=apiKeys['O_APIkey'], 
                                 O_APIuser=apiKeys['O_APIuser'], 
                                 G_user=G_USER, 
                                 G_pass=G_PASS
                                 )
            return responseCard

        else:
            searchResult = getNeonAcctByEmail(input, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    else:
        acctEmail = getFromGmailEmail(gevent, creds)
        searchResult = getNeonAcctByEmail(acctEmail, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    if len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. \
            Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    elif len(searchResult) == 0:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    neonID = searchResult[0]['Account ID']

    if not searchResult[0]['WaiverDate'] or not searchResult[0]['FacilityTourDate'] or not \
        searchResult[0]['Membership Start Date']:
        errorText = "Account has not completed all access requirements. \
            Use the Check Access button to find out what's missing."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    openPathUpdateSingle(neonID, 
                         N_APIkey=apiKeys['N_APIkey'], 
                         N_APIuser=NEON_API_USER, 
                         O_APIkey=apiKeys['O_APIkey'], 
                         O_APIuser=apiKeys['O_APIuser'], 
                         G_user=G_USER, 
                         G_pass=G_PASS
                         )

    return responseCard

@app.post('/giftCertSearch')
def giftCertSearch(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    certNumber = gevent.commonEventObject.formInputs.get('giftCertNum').get('stringInputs').get('value')[0]

    if not certNumber.isdigit():
        errorText = "<b>Error:</b> Gift certificate number must be a number."
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
    if not apiKeys.get("N_APIkey"):
        return apiKeys

    searchFields = f'''
[
    {{
        "field": "Shopping Cart ID",
        "operator": "EQUAL",
        "value": "{certNumber}"
    }}
]
'''

    outputFields = '''
[
    "Account ID",
    "First Name",
    "Last Name",
    "Email 1"
]
'''

    response = neon.postOrderSearch(searchFields, outputFields, N_APIkey=apiKeys['N_APIkey'], N_APIuser=NEON_API_USER)

    searchResults = response.get("searchResults")

    if len(searchResults) == 0:
        errorText = "<b>Error:</b> No gift certificate found with that number."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    cardSection1DecoratedText1 = CardService.DecoratedText(
        text = searchResults[0]['First Name'] + ' ' + searchResults[0]['Last Name'],
        bottom_label = searchResults[0]['Email 1'],
        top_label = "Neon ID: " + searchResults[0]['Account ID'],
    )

    cardSection1 = CardService.CardSection(
        widget = [cardSection1DecoratedText1],
        header = "Gift Certificate Purchaser"
    )

    card = CardService.CardBuilder(
        section = [cardSection1]
    )

    responseCard = card.build()

    return {"renderActions": responseCard}

@app.post('/composeTrigger')
def composeTrigger(gevent: models.GEvent):
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

    """ with build('gmail', 'v1', credentials=creds) as gmailClient:
        messageToken = gevent.gmail.accessToken
        messageId = gevent.gmail.messageId

        toEmail = gmailClient.users().messages().get(
            userId='me', 
            id=messageId, 
            #accessToken=messageToken, 
            format='metadata', 
            metadataHeaders='To') \
                .execute().get('payload').get('headers')[0].get('value')
        
        if toEmail == 'membership@asmbly.org':
            currentDraftId = gmailClient.users().drafts().list(
                userId='me',
                includeSpamTrash=False
            ).execute().get('drafts')[0].get('id')

            body = {
                'id': currentDraftId,
                'message': {
                    'payload': {
                        'headers': [
                            {
                                'name': 'CC',
                                'value': 'membership@asmbly.org'
                            }
                        ]
                    }
                }
            }

            update = gmailClient.users().drafts().update(
                userId='me',
                id=currentDraftId,
                body=body
            ).execute()

    cardSection1TextParagraph1 = CardService.TextParagraph(
        text = "Email headers updated."
    )

    cardSection1 = CardService.CardSection(
        widget = [cardSection1TextParagraph1]
    )

    card = CardService.CardBuilder(
        section=[cardSection1]
    )

    responseCard = card.build() """

    response = {
                "action": {
                    "navigations": [
                        {
                            "pushCard": {
                                "sections": [
                                    {
                                        "collapsible": False,
                                        "uncollapsible_widgets_count": 1,
                                        "widgets": [
                                            {
                                                "textParagraph": {
                                                    "text": "Email headers updated."
                                                }
                                            }
                                        ],
                                    }
                                ]
                            }
                        }]
                },
                "hostAppAction": {
                    "gmailAction": {
                        "updateDraftActionMarkup": {
                            "updateCcRecipients": {
                                "ccRecipients": [
                                    {
                                        "email": "membership@asmbly.org"
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        

    return response
                

@app.post('/settings')
def settings(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
    try:
        keys = getUserKeys(creds, decodeUser(gevent.authorizationEventObject.userIdToken))
    except:
        pass
        
    cardSection1TextInput1 = CardService.TextInput(
        field_name = "neonAPIKey",
        title = "Neon API Key",
        multiline = False,
        hint = keys.get('N_APIkey', '')
    )

    cardSection1TextInput2 = CardService.TextInput(
        field_name = "openPathAPIUser",
        title = "OpenPath API User",
        multiline = False,
        hint = keys.get('O_APIuser', '')
    )

    cardSection1TextInput3 = CardService.TextInput(
        field_name = "openPathAPIKey",
        title = "Openpath API Key",
        multiline = False,
        hint = keys.get('O_APIkey', '')
    )

    cardSection1ButtonList1Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('submitSettings')
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
        widget = [cardSection1TextInput1, 
                  cardSection1TextInput2, 
                  cardSection1TextInput3, 
                  cardSection1ButtonList1
                  ],
        header = "API Keys"
    )

    card = CardService.CardBuilder(
        section = [cardSection1]
    )

    responseCard = card.build()

    responseCard = {"renderActions": responseCard}

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
        ).execute()
    print(user)
    firstName = user.get('names')[0].get('givenName').lower()
    
    userId = decodeUser(gevent.authorizationEventObject.userIdToken)

    neonAPIKey = gevent.commonEventObject.formInputs.get('neonAPIKey').get('stringInputs').get('value')[0]
    openPathAPIUser = gevent.commonEventObject.formInputs.get('openPathAPIUser').get('stringInputs').get('value')[0]
    openPathAPIKey = gevent.commonEventObject.formInputs.get('openPathAPIKey').get('stringInputs').get('value')[0]

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

    secret_id = firstName + '_' + userId

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
        widget = [cardSection1TextParagraph1]
    )

    card = CardService.CardBuilder(
        section=[cardSection1]
    )

    responseCard = card.build()

    response = {"renderActions": responseCard}

    return response

@app.post('/contextualHome')
def contextualHome(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard
    
    cardSection1ButtonList1Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('getNeonId')
    )

    cardSection1ButtonList1Button1 = CardService.TextButton(
        text = "Get Neon ID",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList1Button1Action1
    )

    cardSection1ButtonList1 = CardService.ButtonSet(
        button = [cardSection1ButtonList1Button1]
    )

    cardSection1Divider1 = CardService.Divider()

    cardSection1ButtonList2Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('checkAccess')
    )

    cardSection1ButtonList2Button1 = CardService.TextButton(
        text = "Check Access",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList2Button1Action1
    )

    cardSection1ButtonList2 = CardService.ButtonSet(
        button = [cardSection1ButtonList2Button1]
    )

    cardSection1Divider2 = CardService.Divider()

    cardSection1ButtonList3Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('updateOP')
    )

    cardSection1ButtonList3Button1 = CardService.TextButton(
        text = "Update Openpath",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList3Button1Action1
    )

    cardSection1ButtonList3 = CardService.ButtonSet(
        button = [cardSection1ButtonList3Button1]
    )

    cardSection1Divider3 = CardService.Divider()

    cardSection1ButtonList4Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('classHomePage')
    )

    cardSection1ButtonList4Button1 = CardService.TextButton(  
        text = "Classes",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList4Button1Action1
    )

    cardSection1ButtonList4 = CardService.ButtonSet(
        button = [cardSection1ButtonList4Button1]
    )

    cardSection1 = CardService.CardSection(
        widget = [cardSection1ButtonList1, 
                  cardSection1Divider1, 
                  cardSection1ButtonList2, 
                  cardSection1Divider2, 
                  cardSection1ButtonList3, 
                  cardSection1Divider3, 
                  cardSection1ButtonList4
                  ],
        header = "Home"
    )

    card = CardService.CardBuilder(
        section = [cardSection1],
        name = "contextualHome"
    )

    responseCard = card.build()

    return responseCard

@app.post('/home')
def home(gevent: models.GEvent):
    token = gevent.authorizationEventObject.systemIdToken
    if not verifyGoogleToken(token):
        errorText = "<b>Error:</b> Unauthorized."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    cardSection1TextInput1 = CardService.TextInput(
        field_name = "checkAccess",
        title = "Account ID or Email",
        multiline = False
    )

    cardSection1ButtonList1Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('checkAccess')
    )

    cardSection1ButtonList1Button1 = CardService.TextButton(
        text = "Check Access",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList1Button1Action1
    )

    cardSection1ButtonList1 = CardService.ButtonSet(
        button = [cardSection1ButtonList1Button1]
    )

    cardSection1Divider1 = CardService.Divider()

    cardSection1TextInput2 = CardService.TextInput(
        field_name = "updateOpenpath",
        title = "Account ID or Email",
        multiline = False
    )

    cardSection1ButtonList2Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('updateOP')
    )

    cardSection1ButtonList2Button1 = CardService.TextButton(
        text = "Update Openpath",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList2Button1Action1
    )

    cardSection1ButtonList2 = CardService.ButtonSet(
        button = [cardSection1ButtonList2Button1]
    )

    cardSection1Divider2 = CardService.Divider()

    cardSection1TextInput3 = CardService.TextInput(
        field_name = "giftCertNum",
        title = "Gift Certificate Number",
        multiline = False
    )

    cardSection1ButtonList3Button1Action1 = CardService.Action(
        function_name = BASE_URL + app.url_path_for('giftCertSearch')
    )

    cardSection1ButtonList3Button1 = CardService.TextButton(
        text = "Lookup",
        text_button_style=CardService.TextButtonStyle.TEXT,
        on_click_action = cardSection1ButtonList3Button1Action1
    )

    cardSection1ButtonList3 = CardService.ButtonSet(
        button = [cardSection1ButtonList3Button1]
    )

    cardSection1 = CardService.CardSection(
        widget = [cardSection1TextInput1, 
                  cardSection1ButtonList1, 
                  cardSection1Divider1, 
                  cardSection1TextInput2, 
                  cardSection1ButtonList2, 
                  cardSection1Divider2, 
                  cardSection1TextInput3, 
                  cardSection1ButtonList3
                  ],
        header = "Home"
    )

    card = CardService.CardBuilder(
        section = [cardSection1],
        name = "home"
    )

    responseCard = card.build()

    return responseCard

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)