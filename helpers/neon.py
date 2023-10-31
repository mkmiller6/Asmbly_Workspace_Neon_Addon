from pprint import pprint
import base64
import json
import datetime

from helpers.api import apiCall

N_baseURL = 'https://api.neoncrm.com/v2'

###########################
#####   NEON EVENTS   #####
###########################

def getHeaders(N_APIkey, N_APIuser):
    N_auth = f'{N_APIuser}:{N_APIkey}'
    N_signature = base64.b64encode(bytearray(N_auth.encode())).decode()
    N_headers = {'Content-Type': 'application/json',
                'Authorization': f'Basic {N_signature}'}
    return N_headers

# Get list of custom fields for events
def getEventCustomFields(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = '/customFields'
    queryParams = '?category=Event'
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseEventFields = apiCall(httpVerb, url, data, N_headers).json()
    # print("### CUSTOM FIELDS ###\n")
    # pprint(responseFields)

    return responseEventFields


# Get list of event categories
def getEventCategories(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = '/properties/eventCategories'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseCategories = apiCall(httpVerb, url, data, N_headers).json()

    return responseCategories


# Filter event categories to active only
def getEventActiveCategories(responseCategories):
    categories = list(
        filter(lambda cat: cat["status"] == "ACTIVE", responseCategories))

    return categories


# Get a list of active event category names
def getEventActiveCatNames(responseCategories):
    categories = []
    for cat in responseCategories:
        if cat["status"] == "ACTIVE":
            categories.append(cat["name"])

    return categories


# Get possible search fields for POST to /events/search
def getEventSearchFields(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = '/events/search/searchFields'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseSearchFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseSearchFields


# Get possible output fields for POST to /events/search
def getEventOutputFields(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = '/events/search/outputFields'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseOutputFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseOutputFields


# Post search query to get back events (only gets 200 events, pagination not currently supported)
def postEventSearch(searchFields, outputFields, N_APIkey, N_APIuser, page=0):
    httpVerb = 'POST'
    resourcePath = '/events/search'
    queryParams = ''
    data = f'''
    {{
        "searchFields": {searchFields},
        "outputFields": {outputFields},
        "pagination": {{
        "currentPage": {page},
        "pageSize": 200
        }}
    }}
    '''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvents

# Get registrations for a single event by event ID


def getEventRegistrants(eventId, N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = f'/events/{eventId}/eventRegistrations'
    queryParams = ''
    # queryParams = '?page=0'
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    individualEvent = apiCall(httpVerb, url, data, N_headers).json()

    return individualEvent


# Get event registration count (SUCCEEDED status only) from "eventRegistrations" field in individual event
def getEventRegistrantCount(registrantList):
    count = 0
    if type(registrantList) is not type(None): 
        for registrant in registrantList:
            status = registrant["tickets"][0]["attendees"][0]["registrationStatus"]
            if status == "SUCCEEDED":
                tickets = registrant["tickets"][0]["attendees"]
                count += len(tickets)

    return count


# Get individual accounts by account ID
def getAccountIndividual(acctId, N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = f'/accounts/{acctId}'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseAccount = apiCall(httpVerb, url, data, N_headers).json()

    return responseAccount

# Get possible search fields for POST to /orders/search


def getOrderSearchFields(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = '/orders/search/searchFields'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseSearchFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseSearchFields


# Get possible output fields for POST to /events/search
def getOrderOutputFields(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = '/orders/search/outputFields'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseOutputFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseOutputFields

# Post search query to get back orders (only gets 200 events, pagination not currently supported)


def postOrderSearch(searchFields, outputFields, N_APIkey, N_APIuser):
    httpVerb = 'POST'
    resourcePath = '/orders/search'
    queryParams = ''
    data = f'''
    {{
        "searchFields": {searchFields},
        "outputFields": {outputFields},
        "pagination": {{
        "currentPage": 0,
        "pageSize": 200
        }}
    }}
    '''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvents

# Get possible search fields for POST to /accounts/search


def getAccountSearchFields(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = '/accounts/search/searchFields'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseSearchFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseSearchFields


# Get possible output fields for POST to /events/search
def getAccountOutputFields(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = '/accounts/search/outputFields'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseOutputFields = apiCall(httpVerb, url, data, N_headers).json()

    return responseOutputFields

# Post search query to get back orders (only gets 200 events, pagination not currently supported)


def postAccountSearch(searchFields, outputFields, N_APIkey, N_APIuser):
    httpVerb = 'POST'
    resourcePath = '/accounts/search'
    queryParams = ''
    data = f'''
    {{
        "searchFields": {searchFields},
        "outputFields": {outputFields},
        "pagination": {{
        "currentPage": 0,
        "pageSize": 200
        }}
    }}
    '''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvents


def postEventRegistration(accountID, eventID, accountFirstName, accountLastName, N_APIkey, N_APIuser):
    httpVerb = 'POST'
    resourcePath = '/eventRegistrations'
    queryParams = ''
    data = {
        "eventId": eventID,
        "sendSystemEmail": True,
        "registrationAmount": 0,
        "ignoreCapacity": False,
        "registrantAccountId": accountID,
        "registrationDateTime": f"{datetime.datetime.today().isoformat(timespec='seconds')}Z",
        "tickets": [
            {
                "attendees": [
                    {
                        "accountId": accountID,
                        "firstName": accountFirstName,
                        "lastName": accountLastName,
                        "markedAttended": False,
                        "registrantAccountId": accountID,
                        "registrationStatus": "SUCCEEDED",
                        "registrationDate": datetime.datetime.today().isoformat(timespec='seconds'),
                    }
                ]
            }
        ],
        "totalCharge": 0
    }
    data = json.dumps(data)

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers)

    return responseEvents

def getAccountEventRegistrations(neonId, N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = f'/accounts/{neonId}/eventRegistrations'
    queryParams = '?sortColumn=registrationDateTime&sortDirection=DESC'
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvents

def getAccountSingleEventRegistration(neonId, eventId, N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = f'/accounts/{neonId}/eventRegistrations'
    queryParams = f'?sortColumn=registrationDateTime&sortDirection=DESC&eventId={eventId}'
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseEvents = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvents

def getEvent(eventId, N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = f'/events/{eventId}'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseEvent = apiCall(httpVerb, url, data, N_headers).json()

    return responseEvent

def cancelClass(registrationId, eventId: str, neonId: str, N_APIkey, N_APIuser):
    httpVerb = 'PATCH'
    resourcePath = f'/eventRegistrations/{registrationId}'
    queryParams = ''
    reg = getAccountSingleEventRegistration(neonId, eventId, N_APIkey, N_APIuser).get('eventRegistrations')[0]
    #ticketId = reg.get("tickets")[0].get("ticketId")
    attendeeId = reg.get("tickets")[0].get("attendees")[0].get("attendeeId")
    data = {
        "eventId": eventId,
        "registrantAccountId": neonId,
        "tickets": [
            {
                "attendees": [
                    {
                        "attendeeId": attendeeId,
                        "registrationStatus": "CANCELED",
                    }
                ]
            }
        ]
    }
    data = json.dumps(data)

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseStatus = apiCall(httpVerb, url, data, N_headers)

    return responseStatus

def getEventTopics(N_APIkey, N_APIuser):
    httpVerb = 'GET'
    resourcePath = f'/properties/eventTopics'
    queryParams = ''
    data = ''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    responseTopics = apiCall(httpVerb, url, data, N_headers).json()

    return responseTopics

def eventTierCodePatch(classId, tier, N_APIkey, N_APIuser):
    httpVerb = 'PATCH'
    resourcePath = f'/events/{classId}'
    queryParams = ''
    data = f'''
    {{
        "code": "Tier {tier}"
    }}
    '''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data, N_headers)

    return response

def eventTimePatch(classId: str, N_APIkey, N_APIuser, eventStartTime: str='hh:mm AM/PM', eventEndTime: str="hh:mm AM/PM"):
    httpVerb = 'PATCH'
    resourcePath = f'/events/{classId}'
    queryParams = ''
    data = f'''
    {{
        "eventDates": {{
            "startTime": "{eventStartTime}",
            "endTime": "{eventEndTime}"
        }}
    }}
    '''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data, N_headers)

    return response

def eventAttendeeCountPatch(classId: str, maxAttendees: int, N_APIkey, N_APIuser):
    httpVerb = 'PATCH'
    resourcePath = f'/events/{classId}'
    queryParams = ''
    data = f'''
    {{
        "maximumAttendees": {maxAttendees}
    }}
    '''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data, N_headers)

    return response

def eventNamePatch(classId: str, newName: str, N_APIkey, N_APIuser):
    httpVerb = 'PATCH'
    resourcePath = f'/events/{classId}'
    queryParams = ''
    data = f'''
    {{
        "name": "{newName}"
    }}
    '''

    # Neon Account Info
    N_headers = getHeaders(N_APIkey, N_APIuser)

    url = N_baseURL + resourcePath + queryParams
    response = apiCall(httpVerb, url, data, N_headers)

    return response

