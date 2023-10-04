from openPathUpdateSingle import openPathUpdateSingle
from helpers import neon

import httpx
import json
import datetime
import os

from fastapi import FastAPI
from functools import lru_cache

from gapps import CardService
from gapps.cardservice import models
from gapps.cardservice.utilities import decode_email, decode_user

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


app = FastAPI(title='Neon Workspace Integration')

#TODO: Implement Google secrets manager lookup for neon api user variable to pull into environment

SERVICE_ACCT_EMAIL = os.environ.get('SERVICE_ACCT_EMAIL')
NEON_API_USER = os.environ.get('N_APIUser')

@lru_cache()
async def getConstituentEmail(gevent: models.GEvent, creds: Credentials):
    
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


#Creates a general error reponse card with inputed error text
def createErrorResponseCard(errorText: str):
    cardSection1TextParagraph1 = CardService.TextParagraph(text=errorText)

    cardSection1 = CardService.CardSection(widget=cardSection1TextParagraph1)

    card = CardService.CardBuilder(section=cardSection1)

    responseCard = card.build()

    return responseCard

#Gets full Neon account from an email address
#Output fields:
#179 is WaivervDate
#182 is Facility Tour Date
def getNeonAcctByEmail(accountEmail: str) -> dict:
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

    response = neon.postAccountSearch(searchFields, outputFields)

    searchResults = response.get("searchResults")

    return searchResults

#Pushes card to front of stack with Neon ID of account with associated email address, otherwise tell user there
#are no Neon accounts associated with that email
@app.post('/getNeonId')
async def getNeonId(gevent: models.GEvent):
    try:
        creds = Credentials(gevent.authorizationEventObject.userOAuthToken)
        if not creds.is_valid():
            errorText = "<b>Error:</b> Credentials not valid."
            responseCard = createErrorResponseCard(errorText)
            return responseCard
    except:
        errorText = "<b>Error:</b> Credentials not found."
        responseCard = createErrorResponseCard(errorText)
        return responseCard

    userEmail = decode_email(gevent.authorizationEventObject.userIdToken)

    
    
    acctEmail = await getConstituentEmail(gevent, creds)
    searchResult = getNeonAcctByEmail(acctEmail)
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

        responseCard = CardService.CardBuilder(section=cardSection1).build()

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
def classHomePage():
    responseCard = {
        "renderActions": {
            "action": {
                "navigations": [
                    {
                        "pushCard": {
                            "sections": [
                                    {
                                        "header": "Add Registration",
                                        "collapsible": False,
                                        "uncollapsible_widgets_count": 1,
                                        "widgets": [
                                            {
                                                "text_input": {
                                                    "label": "Class Name (required)",
                                                    "name": "className"
                                                }
                                            },
                                            {
                                                "date_time_picker": {
                                                    "label": "Pick a date (optional)",
                                                    "name": "classDatePicker",
                                                    "value_ms_epoch": 1514775600,
                                                    "type": "DATE_ONLY"
                                                }
                                            },
                                            {
                                                "button_list": {
                                                    "buttons": [
                                                        {
                                                            "disabled": False,
                                                            "text": "Search Classes",
                                                            "on_click": {
                                                                "action": {
                                                                    "function": url_for('searchClasses')
                                                                }
                                                            },
                                                            "color": {
                                                                "red": "0.04",
                                                                "green": "0.40",
                                                                "blue": "0.51"
                                                            }
                                                        }
                                                    ]
                                                }
                                            }
                                        ]
                                    },
                                {
                                    "header": "Cancel Registration",
                                    "collapsible": False,
                                    "uncollapsible_widgets_count": 1,
                                    "widgets": [
                                        {
                                            "button_list": {
                                                "buttons": [
                                                    {
                                                        "disabled": False,
                                                        "text": "Cancel Registration",
                                                        "on_click": {
                                                            "action": {
                                                                "function": url_for('getAcctRegClassCancel')
                                                            }
                                                        },
                                                        "color": {
                                                            "red": "0.04",
                                                            "green": "0.40",
                                                            "blue": "0.51"
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    ]
                                        },
                                {
                                    "header": "Refund Registration",
                                    "collapsible": False,
                                    "uncollapsible_widgets_count": 1,
                                    "widgets": [
                                        {
                                            "button_list": {
                                                "buttons": [
                                                    {
                                                        "disabled": False,
                                                        "text": "Refund Registration",
                                                        "on_click": {
                                                            "action": {
                                                                "function": url_for('getAcctRegClassRefund')
                                                            }
                                                        },
                                                        "color": {
                                                            "red": "0.04",
                                                            "green": "0.40",
                                                            "blue": "0.51"
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    ]
                                        }
                            ]
                        }
                    }]
            }
        }
    }


    return json.dumps(responseCard)

#Push a card to the front of the stack that has all future classes of the searched Event Name. If a date is picked, 
#only classes on that date will be returned.
#Every event is returned as its own widget with corresponding button. Clicking that button invokes /classReg to register 
#the account for that class
@app.post('/searchClasses')
def searchClasses():
    if request.json["commonEventObject"]["formInputs"]["className"]["stringInputs"]["value"][0]:
        eventName = request.json["commonEventObject"]["formInputs"]["className"]["stringInputs"]["value"][0]
    else:
        errorText = "<b>Error:</b> Event name is required."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)
    if request.json["commonEventObject"]["formInputs"]["classDatePicker"]["dateInput"]["msSinceEpoch"]:
        #This will give UTC time - need to convert to CST
        eventStartDate = datetime.datetime.utcfromtimestamp(request.json["commonEventObject"]["formInputs"]["classDatePicker"]["dateInput"]["msSinceEpoch"]).isoformat()
        operator = "EQUAL"
    else:
        eventStartDate = datetime.date.today().isoformat()
        operator = "GREATER_AND_EQUAL"
    searchFields = [
        {
            "field": "Event Name",
            "operator": "CONTAIN",
            "value": eventName
        },
        {
            "field": "Event Start Date",
            "operator": operator,
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
        classResults = neon.postEventSearch(searchFields, outputFields)
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
                                    "top_label": result["Event Name"],
                                    "text": result["Event ID"],
                                    "bottom_label": result["Event Start Date"],
                                    "wrap_text": True,
                                    "button": {
                                        "text": "Register",
                                        "on_click": {
                                            "action": {
                                                "function": url_for('classReg')
                                            }
                                        }
                                    }
                                }
                            }

                responseCard["renderActions"]["action"]["navigations"][0]["pushCard"]["sections"][0]["widgets"].append(newWidget)
            return json.dumps(responseCard)
        else:
            errorText = "No classes found. Check your spelling or try a different date."
            responseCard = pushErrorResponseCard(errorText)
            return json.dumps(responseCard)
    except:
        errorText = "<b>Error:</b> Unable to find classes. Check your authentication or use the Neon website."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)

#Registers the active gmail user for the selected class with a $0 price. Pulls the eventID from the bottom label of the
#previous card
@app.post('/classReg')
def classReg():
    acctEmail = request.form('gmail_email')
    eventID = request.json('decorated_txt_bottom_label')
    searchResult = getNeonAcctByEmail(acctEmail)
    if len(searchResult) == 0:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)
    elif len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)
    else:
        accountFirstName = searchResult[0]["First Name"]
        accountLastName = searchResult[0]["Last Name"]
        accountID = searchResult[0]["Account ID"]
        try:
            neon.postEventRegistration(accountID, eventID, accountFirstName, accountLastName)
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
                                            "widgets": [
                                                {
                                                    "text_paragraph": {
                                                        "text": "<b>Successfully registered</b>"
                                                    }
                                                }
                                            ]
                                        }
                                    ]
                                }
                            }]
                    }
                }
            }
            return json.dumps(responseCard)
        except:
            errorText = "<b>Error:</b> Registration failed. Use Neon to register individual."
            responseCard = pushErrorResponseCard(errorText)
            return json.dumps(responseCard)


#Pushes card to front of stack showing all classes the user is currrently registered for. Each class is shown
# as its own widget with a corresponding button to cancel the registration for that class.
@app.post('/getAcctRegClassCancel')
def getAcctRegClassCancel():
    acctEmail = request.form('gmail_email')
    searchResult = getNeonAcctByEmail(acctEmail)
    if len(searchResult) == 1:
        neonID = searchResult[0]['Account ID']
        try:
            classDict = json.loads(neon.getAccountEventRegistrations(neonID))
            today = datetime.datetime.today()
            upcomingClasses = []
            for event in classDict["eventRegistrations"]:
                registrationID = event["id"]
                eventID = event["eventId"]
                regStatus = event["tickets"][0]["attendees"][0]["registrationStatus"]
                eventInfo = neon.getEvent(eventID)
                eventDate = datetime.datetime.fromisoformat(eventInfo["eventDates"]["startDate"]).date()
                eventName = eventInfo["name"]
                if eventDate - today >= 0:
                    upcomingClasses.append({"regID":registrationID, "eventID":eventID, "regStatus":regStatus, "eventName":eventName})
            
            if len(upcomingClasses > 0):
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
                for event in upcomingClasses:
                    newWidget = {
                                    "decorated_text": {
                                        "top_label": event["regID"],
                                        "text": event["eventName"],
                                        "bottom_label": event["regStatus"],
                                        "wrap_text": True,
                                        "button": {
                                            "text": "Cancel",
                                            "on_click": {
                                                "action": {
                                                    "function": url_for('classCancel')
                                                }
                                            }
                                        }
                                    }
                                }

                    responseCard["renderActions"]["action"]["navigations"][0]["pushCard"]["sections"][0]["widgets"].append(newWidget)
                return json.dumps(responseCard)
            else:
                errorText = "No upcoming classes found."
                responseCard = pushErrorResponseCard(errorText)
                return json.dumps(responseCard)
        except:
            errorText = "<b>Error:</b> Unable to find classes. Account may not have registered for any classes. Alternaively, check your authentication or use the Neon website."
            responseCard = pushErrorResponseCard(errorText)
            return json.dumps(responseCard)
    elif len(searchResult) >1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)
    else:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)
    
    

