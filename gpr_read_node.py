#!/usr/bin/env python3
# coding=utf-8

import rospy
import socket
import struct
import json
import requests
import numpy as np
import time

from husky_gpr.msg import GPRTrace

IP_ADDRESS = '192.168.20.221' # EDIT THIS FOR YOUR GPR IP ADDRESS

# Commands to communication with SDK
API_URL = "http://" + IP_ADDRESS + ":8080/api"
NIC_SYSTEM_INFO_CMD = API_URL + "/nic/system_information"
GPR_SYSTEM_INFO_CMD = API_URL + "/nic/gpr/system_information"
DATA_SOCKET_CMD = API_URL + "/nic/gpr/data_socket"
VERSION_CMD = API_URL + "/nic/version"
POWER_CMD = API_URL + "/nic/power"
SETUP_CMD = API_URL + "/nic/setup"
ACQUISITION_CMD = API_URL + "/nic/acquisition"

# GPR settings
POINTS_PER_TRACE = 200              # number of sample points to collect per trace
TIME_SAMPLING_INTERVAL_PS = 100     # time interval between sample points per trace
POINT_STACKS = 4                    # the measurement used to average the trace, must be a power of 2 between 1 and 32768
PERIOD_S = 0.2                      # interval between trigger events when the GPR trigger mode is set to "Free"
FIRST_BREAK_POINT = 20
# FREQUENCY_MHZ = 500.0

# Configuration for the following put commands
POWER_ON_CONFIGURATION = {"data": json.dumps({'state': 2})}
POWER_OFF_CONFIGURATION = {"data": json.dumps({'state': 2})}
START_ACQUISITION_CONFIGURATION = {"data": json.dumps({'state': 1})}
STOP_ACQUISITION_CONFIGURATION = {"data": json.dumps({'state': 0})}

# Trace settings
HEADER_SIZE_BYTES = 20
POINT_SIZE_BYTES = 4


class trace_reader(object):
    def __init__(self):
        
        # rospy.init_node('gpr_reader', anonymous=True)
        self.pub = rospy.Publisher('/gpr/traces', GPRTrace, queue_size = 10)
        self.gpr_data = GPRTrace()
        self.gpr_temp_data = b''
        self.gpr_data_size_bytes = HEADER_SIZE_BYTES + (POINTS_PER_TRACE * POINT_SIZE_BYTES)
        self.all_data = np.array([])
        self.window_time_shift_ps = -55000
        self.setup_nic_configuration = {'data': json.dumps(
            {"gpr0": {"parameters": {'points_per_trace': POINTS_PER_TRACE,
                                    'window_time_shift_ps': self.window_time_shift_ps,
                                    'point_stacks': POINT_STACKS,
                                    'time_sampling_interval_ps': TIME_SAMPLING_INTERVAL_PS
                                    # 'frequency_MHz': FREQUENCY_MHZ
                                    }},
            "timer": {"parameters": {"period_s": PERIOD_S}}})}
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def read_data(self):
        try:
            self.gpr_temp_data = self.gpr_temp_data + self.data_socket.recv(self.gpr_data_size_bytes)
        except:
            print('The socket connection was severed. Shutting down the socket.')
            self.data_socket.close()
            return

        num_traces_received = int(len(self.gpr_temp_data) / self.gpr_data_size_bytes)
        for i in range(0, num_traces_received):
            (tv_sec, tv_nsec, trace_num, status, stacks, header_size), s = struct.unpack('<LLLLHH',
                                                                                        self.gpr_temp_data[0:HEADER_SIZE_BYTES]), \
                                                                        self.gpr_temp_data[HEADER_SIZE_BYTES:self.gpr_data_size_bytes] 
            self.gpr_temp_data = self.gpr_temp_data[self.gpr_data_size_bytes:]
            
            
            data = np.frombuffer(s, dtype=np.float32) #[0:40]
            temp_mat = data.reshape((data.size,1))
            if self.all_data.size == 0:
                self.all_data = temp_mat
            else:
                self.all_data = np.concatenate((self.all_data, temp_mat), axis=1)

        self.gpr_data.trace = (self.all_data.flatten()).tolist()
        self.gpr_data.header.stamp = rospy.Time.now()
        self.all_data = np.array([])
        self.gpr_temp_data = b''
        self.pub.publish(self.gpr_data)


    def initialize_gpr(self):
        api_response = self.get_requests(API_URL, "API")
        if api_response is None or not api_response['data']['name'] == "NIC-500 SDK":
            print("Not in NIC SDK Mode")
            quit()

        # put_requests(ACQUISITION_CMD, STOP_ACQUISITION_CONFIGURATION, "Stop Acquisition")
        power_on_response = self.put_requests(POWER_CMD, POWER_ON_CONFIGURATION, "Power")
        # Confirm the GPR was able to turn on
        if power_on_response is None:
            quit()

        # Use the GPR System Information command to get system information
        gpr_system_json_response = self.get_requests(GPR_SYSTEM_INFO_CMD, "GPR System Information")
        # Confirm we've received a successful response
        if gpr_system_json_response is None:
            quit()

        gpr_system_info = gpr_system_json_response['data']['gpr']
        
        if gpr_system_info['window_time_shift_reference_ps'] is not None:
            window_time_shift_reference_ps = int(gpr_system_info['window_time_shift_reference_ps'])
            self.window_time_shift_ps = window_time_shift_reference_ps - (FIRST_BREAK_POINT * TIME_SAMPLING_INTERVAL_PS)
        
        # Use the GPR data socket command to get data socket's port
        data_socket_json_response = self.get_requests(DATA_SOCKET_CMD, "GPR Data Socket")
        # Get the data socket port
        data_socket_port = data_socket_json_response['data']['data_socket']['port']
        # Use the port to connect to the data socket
        
        self.data_socket.connect((IP_ADDRESS, data_socket_port))
        setup_nic_json_response = self.put_requests(SETUP_CMD, self.setup_nic_configuration, "Setup")
        # Confirm we've received a successful response
        if setup_nic_json_response is None:
            data_socket.close()
            quit()

        # Use the GPR data acquisition command to start data collection
        start_acquisition_json_response = self.put_requests(ACQUISITION_CMD, START_ACQUISITION_CONFIGURATION, "Start Acquisition")
        # Confirm we've received a successful response
        if start_acquisition_json_response is None:
            data_socket.close()
            quit()
    def destructor(self):
        # Use the GPR data acquisition command to stop data collection
        stop_acquisition_json_response = self.put_requests(ACQUISITION_CMD, STOP_ACQUISITION_CONFIGURATION, "Stop Acquisition")
        power_on_response = self.put_requests(POWER_CMD, POWER_OFF_CONFIGURATION, "Power")
        # Close data socket
        self.data_socket.close()
        print("We've shut down the GPR")

    def get_requests(self, command, command_str_name):
        """
        Perform a get request to retrieve data from a resource.
        @param command: URL for the request command
        @type command: str
        @param command_str_name: Name of the command
        @type command_str_name: str
        @return: response in json format
        @rtype: JSON or None when request failed
        """
        json_response = None
        try:
            response = requests.get(command)
            json_response = json.loads(response.content)
            print("Response from {} command: {}\n".format(command_str_name, json_response["status"]["message"]))
        except ValueError as err:
            print("Unable to decode JSON: {}\n".format(err))
        except KeyError:
            print("Response from {} command: {}\n".format(command_str_name, json_response["success"]))
        return json_response
    
    def put_requests(self, command, data, command_str_name):
        """
        Perform a put request to change the resource’s data.
        @param command: URL for the request command
        @type command: str
        @param data: Data to send to the command
        @type data: dict
        @param command_str_name: Name of the command
        @type command_str_name: str
        @return: response in json format
        @rtype: JSON or None when request failed
        """
        json_response = None
        try:
            response = requests.put(command, data=data)
            json_response = json.loads(response.content)
            print("Response from {} command: {}\n".format(command_str_name, json_response["status"]["message"]))
        except ValueError as err:
            print("Unable to decode JSON: {}\n".format(err))
        
        if json_response["status"]["status_code"] != 0:
            print("Command failed: {}".format(json_response["status"]["message"]))
            json_response = None

        return json_response


if __name__ == '__main__':
    rospy.init_node('gpr_read_node', anonymous=True)
    
    gpr = trace_reader()
    gpr.initialize_gpr()
    rospy.on_shutdown(gpr.destructor)

    while not rospy.is_shutdown():
        gpr.read_data()
