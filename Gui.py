#!/usr/bin/env python3
from __future__ import print_function
import struct
import sys
import argparse
import math
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import re

PythonGateways = 'pythonGateways/'
sys.path.append(PythonGateways)

import VsiCommonPythonApi as vsiCommonPythonApi
import VsiTcpUdpPythonGateway as vsiEthernetPythonGateway


class MySignals:
    def __init__(self):
        # Inputs
        self.headX = 0
        self.headY = 0
        self.headZ = 0
        self.errorCode = 0
        self.nozzleTemp = 0
        self.bedTemp = 0
        self.filamentRemaining = 0
        self.printerState = 0

        # Outputs
        self.dashboardStart = 0
        self.dashboardRefill = 0
        self.dashboardPause = 0
        self.dashboardEmergencyStop = 0



srcMacAddress = [0x12, 0x34, 0x56, 0x78, 0x9a, 0xbc]
ProcessorComponentMacAddress = [0x12, 0x34, 0x56, 0x78, 0x90, 0x02]
InputComponentMacAddress = [0x12, 0x34, 0x56, 0x78, 0x90, 0x01]
srcIpAddress = [192, 168, 1, 1]
ProcessorComponentIpAddress = [192, 168, 2, 11]
InputComponentIpAddress = [192, 168, 2, 10]

ProcessorComponentSocketPortNumber0 = 9001
InputComponentSocketPortNumber1 = 9002

DashboardComponent0 = 0
DashboardComponent1 = 1


# Start of user custom code region. Please apply edits only within these regions:  Global Variables & Definitions

