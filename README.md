# Active/Standy Across Availability Zones
Before the R80.40 release, which introduced the capability of setting up an Active/Standby cluster with members in separate AZs, Check Point didn't have a way to fail over across AZs. The aim of the two scripts in this repo is to allow eactly that:  cross -AZ, high availability,  with a (stateless) failover between two gateways or clusters deployed in different AZs. 

Specifically, the scripts here are intended to be used in the context of a multi-VPC architecture centered around a Transit Gateway, where inter-VPC, VPC<->On Prem and/or VPC<->internet traffic needs to be inspected. This solution has customers dedicate a VPC to a security setup consisting of two gateways (or clusters) in different AZs and use the Lambda function code of these scripts to make it so that at any given time one healthy gateway (or cluster) will have these traffic flows routed through it. If a gateway or cluster in one AZ become unavailable, the Lambda function will detect it and will change the routes so as to point traffic to the gateway (or cluster) in the other AZ.

There are two scripts in this repo:
[twogatwaysacrossAZs](/twogatwaysacrossAZs.py) is intended to be used when there are two gateways in different AZs
[twoclustersaccrossAZs] (/twoclustersaccrossAZs.py) is intended to use when there are either two gateways or two clusters in different AZs

## general mode of operation
the functions generally work in two stages. in the first stage the function, set up to be triggered periodically by a [Cloudwatch Scheduler](https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/RunLambdaSchedule.html), and living on a subnet who's routing points to the active gateway, sends a TCP probe to some host/port that would only succeed if the gateway is functioning, i.e., for the probe to succeed, it has to match a rule on on the gateway. If the probe fails it immediately tries to probe a second host/port. If both probes fail then, in the case of the two gateway script, the route table conrolling the subnet in changed to point to the ENI of the other gateway, while in the case of the two cluster setup, the functions waits for a while (because an intra-AZ failover might be under way), continuously trying to see if a connection has been restored, and only once this times out, it changes the route table.

## setup for twogatwaysacrossAZs
0) The code assumes a VPC is already in place with 2 Check Point cloudguard gateways deployed in 2 AZs. The VPC is attached to some TGW. The Subnets for the Check Point ENIs are different from the subnets used for the TGW attachment.
1) The code needs to be deployed as a python 3.7 Lambda function. 
2) the function needs to allow execution time of up to 10 secs. 
3) the function needs to be deployed in the same VPC as the gateways, on the same subnets as the subnets where the ENIs of the TGW are deployed 
4) A VPC endpoint for the EC2 API needs to be enabled on the VPC (so as to allow the function to make API calls to EC2 when the gateways are down).
5) Permissions: the Lambda function need to be describe route tables, as well as replace routes.
6) Trigger: the function needs to be triggered by a Cloudwatch scheduler. Every 30 secs seems reasonable. 
7) Environmental variables need to be set up as follows:

|variable name|variable value|notes|
|host1| an FQDN or IP address| the address for the first probe the function will use| 
|port1| a port number| the port for the first probe the function will use|
|host2| an FQDN or IP address| the address for the second probe the function will use| 
|port2| a port number| the port for the second probe the function will use|
|eni1|  ENI ID | The ENI of eth1 of the first gateway. The function will use this ENI in setting the target of the route if this gateway is to become active|
|eni2| ENI ID |  The ENI of eth1 of the second gateway. The function will use this ENI in setting the target of the route if this gateway is to become active|
|routetable| Route Table ID| the route table associated with the subnets to which the Lambda function and TGW ENIs are attached|

## setup for twoclustersaccrossAZs
0) The code assumes a VPC is already in place with 2 Check Point cloudguard gateways (or clusters) deployed in 2 AZs. The VPC is attached to some TGW. The Subnets for the Check Point ENIs are different from the subnets used for the TGW attachment.
1) The code needs to be deployed as a python 3.7 Lambda function. 
2) the function needs to allow execution time of up to 10 secs more than the "waittime" value is set (see below) 
3) the function needs to be deployed in the same VPC as the gateways, on the same subnets as the subnets where the ENIs of the TGW are deployed 
4) A VPC endpoint for the EC2 API needs to be enabled on the VPC (so as to allow the function to make API calls to EC2 when the gateways are down)
5) Permissions: the Lambda function need to be allows to describe instances, and route tables, as well as replace routes
6) Trigger: the function needs to be triggered by a Cloudwatch scheduler. Every 40 secs seems reasonable. 
7) Environmental variables need to be set up as follows:

|variable name|variable value|notes|
|host1| an FQDN or IP address| the address for the first probe the function will use| 
|port1| a port number| the port for the first probe the function will use|
|host2| an FQDN or IP address| the address for the second probe the function will use| 
|port2| a port number| the port for the second probe the function will use|
|routetable| Route Table ID| the route table associated with the subnets to which the Lambda function and TGW ENIs are attached|
|tagkey| a string| a tag key that together with the tage value (see below) uniquely identifies all and only the instances of the clusters (or gateways)|
|tagkey| a string| a tag value that together with the tage key (see acov) uniquely identifies all and only the instances of the clusters (or gateways)|
|waittime| a non-negative number| the number of seconds the function should wait when there is no connectivity before changing the route. This is necessary when clusters are used because intra-AZ cluster failover might be underway that will resolve the connectivity issue. a value no less than 30 is recommended|