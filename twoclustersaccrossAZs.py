# -*- coding: utf-8 -*-
"""
Created on Mon Oct  7 14:29:21 2019

@author: lebowits

1. test connectivity
2. if none, wait 40 secs and test again (maybe there's a faiover...give it time)
3. if none,
    a. get clusters
    b. get route table
    c. figure out the active interface in the other cluster and switch
    d. test connectivity and report


"""

import boto3
import os
import socket
import json
import time

host1= os.environ['host1'].strip()
host2=os.environ['host2'].strip()
port1= int(os.environ['port1'].strip())
port2= int(os.environ['port2'].strip())
tagkey= os.environ['tagkey'].strip()
tagval= os.environ['tagval'].strip()
routetable=os.environ['routetable'].strip()
waittime=int(os.environ['waittime'].strip()) #the time for the lambda has to be at least waittime+10


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


def CreateClustersTable():

    ec2=boto3.client("ec2")
    try: 
        gwsapi=ec2.describe_instances(Filters=[{"Name": "tag:"+tagkey, "Values": [tagval]}])
        gws=[]
        for x in gwsapi["Reservations"]:
            for y in x['Instances']:
                gws.append(y)
        if len(gws)==0:
            raise
    except:
        return [0,"could not get instances. Check permisions and connectivity to EC2 API endpoint, or the correct tagging on the GWs. Looking for key " +tagkey+" and value "+tagval]
    else:
        
#   az,instance id, is active, eth1 ENI, eth1 IP    
        try:
            M=[]
            for gw in gws:
                m=[gw['Placement']['AvailabilityZone']
                    , gw['InstanceId']
                    , len(gw['NetworkInterfaces'][1]['PrivateIpAddresses'])==2   #right now this is the best we can do to tell that an instance is active.                    
                    , [x['NetworkInterfaceId'] for x in gw['NetworkInterfaces'] if x['Attachment']["DeviceIndex"]==1].pop()
                    , gw['VpcId']
                    ]
                M.append(m)
        except:
            listofinsids="zubi"
            for x in gws:
                listofinsids+=' ,'+x['InstanceId']
            return [0,"some of the tagged instances don't have a second interface.   These are all the tagged GWs: "+listofinsids]
        else:
            return [1,M]



def switchAZ(ctable):
    ec2 = boto3.client('ec2')
    try:
        rt2 = ec2.describe_route_tables(Filters=[{'Name': 'route-table-id', 'Values': [routetable]}
                                            ,{'Name': 'route.destination-cidr-block', 'Values': ["0.0.0.0/0"]}])['RouteTables'][0]['Routes'] 
    except:
        return [0,"could not fetch route table "+routetable]
    else:
        try: 
            currenteni=[x['NetworkInterfaceId'] for x in rt2 if x['DestinationCidrBlock']=='0.0.0.0/0'].pop()
        except:
            return [0,"route table "+ routetable+" doesn't have an ENI as default gateway"]
        else:
            try: 
                currentgw=[x for x in ctable if x[3]==currenteni].pop()
            except:
                return [0,"the current eni set as the default gw: "+currenteni+", isn't of any gateway fetched"]
            else:
                try:
                    onegwinAZ=sum([1 for x in ctable if x[0]!=currentgw[0]])==1
                    newgateway=[x for x in ctable if x[0]!=currentgw[0] and (x[2]==True or onegwinAZ)].pop()
                except:
                    return [0,"no single GW or cluster was found on a different AZ"]
                else:
                    try:
                        ec2.replace_route(DestinationCidrBlock="0.0.0.0/0", RouteTableId=routetable, NetworkInterfaceId=newgateway[3])
                    except:
                        return [0,"could not replace route on the route table "+routetable+ " with eni "+newgateway[3]+" on gateway "+newgateway[1]+". please check permissions"] #might be that GWs are in different VPC...need to verify
                    else:
                        return [1,"route table "+routetable+" default gw changed to instance "+newgateway[1]+" and interface "+newgateway[3]]



def main():
    itn=istherenetworking()
    if itn==1:
        print("connectivity is in place. no change was made")
    else:
# we can optimize for the case there is no cluster but not necessary
        t=time.time()
        print("connectivity is broken. waiting up to "+str(waittime+3)+" secs to see if conneectiity will be restored")
        while (time.time()-t)<waittime and itn==0:
            time.sleep(3)
            itn=istherenetworking()                           
        if itn==1:
            print("connectivity is restored. no change was made")                
        else:          
            print("Wait time elapsed. attempting to change the route")
            ctable=CreateClustersTable()
            if ctable[0]==1:
                saz=switchAZ(ctable[1])
                print(saz[1])
                if saz[0]==1:
                    itn=istherenetworking()
                    if itn==1:
                        print("Changed route and onnectivity is now restored")
                    else:
                        print("Alert: Changed route but connectivity is not restored")
                else:
                    print("Alert: Connecticity is down but couldn't change route")
            else: 
                print(ctable[1])
                print("Alert: Connecticity is down but couldn't get good clusters information. Did not change any routes")
                
        
def lambda_handler(event, context):
    main()
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }



