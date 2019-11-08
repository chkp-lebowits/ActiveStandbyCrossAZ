# -*- coding: utf-8 -*-
"""
this is meant to run from a subnet whose associated route table is routetable. the eni params are alterntive default gateways
and the host/port pairs should be accessible from the host from which this code runs.
lambda timeout needs to be set to at least 9 secs
lambda needs access to the ec2 API, e.g., through a VPC endpoint
"""

import socket
import boto3
import os
import json


host1= os.environ['host1'].strip()
host2=os.environ['host2'].strip()
port1= int(os.environ['port1'].strip())
port2= int(os.environ['port2'].strip())
eni1=os.environ['eni1'].strip()
eni2=os.environ['eni2'].strip()
routetable=os.environ['routetable'].strip()

def lambda_handler(event, context):
    mainproc()
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }


def istherenetworking():
    try: 
        conn=socket.create_connection((host1, port1),1.5)
    except:
        try:
            conn=socket.create_connection((host2, port2),1.5)
        except:
            return 0
            
        else:
           return 1
    else:
        return 1

def changeeni():
    ec2c = boto3.client('ec2')
    try:
        rt2 = ec2c.describe_route_tables(Filters=[{'Name': 'route-table-id', 'Values': [routetable]}
                                            ,{'Name': 'route.destination-cidr-block', 'Values': ["0.0.0.0/0"]}])
    except:
        return "could not find default route for table "+routetable
    else:
        try:
            currneteni=[x['NetworkInterfaceId'] for x in rt2['RouteTables'][0]['Routes'] if x['DestinationCidrBlock']=='0.0.0.0/0'].pop()
        except:
            return "routetable "+routetable+" default route doesn't point to an eni "
        else: 
            if (currneteni==eni1 or currneteni==eni2):
                neweni=[x for x in [eni1,eni2] if x!=currneteni].pop()
                try:
                    ec2c.replace_route(DestinationCidrBlock="0.0.0.0/0", RouteTableId=routetable, NetworkInterfaceId=neweni)
                except:
                    return "could not change eni " + neweni + " in route table "+ routetable
                else:
                    return neweni
            else:
                return "the eni the route table "+routetable+" points to is not included in the parameters"


def mainproc():
    itn=istherenetworking()
    if itn==1:
        print("networking is in place. no change was made")
    elif itn==0:
        ceni=changeeni()
        if ceni[:3]=="eni":
            itn=istherenetworking()
            if itn==1:
                print("switched eni to ",ceni, " and restored connectivity")
            else:
                print("switched eni to ",ceni, " but connectivity is not restored")
        else:
            print(ceni)
            



