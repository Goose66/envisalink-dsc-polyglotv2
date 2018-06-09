#!/usr/bin/python3
# Polyglot Node Server for EnvisaLink EVL 3/4 Device (DSC)

import sys
import time

import envisalinktpi as EVL
import polyinterface

_ISY_BOOL_UOM = 2 # Used for reporting status values for Controller node
_ISY_INDEX_UOM = 25 # Index UOM for custom states (must match editor/NLS in profile):
_ISY_USER_NUM_UOM = 70 # User Number UOM for reporting last user number
_ISY_MINUTES_UOM = 45 # Used for reporting duration in minutes

_LOGGER = polyinterface.LOGGER

_PART_ADDR_FORMAT_STRING = "partition%1d"
_ZONE_ADDR_FORMAT_STRING = "zone%02d"
_CMD_OUTPUT_ADDR_FORMAT_STRING = "cmdout%02d"

_PARM_IP_ADDRESS_NAME = "ipaddress"
_PARM_PASSWORD_NAME = "password"
_PARM_USER_CODE_NAME = "usercode"
_PARM_NUM_PARTITIONS_NAME = "numpartitions"
_PARM_NUM_ZONES_NAME = "numzones"
_PARM_NUM_CMD_OUTS_NAME = "numcmdouts"

_DEFAULT_IP_ADDRESS = "0.0.0.0"
_DEFAULT_PASSWORD = "user"
_DEFAULT_USER_CODE = "5555"
_DEFAULT_NUM_PARTITIONS = 1
_DEFAULT_NUM_ZONES = 16
_DEFAULT_NUM_CMDOUTS = 4

# Node class for partitions
class Partition(polyinterface.Node):

    id = "PARTITION"

    # Override init to handle partition number
    def __init__(self, controller, primary, partNum):
        super(Partition, self).__init__(controller, primary, _PART_ADDR_FORMAT_STRING % partNum, "Partition %1d" % partNum)
        self.partitionNum = partNum
        self.initialBypassZoneDump = False
        self.readyState = False

    # Update the driver values based on the command received from the EnvisaLink for the partition
    def update_state_values(self, cmd, data):

        # update the ST value
        if cmd == EVL.CMD_PARTITION_READY:
            self.setDriver("ST", 0) # Ready

            self.readyState = True

        elif cmd == EVL.CMD_PARTITION_NOT_READY:
            self.setDriver("ST", 1) # Not Ready

            self.readyState = False

        elif cmd == EVL.CMD_PARTITION_ARMED:

            # get the arming mode from the data
            armingMode = data.decode("ascii")[-1:]
            if armingMode == "0":
                self.setDriver("ST", 2) # Armed Away
            elif armingMode == "1":
                self.setDriver("ST", 3) # Armed Stay
            elif armingMode == "2":
                self.setDriver("ST", 4) # Armed Away Zero-Entry
            elif armingMode == "3":
                self.setDriver("ST", 5) # Armed Stay Zero-Entry

            self.readyState = False
            
        elif cmd == EVL.CMD_PARTITION_IN_ALARM:

            # send a DON commmand when the partition goes to an alarming state
            self.reportCmd("DON")

            # set the status to Alarming
            self.setDriver("ST", 6)

            self.readyState = False

        elif cmd == EVL.CMD_PARTITION_DISARMED:
            
            # send a DOF commmand when the partition is disarmed
            self.reportCmd("DOF")

        elif cmd == EVL.CMD_EXIT_DELAY_IN_PROGRESS:
            self.setDriver("ST", 7) # Exit Delay

            self.readyState = False

        elif cmd == EVL.CMD_ENTRY_DELAY_IN_PROGRESS:
            self.setDriver("ST", 8) # Entry Delay

            self.readyState = False

        # update the GV0 (chime enabled) value
        elif cmd == EVL.CMD_CHIME_ENABLED:
            self.setDriver("GV0", 1)

        elif cmd == EVL.CMD_CHIME_DISABLED:
            self.setDriver("GV0", 0)

        elif cmd in (EVL.CMD_SPECIAL_OPENING, EVL.CMD_SPECIAL_CLOSING):
            self.setDriver("GV1", 0)

        elif cmd in (EVL.CMD_USER_CLOSING, EVL.CMD_USER_OPENING):
            userNum = int(data.decode("ascii")[-4:])
            self.setDriver("GV1", userNum)

    # Arm the partition in Away mode (the listener thread will update the corresponding driver values)
    def arm_away(self, command):
        
        # send arming command to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_ARM_PARTITION, "%1d" % self.partitionNum):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Arm the partition in Stay mode (the listener thread will update the corresponding driver values)
    def arm_stay(self, command):
        
        # send arming command to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_ARM_PARTITION_STAY, "%1d" % self.partitionNum):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Arm the partition in Zero Entry mode (the listener thread will update the corresponding driver values)
    def arm_zero_entry(self, command):
        
        # send arming command to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_ARM_PARTITION_NO_ENTRY_DELAY, "%1d" % self.partitionNum):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to arm partition failed for node %s.", self.address)

    # Disarm the partition (the listener thread will update the corresponding driver values)
    def disarm(self, command):
        
        # send disarm command and user code to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_DISARM_PARTITION, "%1d%s" % (self.partitionNum, self.controller.userCode)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to disarm partition failed for node %s.", self.address)

    # Toggle the door chime for the partition (the listener thread will update the corresponding driver values)
    def toggle_chime(self, command):
        
        # send door chime toggle keystrokes to EnvisaLink device for the partition numner
        if self.controller.envisalink.send_command(EVL.CMD_SEND_KEYSTROKES, "%1d%s" % (self.partitionNum, EVL.KEYS_TOGGLE_DOOR_CHIME)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to toggle door chime failed for node %s.", self.address)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV1", "value": 0, "uom": _ISY_USER_NUM_UOM}
    ]
    commands = {
        "DISARM": disarm,
        "ARM_AWAY": arm_away,
        "ARM_STAY": arm_stay,
        "ARM_ZEROENTRY": arm_zero_entry,
        "TOGGLE_CHIME": toggle_chime
    }

