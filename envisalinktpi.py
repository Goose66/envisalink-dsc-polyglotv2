#!/usr/bin/python3
# Interface to EnvisaLink 3/4 TPI (DSC)

import socket
import logging
import threading

# Commands to control DSC Alarm Panel
CMD_STATUS_REPORT = b"001"
CMD_NETWORK_LOGIN = b"005"
CMD_SET_TIME = b"010"
CMD_ACTIVATE_CMD_OUTPUT = b"020"
CMD_ARM_PARTITION = b"030"
CMD_ARM_PARTITION_STAY = b"031"
CMD_ARM_PARTITION_NO_ENTRY_DELAY = b"032"
CMD_ARM_PARTITION_WITH_CODE = b"033"
CMD_DISARM_PARTITION = b"040"
CMD_TIMESTAMP_CONTROL = b"055"
CMD_TIME_BROADCAST_CONTROL = b"056"
CMD_TEMP_BROADCAST_CONTROL = b"057"
CMD_TRIGGER_PANIC_ALARM = b"060"
CMD_SEND_KEYSTROKE = b"070"
CMD_SEND_KEYSTROKES = b"071"
CMD_ENTER_USER_CODE_PROG_5 = b"072"
CMD_ENTER_USER_CODE_PROG_6 = b"073"
CMD_KEEP_ALIVE = b"074"
CMD_RQST_HVAC_BDCST = b"080"
CMD_SEND_CODE= b"200"

# Response commands sent by DSC Alarm Panel
CMD_ACK = b"500"
CMD_ERR= b"501"
CMD_SYSTEM_ERROR = b"502"
CMD_LOGIN_INTERACTION = b"505"
CMD_LED_STATE = b"510"
CMD_LED_FLASH_STATE = b"511"
CMD_TIME_BROADCAST = b"550"
CMD_RING_DETECTED = b"560"
CMD_INDOOR_TEMP_BROADCAST = b"561"
CMD_OUTDOOR_TEMP_BROADCAST = b"562"
CMD_ZONE_ALARM = b"601"
CMD_ZONE_ALARM_RESTORED = b"602"
CMD_ZONE_TAMPER = b"603"
CMD_ZONE_TAMPER_RESTORED = b"604"
CMD_ZONE_FAULT = b"605"
CMD_ZONE_FAULT_RESTORED = b"606"
CMD_ZONE_OPEN = b"609"
CMD_ZONE_RESTORED = b"610"
CMD_ZONE_TIMER_DUMP = b"615"
CMD_BYPASSED_ZONES_DUMP = b"616"
CMD_DURESS_ALARM = b"620"
CMD_FIRE_KEY_ALARM = b"621"
CMD_FIRE_KEY_RESTORED = b"622"
CMD_AUX_KEY_ALARM = b"623"
CMD_AUX_KEY_RESTORED = b"624"
CMD_PANIC_KEY_ALARM = b"625"
CMD_PANIC_KEY_RESTORED = b"626"
CMD_2_WIRE_SMOKE_ALARM = b"631"
CMD_2_WIRE_SMOKE_RESTORED = b"632"
CMD_PARTITION_READY = b"650"
CMD_PARTITION_NOT_READY = b"651"
CMD_PARTITION_ARMED = b"652"
CMD_PARTITION_READY_FORCE_ARM = b"653"
CMD_PARTITION_IN_ALARM = b"654"
CMD_PARTITION_DISARMED = b"655"
CMD_EXIT_DELAY_IN_PROGRESS = b"656"
CMD_ENTRY_DELAY_IN_PROGRESS = b"657"
CMD_KEYPAD_LOCKOUT = b"658"
CMD_PARTITION_FAILED_TO_ARM = b"659"
CMD_PGM_OUTPUT_IN_PROGRESS = b"660"
CMD_CHIME_ENABLED = b"663"
CMD_CHIME_DISABLED = b"664"
CMD_INVALID_ACCESS_CODE = b"670"
CMD_FUNCTION_NOT_AVAILABLE = b"671"
CMD_FAILURE_TO_ARM = b"672"
CMD_PARTITION_IS_BUSY = b"673"
CMD_SYSTEM_ARMING_IN_PROGRESS = b"674"
CMD_SYSTEM_IN_INSTALLERS_MODE = b"680"
CMD_USER_CLOSING = b"700"
CMD_SPECIAL_CLOSING = b"701"
CMD_PARTIAL_CLOSING = b"702"
CMD_USER_OPENING = b"750"
CMD_SPECIAL_OPENING = b"751"
CMD_BATTERY_TROUBLE = b"800"
CMD_BATTERY_TROUBLE_RESTORED = b"801"
CMD_AC_TROUBLE = b"802"
CMD_AC_TROUBLE_RESTORED = b"803"
CMD_BELL_TROUBLE = b"806"
CMD_BELL_TROUBLE_RESORED = b"807"
CMD_FTC_TROUBLE = b"814"
CMD_FTC_TROUBLE_RESTORED = b"815"
CMD_BUFFER_NEAR_FULL = b"816"
CMD_SYSTEM_TAMPER = b"829"
CMD_SYSTEM_TAMPER_RESTORED = b"830"
CMD_TROUBLE_LED_ON = b"840"
CMD_TROUBLE_LED_OFF = b"841"
CMD_FIRE_TROUBLE = b"842"
CMD_FIRE_TROUBLE_RESTORED = b"843"
CMD_VERBOSE_TROUBLE_STATUS = b"849"
CMD_CODE_REQD = b"900"
CMD_COMMAND_OUTPUT_PRESSED = b"912"
CMD_MASTER_CODE_REQD = b"921"
CMD_INSTALLER_CODE_REQD = b"922"

