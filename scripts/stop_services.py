import subprocess
import re

PORTS = [8000, 8001, 8002, 8003, 8004, 8005, 8006]

def kill_processes_on_ports(ports):
    # Get netstat output
    try:
        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        
        pids_to_kill = set()
        for line in lines:
            parts = line.split()
            # TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING       1234
            if len(parts) >= 5 and 'LISTENING' in line:
                local_address = parts[1]
                pid = parts[-1]
                for port in ports:
                    if f":{port}" in local_address:
                        print(f"Found process {pid} on port {port}")
                        pids_to_kill.add(pid)
        
        for pid in pids_to_kill:
            if pid == "0": continue
            print(f"Killing PID {pid}")
            subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    kill_processes_on_ports(PORTS)
    print("Services stopped.")