# Node class for zones
class Zone(polyinterface.Node):

    id = "ZONE"

    # Override init to handle partition number
    def __init__(self, controller, primary, zoneNum):
        super(Zone, self).__init__(controller, primary, _ZONE_ADDR_FORMAT_STRING % zoneNum, "Zone %02d" % zoneNum)
        self.zoneNum = zoneNum       

    # Update ST driver value based on the command received from the EnvisaLink for the zone
    def update_state_values(self, cmd, data):

        # update the ST value
        if cmd == EVL.CMD_ZONE_RESTORED:

            # send the DOF command for the node - allows node to be scene controller
            self.reportCmd("DOF")

            self.setDriver("ST", 0) # Closed

        elif cmd == EVL.CMD_ZONE_OPEN:

            # send the DON command for the node - allows node to be scene controller
            self.reportCmd("DON")

            self.setDriver("ST", 1) # Open

        elif cmd == EVL.CMD_ZONE_ALARM:
            self.setDriver("ST", 2) # Alarming

        elif cmd == EVL.CMD_ZONE_ALARM_RESTORED:
            self.setDriver("ST", 0) # Closed

    # Set the bypasse driver value
    def set_bypass(self, bypass):
        self.setDriver("GV0", bypass)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_BOOL_UOM}
    ]
    commands = {}

# Node class for zones
class CommandOutput(polyinterface.Node):

    id = "COMMAND_OUTPUT"

    # Override init to handle partition number
    def __init__(self, controller, primary, cmdOutNum):
        super(CommandOutput, self).__init__(controller, primary, _CMD_OUTPUT_ADDR_FORMAT_STRING % cmdOutNum, "Command Output %02d" % cmdOutNum)
        self.partitionNum = 1 # partition 1 only
        self.cmdOutputNum = cmdOutNum  

    # Update ST driver value based on the command received from the EnvisaLink for the zone
    def set_active_state(self):

        # send the DON command for the node - allows node to be scene controller
            self.reportCmd("DON")
            self.setDriver("ST", 1) # Active

    def clear_active_state(self):
        
            self.setDriver("ST", 0) # Off

    # Activate the command output on the DSC Alarm Panel (the listener thread will update the corresponding driver value)
    def cmd_don(self, command):
        
        # Activate the command output
        if self.controller.envisalink.send_command(EVL.CMD_ACTIVATE_CMD_OUTPUT, "%1d%1d" % (self.partitionNum, self.cmdOutputNum)):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to activate command output failed for node %s.", self.address)

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_INDEX_UOM}
    ]
    commands = {
        "DON": cmd_don
    }