# Keypad keystrokes for specific commands to be sent with CMD_SEND_KEYSTROKES
KEYS_TOGGLE_DOOR_CHIME = "*4"
KEYS_DUMP_BYPASS_ZONES = "*1#"

# Error codes returned in data for CMD_SYSTEM_ERROR command
_SYS_ERROR_CODES = {
    "000": "No Error.",
    "001": "Receive Buffer Overrun (a command is received while another is still being processed).",
    "002": "Receive Buffer Overflow.",
    "003": "Transmit Buffer Overflow.",
    "010": "Keybus Transmit Buffer Overrun.",
    "011": "Keybus Transmit Time Timeout.",
    "012": "Keybus Transmit Mode Timeout.",
    "013": "Keybus Transmit Keystring Timeout.",
    "014": "Keybus Interface Not Functioning (the TPI cannot communicate with the security system).",
    "015": "Keybus Busy (Attempting to Disarm or Arm with user code).",
    "016": "Keybus Busy – Lockout (The panel is currently in Keypad Lockout – too many disarm attempts).",
    "017": "Keybus Busy – Installers Mode (Panel is in installers mode, most functions are unavailable).",
    "018": "Keybus Busy – General Busy (The requested partition is busy).",
    "020": "API Command Syntax Error.",
    "021": "API Command Partition Error (Requested Partition is out of bounds).",
    "022": "API Command Not Supported.",
    "023": "API System Not Armed (sent in response to a disarm command).",
    "024": "API System Not Ready to Arm (system is either not-secure, in exit-delay, or already armed).",
    "025": "API Command Invalid Length.",
    "026": "API User Code not Required.",
    "027": "API Invalid Characters in Command (no alpha characters are allowed except for checksum)."
}

_EVL_TCP_PORT = 4025

_msgBuffer = bytearray()
_BUFFER_SIZE = 1024