# End of user custom code region. Please don't edit beyond this point.
class DashboardComponent:

    def __init__(self, args):
        self.componentId = 2
        self.localHost = args.server_url
        self.domain = args.domain
        self.portNum = 50103
        
        self.simulationStep = 0
        self.stopRequested = False
        self.totalSimulationTime = 0
        
        self.receivedNumberOfBytes = 0
        self.receivedPayload = []

        self.numberOfPorts = 2
        self.clientPortNum = [0] * self.numberOfPorts
        self.receivedDestPortNumber = 0
        self.receivedSrcPortNumber = 0
        self.expectedNumberOfBytes = 0
        self.mySignals = MySignals()

        # Start of user custom code region. Please apply edits only within these regions:  Constructor

        # End of user custom code region. Please don't edit beyond this point.



    def mainThread(self):
        dSession = vsiCommonPythonApi.connectToServer(self.localHost, self.domain, self.portNum, self.componentId)
        vsiEthernetPythonGateway.initialize(dSession, self.componentId, bytes(srcMacAddress), bytes(srcIpAddress))
        try:
            vsiCommonPythonApi.waitForReset()

            # Start of user custom code region. Please apply edits only within these regions:  After Reset

            # End of user custom code region. Please don't edit beyond this point.
            self.updateInternalVariables()

            if(vsiCommonPythonApi.isStopRequested()):
                raise Exception("stopRequested")
            self.establishTcpUdpConnection()
            nextExpectedTime = vsiCommonPythonApi.getSimulationTimeInNs()
            while(vsiCommonPythonApi.getSimulationTimeInNs() < self.totalSimulationTime):
                ###############
                class GCodeParser:
                    def __init__(self):
                        self.lines = []
                        self.current_position = [0, 0, 0]
                        self.trajectory = []
                        
                    def parse_gcode_file(self, filename):
                        """Parse G-code file and extract movement commands"""
                        with open(filename, 'r') as file:
                            for line in file:
                                self.parse_gcode_line(line.strip())
                    
                    def parse_gcode_line(self, line):
                        """Parse individual G-code line"""
                        if line.startswith('G') and not line.startswith('G28'):  # Skip homing commands
                            # Extract coordinates
                            x_match = re.search(r'X([-\d.]+)', line)
                            y_match = re.search(r'Y([-\d.]+)', line)
                            z_match = re.search(r'Z([-\d.]+)', line)
                            
                            x = float(x_match.group(1)) if x_match else self.current_position[0]
                            y = float(y_match.group(1)) if y_match else self.current_position[1]
                            z = float(z_match.group(1)) if z_match else self.current_position[2]
                            
                            # Add to trajectory
                            self.trajectory.append([x, y, z])
                            self.current_position = [x, y, z]
                
                class GCodeVisualizer:
                    def __init__(self):
                        self.fig = plt.figure(figsize=(12, 8))
                        self.ax = self.fig.add_subplot(111, projection='3d')
                        self.parser = GCodeParser()
                        
                    def visualize_gcode(self, filename):
                        """Main method to parse and visualize G-code"""
                        self.parser.parse_gcode_file(filename)
                        self.plot_trajectory()
                        
                    def plot_trajectory(self):
                        """Plot the extracted trajectory"""
                        if not self.parser.trajectory:
                            print("No trajectory data to plot")
                            return
                            
                        trajectory = np.array(self.parser.trajectory)
                        
                        self.ax.clear()
                        self.ax.plot(trajectory[:, 0], trajectory[:, 1], trajectory[:, 2], 
                                    'b-', linewidth=2, label='Tool Path')
                        self.ax.scatter(trajectory[0, 0], trajectory[0, 1], trajectory[0, 2], 
                                       c='g', s=100, label='Start')
                        self.ax.scatter(trajectory[-1, 0], trajectory[-1, 1], trajectory[-1, 2], 
                                       c='r', s=100, label='End')
                        
                        self.ax.set_xlabel('X Axis')
                        self.ax.set_ylabel('Y Axis')
                        self.ax.set_zlabel('Z Axis')
                        self.ax.set_title('G-code Tool Path Visualization')
                        self.ax.legend()
                        self.ax.grid(True)
                        
                        plt.tight_layout()
                        plt.show(block=False)
                        plt.pause(0.1)
                
                # In the main component class (generated by VSI)
                class GCodeViewerComponent:
                    def __init__(self):
                        self.visualizer = GCodeVisualizer()
                        self.gcode_file_path = "path/to/your/file.gcode"
                        
                    def mainThread(self):
                        """Main thread that runs the visualization"""
                        try:
                            # Load and visualize G-code
                            self.visualizer.visualize_gcode(self.gcode_file_path)
                            
                            # Keep the visualization alive
                            while True:
                                plt.pause(0.1)
                                
                        except Exception as e:
                            print(f"Error in visualization: {e}")
                            
                    def receive_gcode_command(self, command):
                        """Handle incoming G-code commands via Ethernet"""
                        if command.startswith("LOAD_GCODE:"):
                            filename = command.split(":")[1]
                            self.visualizer.visualize_gcode(filename)
                ###############
                # Start of user custom code region. Please apply edits only within these regions:  Inside the while loop

                # End of user custom code region. Please don't edit beyond this point.

                self.updateInternalVariables()

                if(vsiCommonPythonApi.isStopRequested()):
                    raise Exception("stopRequested")

                if(vsiEthernetPythonGateway.isTerminationOnGoing()):
                    print("Termination is on going")
                    break

                if(vsiEthernetPythonGateway.isTerminated()):
                    print("Application terminated")
                    break

                receivedData = vsiEthernetPythonGateway.recvEthernetPacket(ProcessorComponentSocketPortNumber0)
                if(receivedData[3] != 0):
                    self.decapsulateReceivedData(receivedData)

                receivedData = vsiEthernetPythonGateway.recvEthernetPacket(InputComponentSocketPortNumber1)
                if(receivedData[3] != 0):
                    self.decapsulateReceivedData(receivedData)

                # Start of user custom code region. Please apply edits only within these regions:  Before sending the packet

                # End of user custom code region. Please don't edit beyond this point.

                #Send ethernet packet to InputComponent
                self.sendEthernetPacketToInputComponent()

                # Start of user custom code region. Please apply edits only within these regions:  After sending the packet

                # End of user custom code region. Please don't edit beyond this point.

                print("\n+=DashboardComponent+=")
                print("  VSI time:", end = " ")
                print(vsiCommonPythonApi.getSimulationTimeInNs(), end = " ")
                print("ns")
                print("  Inputs:")
                print("\theadX =", end = " ")
                print(self.mySignals.headX)
                print("\theadY =", end = " ")
                print(self.mySignals.headY)
                print("\theadZ =", end = " ")
                print(self.mySignals.headZ)
                print("\terrorCode =", end = " ")
                print(self.mySignals.errorCode)
                print("\tnozzleTemp =", end = " ")
                print(self.mySignals.nozzleTemp)
                print("\tbedTemp =", end = " ")
                print(self.mySignals.bedTemp)
                print("\tfilamentRemaining =", end = " ")
                print(self.mySignals.filamentRemaining)
                print("\tprinterState =", end = " ")
                print(self.mySignals.printerState)
                print("  Outputs:")
                print("\tdashboardStart =", end = " ")
                print(self.mySignals.dashboardStart)
                print("\tdashboardRefill =", end = " ")
                print(self.mySignals.dashboardRefill)
                print("\tdashboardPause =", end = " ")
                print(self.mySignals.dashboardPause)
                print("\tdashboardEmergencyStop =", end = " ")
                print(self.mySignals.dashboardEmergencyStop)
                print("\n\n")

                self.updateInternalVariables()

                if(vsiCommonPythonApi.isStopRequested()):
                    raise Exception("stopRequested")
                nextExpectedTime += self.simulationStep

                if(vsiCommonPythonApi.getSimulationTimeInNs() >= nextExpectedTime):
                    continue

                if(nextExpectedTime > self.totalSimulationTime):
                    remainingTime = self.totalSimulationTime - vsiCommonPythonApi.getSimulationTimeInNs()
                    vsiCommonPythonApi.advanceSimulation(remainingTime)
                    break

                vsiCommonPythonApi.advanceSimulation(nextExpectedTime - vsiCommonPythonApi.getSimulationTimeInNs())

            if(vsiCommonPythonApi.getSimulationTimeInNs() < self.totalSimulationTime):
                vsiEthernetPythonGateway.terminate()
        except Exception as e:
            if str(e) == "stopRequested":
                print("Terminate signal has been received from one of the VSI clients")
                # Advance time with a step that is equal to "simulationStep + 1" so that all other clients
                # receive the terminate packet before terminating this client
                vsiCommonPythonApi.advanceSimulation(self.simulationStep + 1)
            else:
                print(f"An error occurred: {str(e)}")
        except:
            # Advance time with a step that is equal to "simulationStep + 1" so that all other clients
            # receive the terminate packet before terminating this client
            vsiCommonPythonApi.advanceSimulation(self.simulationStep + 1)




    def establishTcpUdpConnection(self):
        if(self.clientPortNum[DashboardComponent0] == 0):
            self.clientPortNum[DashboardComponent0] = vsiEthernetPythonGateway.tcpConnect(bytes(ProcessorComponentIpAddress), ProcessorComponentSocketPortNumber0)

        if(self.clientPortNum[DashboardComponent1] == 0):
            self.clientPortNum[DashboardComponent1] = vsiEthernetPythonGateway.tcpConnect(bytes(InputComponentIpAddress), InputComponentSocketPortNumber1)

        if(self.clientPortNum[DashboardComponent1] == 0):
            print("Error: Failed to connect to port: ProcessorComponent on TCP port: ") 
            print(ProcessorComponentSocketPortNumber0)
            exit()

        if(self.clientPortNum[DashboardComponent1] == 0):
            print("Error: Failed to connect to port: InputComponent on TCP port: ") 
            print(InputComponentSocketPortNumber1)
            exit()



    def decapsulateReceivedData(self, receivedData):
        self.receivedDestPortNumber = receivedData[0]
        self.receivedSrcPortNumber = receivedData[1]
        self.receivedNumberOfBytes = receivedData[3]
        self.receivedPayload = [0] * (self.receivedNumberOfBytes)

        for i in range(self.receivedNumberOfBytes):
            self.receivedPayload[i] = receivedData[2][i]

        if(self.receivedSrcPortNumber == ProcessorComponentSocketPortNumber0):
            print("Received packet from ProcessorComponent")
            receivedPayload = bytes(self.receivedPayload)
            self.mySignals.headX, receivedPayload = self.unpackBytes('d', receivedPayload)

            self.mySignals.headY, receivedPayload = self.unpackBytes('d', receivedPayload)

            self.mySignals.headZ, receivedPayload = self.unpackBytes('d', receivedPayload)

            self.mySignals.errorCode, receivedPayload = self.unpackBytes('i', receivedPayload)

            self.mySignals.nozzleTemp, receivedPayload = self.unpackBytes('d', receivedPayload)

            self.mySignals.bedTemp, receivedPayload = self.unpackBytes('d', receivedPayload)

            self.mySignals.filamentRemaining, receivedPayload = self.unpackBytes('d', receivedPayload)

            self.mySignals.printerState, receivedPayload = self.unpackBytes('i', receivedPayload)


    def sendEthernetPacketToInputComponent(self):
        bytesToSend = bytes()

        bytesToSend += self.packBytes('B', self.mySignals.dashboardStart)

        bytesToSend += self.packBytes('B', self.mySignals.dashboardRefill)

        bytesToSend += self.packBytes('B', self.mySignals.dashboardPause)

        bytesToSend += self.packBytes('B', self.mySignals.dashboardEmergencyStop)

        #Send ethernet packet to InputComponent
        vsiEthernetPythonGateway.sendEthernetPacket(InputComponentSocketPortNumber1, bytes(bytesToSend))

        # Start of user custom code region. Please apply edits only within these regions:  Protocol's callback function

        # End of user custom code region. Please don't edit beyond this point.



    def packBytes(self, signalType, signal):
        if isinstance(signal, list):
            if signalType == 's':
                packedData = b''
                for str in signal:
                    str += '\0'
                    str = str.encode('utf-8')
                    packedData += struct.pack(f'={len(str)}s', str)
                return packedData
            else:
                return struct.pack(f'={len(signal)}{signalType}', *signal)
        else:
            if signalType == 's':
                signal += '\0'
                signal = signal.encode('utf-8')
                return struct.pack(f'={len(signal)}s', signal)
            else:
                return struct.pack(f'={signalType}', signal)



    def unpackBytes(self, signalType, packedBytes, signal = ""):
        if isinstance(signal, list):
            if signalType == 's':
                unpackedStrings = [''] * len(signal)
                for i in range(len(signal)):
                    nullCharacterIndex = packedBytes.find(b'\0')
                    if nullCharacterIndex == -1:
                        break
                    unpackedString = struct.unpack(f'={nullCharacterIndex}s', packedBytes[:nullCharacterIndex])[0].decode('utf-8')
                    unpackedStrings[i] = unpackedString
                    packedBytes = packedBytes[nullCharacterIndex + 1:]
                return unpackedStrings, packedBytes
            else:
                unpackedVariable = struct.unpack(f'={len(signal)}{signalType}', packedBytes[:len(signal)*struct.calcsize(f'={signalType}')])
                packedBytes = packedBytes[len(unpackedVariable)*struct.calcsize(f'={signalType}'):]
                return list(unpackedVariable), packedBytes
        elif signalType == 's':
            nullCharacterIndex = packedBytes.find(b'\0')
            unpackedVariable = struct.unpack(f'={nullCharacterIndex}s', packedBytes[:nullCharacterIndex])[0].decode('utf-8')
            packedBytes = packedBytes[nullCharacterIndex + 1:]
            return unpackedVariable, packedBytes
        else:
            numBytes = 0
            if signalType in ['?', 'b', 'B']:
                numBytes = 1
            elif signalType in ['h', 'H']:
                numBytes = 2
            elif signalType in ['f', 'i', 'I', 'L', 'l']:
                numBytes = 4
            elif signalType in ['q', 'Q', 'd']:
                numBytes = 8
            else:
                raise Exception('received an invalid signal type in unpackBytes()')
            unpackedVariable = struct.unpack(f'={signalType}', packedBytes[0:numBytes])[0]
            packedBytes = packedBytes[numBytes:]
            return unpackedVariable, packedBytes

    def updateInternalVariables(self):
        self.totalSimulationTime = vsiCommonPythonApi.getTotalSimulationTime()
        self.stopRequested = vsiCommonPythonApi.isStopRequested()
        self.simulationStep = vsiCommonPythonApi.getSimulationStep()



def main():
    inputArgs = argparse.ArgumentParser(" ")
    inputArgs.add_argument('--domain', metavar='D', default='AF_UNIX', help='Socket domain for connection with the VSI TLM fabric server')
    inputArgs.add_argument('--server-url', metavar='CO', default='localhost', help='server URL of the VSI TLM Fabric Server')

    # Start of user custom code region. Please apply edits only within these regions:  Main method

    # End of user custom code region. Please don't edit beyond this point.

    args = inputArgs.parse_args()
                      
    dashboardComponent = DashboardComponent(args)
    dashboardComponent.mainThread()



if __name__ == '__main__':
    main()