#@app.post('/getAcctRegClassRefund')

#Cancels user's registration in class. RegistrationID for given registration is pulled from top label of widget on 
# /getAcctRegClassCancel card
@app.post('/classCancel')
def classCancel():
    acctEmail = request.form('gmail_email')
    searchResult = getNeonAcctByEmail(acctEmail)
    if len(searchResult) == 1:
        neonID = searchResult[0]['Account ID']
    else:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)
    regId = request.json('decorated_txt_top_label')
    try:
        cancelResponse = neon.cancelClass(regId)
        if cancelResponse.status_code == 200 or 222 or 204:
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
                                                "widgets": [
                                                    {
                                                        "text_paragraph": {
                                                            "text": "<b>Registration Canceled</b>"
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                }]
                        }
                    }
                }
            return json.dumps(responseCard) 
        else:
            errorText = f"<b>Error:</b> Cancelation failed with status code {cancelResponse.status_code}. Use Neon to cancel registration."
            responseCard = pushErrorResponseCard(errorText)
            return json.dumps(responseCard)
    except:
        errorText = "<b>Error:</b> Cancelation failed. Check your authentication or use the Neon website."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)



#@app.post('/classRefund')

@app.post('/checkAccess')
def checkAccess():
    acctEmail = request.form('gmail_email')
    searchResult = getNeonAcctByEmail(acctEmail)
    if len(searchResult) == 1:
        neonID = searchResult[0]['Account ID']
        accountName = searchResult[0]["First Name"] + \
            ' ' + searchResult[0]["Last Name"]
        if waiverDate := searchResult[0]['WaiverDate']:
            waiverBoolean = True
        else:
            waiverBoolean = False
        if tourDate := searchResult[0]['FacilityTourDate']:
            orientBoolean = True
        else:
            orientBoolean = False
        if activeMem := searchResult[0]['Membership Start Date']:
            memBoolean = True
        else:
            memBoolean = False
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
                                    "widgets": [
                                        {
                                            "selection_input": {
                                                "label": f'''Account Name: {accountName}; Account ID: {neonID}''',
                                                "name": "checkList",
                                                "items": [
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
                                                ],
                                                "type": "CHECK_BOX"
                                            }
                                        }
                                    ]
                                }
                            ]
                        }}]
            }
        }
    }
        return json.dumps(responseCard)
    elif len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)
    else:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)
    
    
    


@app.post('/updateOP')
def updateOP():
    acctEmail = request.form('gmail_email')
    searchResult = getNeonAcctByEmail(acctEmail)
    if len(searchResult) == 1:
        neonID = searchResult[0]['Account ID']
        if searchResult[0]['WaiverDate'] and searchResult[0]['FacilityTourDate'] and searchResult[0]['Membership Start Date']:
            openPathUpdateSingle(neonID)
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
                                                "widgets": [
                                                    {
                                                        "text_paragraph": {
                                                            "text": "<b>Openpath Updated</b>"
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                }]
                        }
                    }
                }
            return json.dumps(responseCard)
        else:
            errorText = "Account has not completed all access requirements. Use the Check Access button to find out what's missing."
            responseCard = pushErrorResponseCard(errorText)
            return json.dumps(responseCard)
    elif len(searchResult) > 1:
        errorText = "<b>Error:</b> Multiple Neon accounts found. Go to <a href=\"https://app.neonsso.com/login\">Neon</a> to merge duplicate accounts."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)
    else:
        errorText = "<b>Error:</b> No Neon accounts found."
        responseCard = pushErrorResponseCard(errorText)
        return json.dumps(responseCard)


#@app.post('/settings')
#@app.post('/submitSettings')

#@app.post('/contextualHome')

#@app.post('/home')
responseCard = {
    "renderActions": {
        "action": {
            "navigations": [
                {
                    "pushCard": []
                }]
        }
    }
}