class EnvisaLinkInterface(object):

    # Primary constructor method
    def __init__(self, logger=None):

        # declare instance variables
        self._evlConnection = None
        self._listenerThread = None
        self._lastCmd = b''
        self._sendLock = threading.Lock()

        # setup basic console logger for debugging
        if logger is None:
            logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.DEBUG)
            self._logger = logging.getLogger() # Root logger
        else:
            self._logger = logger

    def connect(self, deviceAddr, password, commandCallback=None):
        
        if self._connect_evl(deviceAddr, password):

            self._logger.debug("Starting listener thread...")
            
            # setup thread for listener for commands from EnvisaLink with specified callback function
            self._listenerThread = threading.Thread(target=self._command_listener, args=(commandCallback,))
            self._listenerThread.daemon = True
            try:
                self._listenerThread.start()
            except:
                self._logger.error("Error starting listener thread.")
                raise

            return True
        
        else:
            
            return False

    # Connect to EnvisaLink and login
    def _connect_evl(self, deviceAddr, password):

        self._logger.debug("Connecting to EnvisaLink device...")

        # set initial timeout value for socket connection during login sequence
        initialTimeout = 0.5

        # connect to the EnvisaLink device
        self._evlConnection = connect(deviceAddr, initialTimeout, self._logger)
        if self._evlConnection is None:
            self._logger.error("Unable to establish connection with EnvisaLink device.")
            return False

        # wait for password request
        cmd_seq = get_next_cmd_seq(self._evlConnection, self._logger)
        if cmd_seq is None or (cmd_seq[0] != CMD_LOGIN_INTERACTION or cmd_seq[1] != b"3"):
            self._logger.error("Invalid sequence received from EnvisaLink upon connection: %s", cmd_seq)
            self._evlConnection.close()
            return False

        # send password to EVL
        send_cmd(self._evlConnection, CMD_NETWORK_LOGIN, password.encode("ascii"), self._logger)
        cmd_seq = get_next_cmd_seq(self._evlConnection, self._logger)
        if cmd_seq is None or (cmd_seq[0] != CMD_ACK or cmd_seq[1] != CMD_NETWORK_LOGIN):
            self._logger.error("Failure in sending password to EnvisaLink. Received sequence: %s", cmd_seq)
            self._evlConnection.close()
            return False
        
        # wait for login verification
        cmd_seq = get_next_cmd_seq(self._evlConnection, self._logger)
        if cmd_seq is None or (cmd_seq[0] != CMD_LOGIN_INTERACTION or cmd_seq[1] not in (b"0", b"1")):
            self._logger.error("Invalid sequence received from EnvisaLink on login: %s", cmd_seq)
            self._evlConnection.close()
            return False

        elif cmd_seq[1] == b"0":
            self._logger.error("Invalid password specified. Login failed.")
            self._evlConnection.close()
            return False

        # send a command to the EnvisaLink to send time broadcasts (every 4 minutes) to be used as a keepalive
        send_cmd(self._evlConnection, CMD_TIME_BROADCAST_CONTROL, b"1", self._logger)
        cmd_seq = get_next_cmd_seq(self._evlConnection, self._logger)
        if cmd_seq is None or (cmd_seq[0] != CMD_ACK or cmd_seq[1] != CMD_TIME_BROADCAST_CONTROL):
            self._logger.error("Failure in setting time broadcasts on EnvisaLink. Received sequence: %s", cmd_seq)
            self._evlConnection.close()
            return False

        # set a longer timeout on the socket for remaining calls (5 minutes)
        self._evlConnection.settimeout(300)

        return True

    # Monitors the EnvisaLink for TPI commands and updates node status in the nodeserver
    # To be executed on seperate, non-blocking thread
    def _command_listener(self, commandCallback):

        self._logger.debug("In command_listener()...")

        # loop continuously and listen for TPI commands from EnvisaLink device over TCP connection
        while True:

            # get next status message
            cmd_seq = get_next_cmd_seq(self._evlConnection, self._logger)

            # if the cmd_seq is blank, then an error occurred (connection occured or timeout)
            if cmd_seq is None:
                self._logger.error("No data returned by EnvisaLink device. Listener thread terminated.")
                return

            # extract the command and data
            cmd = cmd_seq[0]
            data = cmd_seq[1]

            # determine action to take based on the command
            if cmd == CMD_TIME_BROADCAST:
                
                # time broadcasts sent every four minutes and used as keep-alive
                # (timeout set to 5 minutes). Just ignore.
                pass
            
            elif cmd == CMD_ERR:

                # log bad checksum error
                self._logger.warning("(%s) Bad checksum error returned. Last Command: %s", cmd.decode("ascii"), self._lastCmd.decode("ascii"))

            elif cmd == CMD_SYSTEM_ERROR:

                # log the system error
                self._logger.warning("(%s) Envisalink returned system error code %s - %s.", cmd.decode("ascii"), data.decode("ascii"), _SYS_ERROR_CODES[data.decode("ascii")])            

            elif cmd == CMD_ACK:

                # if the command was CMD_TIMESTAMP_CONTROL, then the nodeserver is trying to gracefully
                # shutdown the thread
                if data == CMD_TIME_BROADCAST_CONTROL:

                    self._logger.debug("command_listener() being shutdown.")
                    return

                # if the command being acknowledged is the last command sent, then all is well
                elif data == self._lastCmd:

                    pass

                # otherwise log an error
                else:
                    self._logger.warning("(%s) Command acknowledged out of sequence. Last Command: %s, Last Acknowledged: %s", cmd.decode("ascii"), self._lastCmd.decode("ascii"), data.decode("ascii"))
                  
            # otherwise, pass the command and data to the callback function for handling
            else:

                # call status update callback function
                if not commandCallback is None:
                    if not commandCallback(cmd, data):
                        self._logger.debug("Unhandled command received from EnvisaLink. Command: %s, Data: %s", cmd.decode("ascii"), data.decode("ascii"))

    # Send command to Envisalink - manage thread lock to prevent stepping on thread
    # Parameters:   cmd - bytearray with 3 digit command
    #               data - data string
    # Returns:      True if command succesful
    def send_command(self, cmd, data=""):
           
        self._logger.debug("Sending command to EnvisaLink device: Command %s, Data %s", cmd.decode("ascii"), data)

        # acquire the send lock
        if self._sendLock.acquire():

            try:
                send_cmd(self._evlConnection, cmd, data.encode("ascii"), self._logger)
            except:
                raise
            finally:

                # release the lock
                self._sendLock.release()

            self._lastCmd = cmd
            return True
        else:
            self._logger.debug("Cannot acquire lock. Send failed.")
            return False

    # Shutdown listener thread and connection
    def shutdown(self):
           
        self._logger.debug("In shutdown()...")

        # acquire the send lock
        if self._sendLock.acquire():

            # Send a 
            try:
                send_cmd(self._evlConnection, CMD_TIME_BROADCAST_CONTROL, b"0", self._logger)
            except:
                raise
            finally:
                # release the lock
                self._sendLock.release()

            # give the listener thread a couple of seconds to end
            self._listenerThread.join(2.0)

        else:
            self._logger.debug("Cannot acquire lock. Shutdown failed.")

        # close the connection
        self._evlConnection.close()

