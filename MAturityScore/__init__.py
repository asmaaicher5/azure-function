from os import environ
import logging
import json
import lxpy
import requests
import time

import azure.functions as func

#config = lxpy.ClientConfiguration(
    #base_url='',
  #  api_token=''
#)


config = lxpy.ClientConfiguration(
    base_url=environ.get('BASE_URL', ''),
    api_token=environ.get('API_TOKEN', '')
)

pathfinder = lxpy.Pathfinder(config)

auth_url = 'https://' + config.base_url + '/services/mtm/v1/oauth2/token'
request_url = 'https://' + config.base_url + '/services/pathfinder/v1/'

getFactSheet_url = request_url +'factSheets/'

#Authorization
def getApiToken():
    with open('access.json') as json_file:
        data = json.load(json_file)
        return data['apitoken']


def getAccessToken():
    #different than callPost since it needs to send the auth_header
    response = requests.post(auth_url, auth=('apitoken', config.api_token),
                             data={'grant_type': 'client_credentials'})
    response.raise_for_status()
    access_token = response.json()['access_token']
    return access_token


def getHeader(access_token):
    return {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}


# General function to call GraphQL given a query
def call(query, access_token):
    data = {"query" : query}
    json_data = json.dumps(data)
    response = requests.post(url=request_url + "/graphql", headers=getHeader(access_token), data=json_data)
    response.raise_for_status()
    return response.json()


def mapMaturityToNumber(param):
    thisdict = {
        "reactive": 1,
        "defined": 2,
        "managed": 3,
        "measured": 4,
        "innovative":5
    }
    return thisdict[param]



def getMaturityScore(relation, fieldName):
    maturity = 0
    for field in relation['fields']:
        if field['name'] == fieldName:
            maturityNumber = mapMaturityToNumber(field['data']['keyword'])
            
    return maturityNumber

def getFactsheet (fsID):
    endpoint = getFactSheet_url + fsID
    access_token = getAccessToken()
    response = requests.get(endpoint, json={}, headers={
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    })
    return response.json()


    techFit = 5
    factsheetData = getFactsheet(fsID)
    if factsheetData is not None:
        for field in factsheetData['data']['fields']:
            if field['name'] == 'technicalSuitability':
                techFitNumber = mapTechFitToNumber(field['data']['keyword'])
                if techFitNumber < techFit:
                    techFit = techFitNumber
    return techFit



def postMaturityScore(fsId, maturityScore):
    try:
        query = buildGraphQL (fsId,maturityScore)
        response = call(query,getAccessToken())
    except:
        logging.error("There was error updating businessCapability factsheet")
        pass
    else:
        return response


def buildGraphQL (fsId,globalRatingScore):
    query="""
          mutation {
        result: updateFactSheet(id: \"%s\", patches: [{op: replace, path: \"/maturityScore\", value: \"%s\"}], validateOnly: false) {
          factSheet {
            ... on BusinessCapability {
              maturityScore
            }
          }
        }
      }
      """%(fsId,globalRatingScore)

    logging.info(query)
    return query

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        data = req.get_json()
        #with open ("data.json", 'r') as infile:
        #    data = json.load(infile)
        patches = []

        technologyMaturityScore = 0
        processMaturityScore = 0
        peopleMaturityScore = 0
        maturityScore=0
        technologyMaturityNumbers=[]
        processMaturityNumbers=[]
        peopleMaturityNumbers=[]
      

        for relation in data['factSheet']['relations']:
            if relation['type'] == 'relBusinessCapabilityToApplication':
                technologyMaturityNumbers.append(getMaturityScore(relation,'technologyScore'))
            
            if relation['type'] == 'relBusinessCapabilityToUserGroup':
                peopleMaturityNumbers.append(getMaturityScore(relation,'peopleScore'))
                
            if relation['type'] == 'relBusinessCapabilityToProcess':
                processMaturityNumbers.append(getMaturityScore(relation,'processScore'))
                
        technologyMaturityScore= sum(technologyMaturityNumbers) / len(technologyMaturityNumbers)
        peopleMaturityScore= sum(peopleMaturityNumbers) / len(peopleMaturityNumbers)
        processMaturityScore= sum(processMaturityNumbers) / len(processMaturityNumbers)
        maturityScore= (technologyMaturityScore+peopleMaturityScore+processMaturityScore)/3

           


        print('technologyMaturityScore: %d',(technologyMaturityScore))
        print('peopleMaturityScore:%d',(peopleMaturityScore))
        print('processMaturityScore:%d',(processMaturityScore))
        print('maturityScore:%d',(maturityScore))
        
        if maturityScore is not None:
            response = postMaturityScore(data['factSheet']['id'], maturityScore)
            logging.info(str(response))


       #if maturityScore is not None:
            #response = postGlobalRating(data['factSheet']['id'], getGlobalMaturity(globalRating))
           # logging.info(str(response))

        return func.HttpResponse(
            "This HTTP triggered function executed successfully.",
            status_code=200
        )
    except Exception as inst:
        logging.error("There was a value error in the received object")
        logging.error(type(inst))    # the exception instance
        logging.error(inst.args)     # arguments stored in .args
        logging.error(inst)
        return func.HttpResponse(
            "This HTTP triggered function executed with an error.",
            status_code=400
        )
        pass
