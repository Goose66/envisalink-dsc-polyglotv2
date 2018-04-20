# envisalink-dsc-polyglotv2
A Nodeserver for Polyglot v2 that interfaces with a DSC PowerSeries alarm panel through an EnvisaLink EVL-3/4 adapater. See http://www.eyezon.com/?page_id=176 for more information on the EnvisaLink EVL-4.

Instructions for Local (Co-resident with Polyglot) installation:

1. Copy the files from this repository to the folder ~/.polyglot/nodeservers/EnvisaLink-DSC in your Polyglot v2 installation.
2. Log into the Polyglot Version 2 Dashboard (https://(Polyglot IP address):3000)
3. Add the EnvisaLink-DSC nodeserver as a Local nodeserver type.
4. Add the following required Custom Configuration Parameters under Configuration:
```
    ipaddress - IP address of Autelis Pool Control device 
    username - login name for Autelis Pool Control device
    password - password for Autelis Pool Control device
```
5. Add the following optional Custom Configuration Parameters:
```
    pollinginterval - polling interval in seconds (defaults to 60)
    ignoresolar - ignore Solar Heat settings (defaults to False)
```
Here are the known issues with this version:

1. The nodes are added with the node address as the name (description). You need to change the names (especially for the AUX relays) to the name of the pool device controlled by the node.
2. The equipment nodes only take DON and DOF commands, so if you put the nodes in a Managed Scene and do a Fast On or Fast Off, the node will not respond.
3. If you turn spa and spaht or pool and poolht on right after one another (such as putting both in a scene), the second one does not take. There has to be a 2 or 3 second delay between spa and spaht or pool and poolht to make sure both are processed, so it will require a program. I have logged this with Autelis.
4. The Nodeserver only adds nodes that are returning values, so it should only add nodes for those equipment and temp_controls specific to your installation, except for solar heat which it seems to add regardless. You can add a flag to the custom parameters to ignore solar heat (see above).
5. The Nodeserver currently doesn't support dimming AUX relays, colored lights, or one touch nodes (I don't have these installed to test).
6. The Nodeserver utilizes whatever temp units (F or C) are set in your Aqualink controller. If you change it while the Nodeserver is running, everything will update, but temp values can be wonky for a while. A Query (or time) should restore correct values.