# Establish a TCP connection to device
# Parameters:   ipAddr - IP4 address of device
# Returns:      connected socket
def connect(ipAddr, timeout, logger):

    logger.debug("In connect()...")        

    # Open a socket for communication with the device at the specified address
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ipAddr, _EVL_TCP_PORT))
    except (socket.error, socket.herror, socket.gaierror) as e:
        logger.error("Socket error on connect: %s", str(e))
        s.close()
        return None
    except:
        raise
    
    return s

# Send a command to the device
# Parameters:   s- socket for EVL
#               cmd - bytes for command code
#               data - bytes for data
def send_cmd(s, cmd, data, logger):

    logger.debug("In send_cmd(): Command %s, Data %s", cmd.decode("ascii"), data.decode("ascii"))

    # setup the command sequence from the command and data 
    cmd_seq = cmd + data + calc_checksum(cmd, data) + b"\r\n"

    try:
        s.sendall(cmd_seq)

    except socket.timeout:
        logger.error("Unable to communication with EnvisaLink - connection closed.")
        s.close()
    except socket.error as e:
        logger.error("Connection to EnvisaLink unexpectedly closed. Socket error: %s", str(e))
        s.close()
    except:
        raise

# Gets the next full command sequence (delimited by CR/LF pair) from the device
# Parameters:   s- socket for EVL
# Returns:      tuple with command and data bytes or None if no data
def get_next_cmd_seq(s, logger):

    logger.debug("In get_next_cmd_seq()...")

    global _msgBuffer

    # If there is no full command sequence in the buffer, get data from the socket
    if _msgBuffer.count(b"\r\n") == 0:
        
        try:
            msg = s.recv(_BUFFER_SIZE)
        except socket.timeout:
            logger.debug("recv() timed out - no data returned.")
            return None
        except socket.error as e:
            logger.error("TCP Connection to EnvisaLink unexpectedly closed. Socket error: %s", str(e))
            s.close()
            raise
        except:
            raise

        if len(msg) == 0:
            logger.error("TCP Connection to EnvisaLink unexpectedly closed.")
        else:
            _msgBuffer += msg

    # check to see if there is a command sequence in the buffer
    idx = _msgBuffer.find(b"\r\n")
    if idx > -1:
        
        # extract the command sequence from the buffer
        seq = _msgBuffer[:idx]
        _msgBuffer = _msgBuffer[idx+2:] # skip CR/LF pair

        # get the command and data from the sequence
        cmd = seq[:3]
        data = seq[3:-2]

        # log the received command
        logger.debug("Command recived from EnvisaLink: Command %s, Data %s", cmd.decode("ascii"), data.decode("ascii"))

        # return a tuple with the command and data (ignore checksum)
        return (cmd, data)

    # otherwise return empty
    else:
        return None    

# Calculate checksum for a TPI command
# Parameters:   cmd - bytes for command code
#               data - bytes for data
# Returns:      bytes for ASCII codes for hex digits of checksum
def calc_checksum(cmd, data):
    
    val = 0

    # Add up ASCII codes for command characters
    for c in cmd:
        val += c

    # Add up ASCII codes for data characters
    for c in data:
        val += c

    # Mask off all bits but the last 8 and get the ASCII characters for the hex value
    val = val & 0xFF
    return hex(val)[2:4].upper().encode("ascii")