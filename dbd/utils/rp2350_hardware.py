"""
RP2350 Hardware Serial Control Module
Handles communication with RP2350 microcontroller for physical keypress simulation
"""

import serial
import serial.tools.list_ports
import time
from typing import Optional, List, Tuple


class RP2350Hardware:
    """Interface for controlling RP2350 hardware keypress via serial"""
    
    def __init__(self, port: str = None, baudrate: int = 115200, timeout: float = 1.0):
        """
        Initialize RP2350 hardware interface
        
        Args:
            port: Serial port (e.g., 'COM5', '/dev/ttyUSB0'). If None, auto-detect.
            baudrate: Serial communication baudrate
            timeout: Serial read timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection = None
        self.is_connected = False
    
    @staticmethod
    def get_available_ports() -> List[Tuple[str, str]]:
        """
        Get list of available serial ports
        
        Returns:
            List of tuples (port, description)
        """
        ports = []
        for port_info in serial.tools.list_ports.comports():
            ports.append((port_info.device, port_info.description))
        return ports
    
    @staticmethod
    def auto_detect_rp2350() -> Optional[str]:
        """
        Auto-detect RP2350 port by checking port descriptions
        
        Returns:
            Port name if found, None otherwise
        """
        for port, description in RP2350Hardware.get_available_ports():
            if 'RP2350' in description or 'CircuitPython' in description or 'USB' in description:
                return port
        # Fallback: check common ports
        common_ports = ['COM5', 'COM4', 'COM3', '/dev/ttyUSB0', '/dev/ttyUSB1']
        for port in common_ports:
            try:
                s = serial.Serial(port, 115200, timeout=0.5)
                s.close()
                return port
            except:
                continue
        return None
    
    def connect(self) -> bool:
        """
        Establish serial connection to RP2350
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Auto-detect port if not specified
            if self.port is None:
                detected_port = self.auto_detect_rp2350()
                if detected_port is None:
                    print("Error: Could not auto-detect RP2350. Please specify port manually.")
                    return False
                self.port = detected_port
                print(f"Info: Auto-detected RP2350 on {self.port}")
            
            # Attempt connection
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            
            # Wait for RP2350 to be ready
            time.sleep(2)
            
            self.is_connected = True
            print(f"Success: Connected to RP2350 on {self.port}")
            return True
            
        except Exception as e:
            print(f"Error connecting to RP2350: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self) -> None:
        """Safely disconnect from RP2350"""
        try:
            if self.serial_connection is not None:
                self.serial_connection.close()
                self.is_connected = False
                print("Info: Disconnected from RP2350")
        except Exception as e:
            print(f"Error disconnecting from RP2350: {e}")
    
    def press_space(self) -> bool:
        """
        Send spacebar press command to RP2350
        
        Returns:
            True if command sent and ACK received, False otherwise
        """
        if not self.is_connected or self.serial_connection is None:
            return False
        
        try:
            # Send HIT command
            self.serial_connection.write(b"HIT\n")
            self.serial_connection.flush()
            
            # Wait for ACK response
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                if self.serial_connection.in_waiting > 0:
                    response = self.serial_connection.readline().strip()
                    if response == b"ACK":
                        return True
            
            print("Warning: No ACK received from RP2350")
            return False
            
        except Exception as e:
            print(f"Error sending command to RP2350: {e}")
            self.is_connected = False
            return False
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def press_space_key(use_hardware: bool = False, hardware_port: str = None, 
                   hardware_device: Optional[RP2350Hardware] = None) -> bool:
    """
    Abstracted function to press spacebar using either hardware or software
    
    Args:
        use_hardware: Whether to attempt hardware keypress
        hardware_port: Serial port for RP2350 (auto-detect if None)
        hardware_device: Existing RP2350Hardware instance to use
        
    Returns:
        True if keypress successful, False otherwise
    """
    if use_hardware:
        try:
            # Use provided device or create new connection
            if hardware_device is not None and hardware_device.is_connected:
                return hardware_device.press_space()
            else:
                # Quick connection for single press
                hw = RP2350Hardware(port=hardware_port)
                if hw.connect():
                    result = hw.press_space()
                    hw.disconnect()
                    return result
        except Exception as e:
            print(f"Hardware keypress failed: {e}, falling back to software keypress")
    
    # Fallback to software keypress
    try:
        from dbd.utils.directkeys import PressKey, ReleaseKey, SPACE
        from time import sleep
        
        PressKey(SPACE)
        sleep(0.005)
        ReleaseKey(SPACE)
        return True
    except Exception as e:
        print(f"Software keypress also failed: {e}")
        return False