# Node class for controller
class AlarmPanel(polyinterface.Controller):

    id = "CONTROLLER"

    def __init__(self, poly):
        super(AlarmPanel, self).__init__(poly)
        self.name = "Alarm Panel"
        self.envisalink = None
        self.userCode = ""
        self.initialPoll = False
        self.numPartitions = 0

    # Create nodes for zones, partitions, and command outputs as specified by the parameters
    def build_nodes(self, numPartitions, numZones, numCmdOuts):

        # create partition nodes for the number of partitions specified
        for i in range(0, numPartitions):
            
            # create a partition node and add it to the node list
            self.addNode(Partition(self, self.address, i+1))

        # create zone nodes for the number of partitions specified
        for i in range(0, numZones):
            
            # create a partition node and add it to the node list
            self.addNode(Zone(self, self.address, i+1))

        # create command output nodes for the number of command outputs specified
        for i in range(0, numCmdOuts):
            
            # create a command output node and add it to the node list
            self.addNode(CommandOutput(self, self.address, i+1))
            
    # Update the driver values based on the command received from the EnvisaLink for the partition
    def update_state_values(self, cmd, data):

        # update the GV0 value (System Alarm State)
        if cmd in (EVL.CMD_2_WIRE_SMOKE_ALARM, EVL.CMD_FIRE_KEY_ALARM, EVL.CMD_AUX_KEY_ALARM, EVL.CMD_PANIC_KEY_ALARM):
            
            # send the DON command to the ISY
            self.reportCmd("DON")
        
            # set the system alarm status value
            if cmd == EVL.CMD_2_WIRE_SMOKE_ALARM:
                self.setDriver("GV0", 1) # Alarming - Smoke
            elif cmd == EVL.CMD_FIRE_KEY_ALARM:
                self.setDriver("GV0", 2) # Alarming - Panic (Fire)
            elif cmd == EVL.CMD_AUX_KEY_ALARM:
                self.setDriver("GV0", 3) # Alarming - Panic (Aux)
            elif cmd == EVL.CMD_PANIC_KEY_ALARM:
                self.setDriver("GV0", 4) # Alarming - Panic (Police)
       
        # Clear the GV0 value (System Alarm State)
        elif cmd in (EVL.CMD_2_WIRE_SMOKE_RESTORED, EVL.CMD_FIRE_KEY_RESTORED, EVL.CMD_AUX_KEY_RESTORED, EVL.CMD_PANIC_KEY_RESTORED):

            # send the DOF command to the ISY
            self.reportCmd("DOF")
 
            # Clear the system alarm state
            self.setDriver("GVO", 0) # Not Alarming

        # update the GV4 (Bell Trouble) value
        elif cmd == EVL.CMD_BELL_TROUBLE:
            self.setDriver("GV4", True) 
        elif cmd == EVL.CMD_BELL_TROUBLE_RESORED:
            self.setDriver("GV4", False) 

        # update the GV5 (Battery Trouble) value
        elif cmd == EVL.CMD_BATTERY_TROUBLE:
            self.setDriver("GV5", True) 
        elif cmd == EVL.CMD_BATTERY_TROUBLE_RESTORED:
            self.setDriver("GV5", False) 

        # update the GV6 (AC Trouble) value
        elif cmd == EVL.CMD_AC_TROUBLE:
            self.setDriver("GV6", True)
        elif cmd == EVL.CMD_AC_TROUBLE_RESTORED:
            self.setDriver("GV6", False)

        # update the GV7 (FTC Trouble) value
        elif cmd == EVL.CMD_FTC_TROUBLE:
            self.setDriver("GV7", True)
        elif cmd == EVL.CMD_FTC_TROUBLE_RESTORED:
            self.setDriver("GV7", False)

        # update the GV8 (Tamper Trouble) value
        elif cmd == EVL.CMD_SYSTEM_TAMPER:
            self.setDriver("GV8", True)
        elif cmd == EVL.CMD_SYSTEM_TAMPER_RESTORED:
            self.setDriver("GV8", False)

    # Trigger the panic fire alarm (the listener thread will update the corresponding driver values)
    def trigger_panic_fire(self, command):
        
        # send the trigger command to EnvisaLink device
        if self.controller.envisalink.send_command(EVL.CMD_TRIGGER_PANIC_ALARM, "1"):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to trigger panic alarm failed for node %s.", self.address)

    # Trigger the panic aux alarm (the listener thread will update the corresponding driver values)
    def trigger_panic_aux(self, command):
        
        # send the trigger command to EnvisaLink device
        if self.controller.envisalink.send_command(EVL.CMD_TRIGGER_PANIC_ALARM, "2"):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to trigger panic alarm failed for node %s.", self.address)

    # Trigger the panic fire alarm (the listener thread will update the corresponding driver values)
    def trigger_panic_police(self, command):
        
        # send the trigger command to EnvisaLink device
        if self.controller.envisalink.send_command(EVL.CMD_TRIGGER_PANIC_ALARM, "3"):
            pass
        else:
            _LOGGER.warning("Call to EnvisaLink to trigger panic alarm failed for node %s.", self.address)

    # Add query here query so the command can reference it
    def query(self):
        
        # just call the Controller class query method
        super(AlarmPanel, self).query()

    # Start the nodeserver
    def start(self):

        _LOGGER.info("Starting envisaink Nodeserver...")

        # remove all notices from ISY Admin Console
        self.removeNoticesAll()

        customParams = self.poly.config["customParams"] 
        configComplete = True

        # get IP address of the EnvisaLink device from custom parameters
        try:
            ip = customParams[_PARM_IP_ADDRESS_NAME]      
        except KeyError:
            _LOGGER.error("Missing IP address for EnvisaLink device in configuration.")

            # add a notification to the nodeserver's notification area in the Polyglot dashboard
            self.addNotice("Please update the '%s' parameter value in the nodeserver custom parameters and restart the nodeserver." % _PARM_IP_ADDRESS_NAME)

            # put a place holder parameter in the configuration with a default value
            customParams.update({_PARM_IP_ADDRESS_NAME: _DEFAULT_IP_ADDRESS})
            configComplete = False
            
        # get the password of the EnvisaLink device from custom parameters
        try:
            password = customParams[_PARM_PASSWORD_NAME]
        except KeyError:
            _LOGGER.error("Missing password for EnvisaLink device in configuration.")

            # add a notification to the nodeserver's notification area in the Polyglot dashboard
            self.addNotice("Please update the '%s' parameter value in the nodeserver custom parameters and restart the nodeserver." % _PARM_PASSWORD_NAME)

            # put a place holder parameter in the configuration with a default value
            customParams.update({_PARM_PASSWORD_NAME: _DEFAULT_PASSWORD})
            configComplete = False

        # get the user code for the DSC panel from custom parameters
        try:
            self.userCode = customParams[_PARM_USER_CODE_NAME]
        except KeyError:
            _LOGGER.error("Missing user code for DSC panel in configuration.")

            # add a notification to the nodeserver's notification area in the Polyglot dashboard
            self.addNotice("Please update the '%s' custom configuration parameter value in the nodeserver configuration and restart the nodeserver." % _PARM_USER_CODE_NAME)

            # put a place holder parameter in the configuration with a default value
            customParams.update({_PARM_USER_CODE_NAME: _DEFAULT_USER_CODE})
            configComplete = False

        # get the optional number of partitions, zones, and command outputs to create nodes for
        try:
            self.numPartitions = int(customParams[_PARM_NUM_PARTITIONS_NAME])
        except (KeyError, ValueError, TypeError):
            self.numPartitions = _DEFAULT_NUM_PARTITIONS

        try:
            numZones = int(customParams[_PARM_NUM_ZONES_NAME])
        except (KeyError, ValueError, TypeError):
            numZones = _DEFAULT_NUM_ZONES

        try:
            numCmdOuts = int(customParams[_PARM_NUM_CMD_OUTS_NAME])
        except (KeyError, ValueError, TypeError):
            numCmdOuts = _DEFAULT_NUM_CMDOUTS

        # if the configuration is not complete, update the custom configurations and stop the nodeserver
        if not configComplete:
            self.poly.saveCustomParams(customParams)
            self.poly.stop()

        else:
            
            # dump the current self._nodes to the log
            #_LOGGER.debug("Current Node Configuration: %s", str(self._nodes))

            #  setup the nodes based on the counts of zones and partition in the configuration parameters
            self.build_nodes(self.numPartitions, numZones, numCmdOuts)

            # Setup the interface to the EnvisaLink device and connect (starts the listener thread)
            self.envisalink = EVL.EnvisaLinkInterface(_LOGGER)
            if self.envisalink.connect(ip, password, self.process_command):

                # perform an initial polling
                # moved initial polling and bypass zone dump to shortPoll
                pass

            else:
            
                # Format errors and exit
                self.addNotice("Could not connect to EnvisaLink device. Please check the custom configuration parameters and restart the nodeserver.")
                self.envisalink = None              
                self.poly.stop()
                       
    # Called when the nodeserver is stopped
    def stop(self):
        
        # shudtown the connection to the EnvisaLink device
        if not self.envisalink is None:
            self.envisalink.shutdown()
        
    # called every long_poll seconds
    def longPoll(self):

        pass
    
    # called every short_poll seconds
    def shortPoll(self):

        # If EnvisaLink interface is connected, perform initial polling and then bypass zone dump
        if not self.envisalink is None:
            
            if not self.initialPoll:
                
                # send the status polling command to the EnvisaLink device
                # Only generates general zone status and trouble LED on keypad
                self.envisalink.send_command(EVL.CMD_STATUS_REPORT)
                self.initialPoll = True

            else:
                
                # dump the bypass zones for each partition
                for part in range(1, self.numPartitions + 1):
                    
                    # get the node for the partition
                    partition = self.nodes[_PART_ADDR_FORMAT_STRING % part]

                    # If the zone bypass dump for the partition has not yet been performed and the partition is ready
                    if not partition.initialBypassZoneDump and partition.readyState:
                            
                        # force a bypass zone dump through the keypad for the partition
                        self.envisalink.send_command(EVL.CMD_SEND_KEYSTROKES, "%1d%s" % (partition.partitionNum, EVL.KEYS_DUMP_BYPASS_ZONES))
                        partition.initialBypassZoneDump = True
        
    # Callback function for listener thread
    def process_command(self, cmd, data):

        retVal = False

        # Pass partition status commands to correct partition node
        if cmd in (
            EVL.CMD_PARTITION_READY,
            EVL.CMD_PARTITION_NOT_READY,
            EVL.CMD_PARTITION_ARMED,
            EVL.CMD_PARTITION_IN_ALARM,
            EVL.CMD_PARTITION_DISARMED,
            EVL.CMD_EXIT_DELAY_IN_PROGRESS,
            EVL.CMD_ENTRY_DELAY_IN_PROGRESS,
            EVL.CMD_CHIME_ENABLED,
            EVL.CMD_CHIME_DISABLED,
            EVL.CMD_USER_OPENING,
            EVL.CMD_USER_CLOSING,
            EVL.CMD_SPECIAL_OPENING,
            EVL.CMD_SPECIAL_CLOSING
        ):

            # get the partition number from the data
            partNum = int(data.decode("ascii")[:1])

            # check if node for partition exists
            for addr in self.nodes:
                if addr == _PART_ADDR_FORMAT_STRING % partNum:

                    # update the driver values of the node from the commands
                    self.nodes[addr].update_state_values(cmd, data)
                    retVal = True
                    break

            # if the command is partition ready for partition 1, also clear any active command output state flags
            if cmd == EVL.CMD_PARTITION_READY and partNum == 1:
                for addr in self.nodes:
                    if addr[:6] == _CMD_OUTPUT_ADDR_FORMAT_STRING[:6]:
                        self.nodes[addr].clear_active_state()
        
        # Pass zone status commands to correct zone node
        elif cmd in (
            EVL.CMD_ZONE_RESTORED,
            EVL.CMD_ZONE_OPEN,
            EVL.CMD_ZONE_ALARM,
            EVL.CMD_ZONE_ALARM_RESTORED
        ):

            # get the zone number from the data
            zoneNum = int(data.decode("ascii")[-3:])

            # check if node for zone
            for addr in self.nodes:
                if addr == _ZONE_ADDR_FORMAT_STRING % zoneNum:
                    
                    # update the driver values of the node from the commands
                    self.nodes[addr].update_state_values(cmd, data)
                    retVal = True
                    break

        # handle panel status commands in the controller node
        elif cmd in (
            EVL.CMD_2_WIRE_SMOKE_ALARM,
            EVL.CMD_2_WIRE_SMOKE_RESTORED,
            EVL.CMD_FIRE_KEY_ALARM,
            EVL.CMD_FIRE_KEY_RESTORED,
            EVL.CMD_AUX_KEY_ALARM,
            EVL.CMD_AUX_KEY_RESTORED,
            EVL.CMD_PANIC_KEY_ALARM,
            EVL.CMD_PANIC_KEY_RESTORED,
            EVL.CMD_BELL_TROUBLE,
            EVL.CMD_BELL_TROUBLE_RESORED,
            EVL.CMD_BATTERY_TROUBLE,
            EVL.CMD_BATTERY_TROUBLE_RESTORED,
            EVL.CMD_AC_TROUBLE,
            EVL.CMD_AC_TROUBLE_RESTORED,
            EVL.CMD_FTC_TROUBLE,
            EVL.CMD_FTC_TROUBLE_RESTORED,
            EVL.CMD_SYSTEM_TAMPER,
            EVL.CMD_SYSTEM_TAMPER_RESTORED
        ):

            # update the driver values of the node from the commands
            self.update_state_values(cmd, data)

            retVal = True

        # handle zone bypass dump
        elif cmd == EVL.CMD_BYPASSED_ZONES_DUMP:
            
            # resequence the hex string in the data to be a big-endian representation
            # of the 64-bit bitfield
            leHexString = data.decode("ascii")
            beHexString = (leHexString[14:]
                           + leHexString[12:14]
                           + leHexString[10:12]
                           + leHexString[8:10]
                           + leHexString[6:8]
                           + leHexString[4:6]
                           + leHexString[2:4]
                           + leHexString[:2])
            
            # convert the big-endian hex string to a 64-bit bitfield representing the
            # bypass status of each of the 64 zones
            bypassFlags = bin(int(beHexString, base=16))[2:].zfill(64)    
            
            # iterate through the zone nodes and set the bypass flag from the bitfield
            for addr in self.nodes:
                node = self.nodes[addr]
                if node.id == "ZONE":
                    node.set_bypass(int(bypassFlags[-node.zoneNum]))
            
            retVal = True

        elif cmd in (EVL.CMD_COMMAND_OUTPUT_PRESSED):
            
            # get the partition and command output number from the data
            partNum = int(data.decode("ascii")[0:1])
            cmdOutNum = int(data.decode("ascii")[1:2])
    
            # set the active state in the corresponding command output node
            for addr in self.nodes:
                if addr == _CMD_OUTPUT_ADDR_FORMAT_STRING % cmdOutNum:
                    self.nodes[addr].set_active_state()
            
            retVal = True

        # handle user code request
        elif cmd in (EVL.CMD_CODE_REQD):

            # send the user code
            self.envisalink.send_command(EVL.CMD_SEND_CODE, self.userCode)

            retVal = True

        return retVal

    drivers = [
        {"driver": "ST", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV0", "value": 0, "uom": _ISY_INDEX_UOM},
        {"driver": "GV4", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV5", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV6", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV7", "value": 0, "uom": _ISY_BOOL_UOM},
        {"driver": "GV8", "value": 0, "uom": _ISY_BOOL_UOM}
    ]

    commands = {
        "QUERY": query,
	    "PANIC_FIRE": trigger_panic_fire,
		"PANIC_AUX": trigger_panic_aux, 
		"PANIC_POLICE": trigger_panic_police
    }

# Main function to establish Polyglot connection
if __name__ == "__main__":
    try:
        polyglot = polyinterface.Interface()
        polyglot.start()
        control = AlarmPanel(polyglot)
        control.runForever()
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
