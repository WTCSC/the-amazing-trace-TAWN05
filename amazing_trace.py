import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.ticker import MaxNLocator
import time
import os
import subprocess
import re

def execute_traceroute(destination):
    """
    Executes a traceroute to the specified destination and returns the output.

    Args:
        destination (str): The hostname or IP address to trace

    Returns:
        str: The raw output from the traceroute command
    """
    # We use subprocess.run to execute the 'traceroute' command.
    # - capture_output=True: captures stdout and stderr
    # - text=True: returns output as a string instead of bytes
    # - check=True: raises an exception if the command exits with a non-zero status

    try:
        result = subprocess.run(["traceroute", destination],
                                capture_output=True,
                                text=True,
                                check=True)
        # Return the standard output if successful
        return result.stdout

    except subprocess.CalledProcessError as e:
        # If traceroute fails or returns a non-zero exit code,
        # return whatever was captured so we don't lose partial data.
        return e.stdout + "\n" + e.stderr

def parse_traceroute(traceroute_output):
    """
    Parses the raw traceroute output into a structured format.

    Args:
        traceroute_output (str): Raw output from the traceroute command

    Returns:
        list: A list of dictionaries, each containing information about a hop:
            - 'hop': The hop number (int)
            - 'ip': The IP address of the router (str or None if timeout)
            - 'hostname': The hostname of the router (str or None if same as ip)
            - 'rtt': List of round-trip times in ms (list of floats, None for timeouts)

    Example:
    ```
    [
        {
            'hop': 1,
            'ip': '192.168.1.1',
            'hostname': '_gateway',
            'rtt': [1.235, 1.391, 1.506]
        },
        {
            'hop': 2,
            'ip': None,
            'hostname': None,
            'rtt': [None, None, None]
        }
    ]
    ```
    """

    # Split the raw output by lines for processing
    lines = traceroute_output.split('\n')
    hops = []

    # Regular expressions to help parse each line
    hop_line_regex = re.compile(r'^(\d+)\s+(.*)$')

    # Pattern to capture RTT times: either '*' or a float followed by "ms"
    # We also allow optional traceroute markers like !H, !N, !X (ignored after parsing the float).
    time_pattern = re.compile(r'(\*)|(\d+(?:\.\d+)?)\s*ms(?:\s*!\S+)?')
    
    # Pattern to capture "hostname (IP)" format
    host_ip_pattern = re.compile(r'([^\s\(]+)\s*\((\d+\.\d+\.\d+\.\d+)\)')
    # Fallback pattern to find a standalone IP if parentheses are missing
    ip_pattern = re.compile(r'(\d+\.\d+\.\d+\.\d+)')

    for line in lines:
        line = line.strip()
        if not line:
            # Skip empty or whitespace-only lines
            continue

        # Attempt to extract hop number and the rest of the line
        hop_match = hop_line_regex.match(line)
        if not hop_match:
            # If we can't match a hop number at the start, skip this line
            continue

        hop_num = int(hop_match.group(1))
        rest = hop_match.group(2)

        # Default values
        ip = None
        hostname = None

        # Extract RTT times. Each hop can have multiple RTT measurements (or '*').
        rtt_values = []
        for match in time_pattern.finditer(rest):
            if match.group(1) == '*':
                # Timeout for this measurement
                rtt_values.append(None)
            else:
                # Convert the matched float string to a float
                rtt_values.append(float(match.group(2)))

        # Try to find "hostname (IP)" first
        match_host_ip = host_ip_pattern.search(rest)
        if match_host_ip:
            possible_hostname = match_host_ip.group(1)
            possible_ip = match_host_ip.group(2)

            # If the 'hostname' text is the same as the IP, we consider it no real hostname
            if possible_hostname == possible_ip:
                hostname = None
            else:
                hostname = possible_hostname

            ip = possible_ip
        else:
            # If no parentheses found, look for a bare IP
            match_ip = ip_pattern.search(rest)
            if match_ip:
                ip_candidate = match_ip.group(1)
                ip = ip_candidate
                # Hostname remains None in this case

        # Build the hop dictionary with the extracted data
        hop_info = {
            'hop': hop_num,
            'ip': ip,
            'hostname': hostname,
            'rtt': rtt_values
        }

        # Add this hop's info to the list of results
        hops.append(hop_info)

    return hops

# ============================================================================ #
#                    DO NOT MODIFY THE CODE BELOW THIS LINE                    #
# ============================================================================ #
def visualize_traceroute(destination, num_traces=3, interval=5, output_dir='output'):
    """
    Runs multiple traceroutes to a destination and visualizes the results.

    Args:
        destination (str): The hostname or IP address to trace
        num_traces (int): Number of traces to run
        interval (int): Interval between traces in seconds
        output_dir (str): Directory to save the output plot

    Returns:
        tuple: (DataFrame with trace data, path to the saved plot)
    """
    all_hops = []

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    print(f"Running {num_traces} traceroutes to {destination}...")

    for i in range(num_traces):
        if i > 0:
            print(f"Waiting {interval} seconds before next trace...")
            time.sleep(interval)

        print(f"Trace {i+1}/{num_traces}...")
        output = execute_traceroute(destination)
        hops = parse_traceroute(output)

        # Add timestamp and trace number
        timestamp = time.strftime("%H:%M:%S")
        for hop in hops:
            hop['trace_num'] = i + 1
            hop['timestamp'] = timestamp
            all_hops.append(hop)

    # Convert to DataFrame for easier analysis
    df = pd.DataFrame(all_hops)

    # Calculate average RTT for each hop (excluding timeouts)
    df['avg_rtt'] = df['rtt'].apply(lambda x: np.mean([r for r in x if r is not None]) if any(r is not None for r in x) else None)

    # Plot the results
    plt.figure(figsize=(12, 6))

    # Create a subplot for RTT by hop
    ax1 = plt.subplot(1, 1, 1)

    # Group by trace number and hop number
    for trace_num in range(1, num_traces + 1):
        trace_data = df[df['trace_num'] == trace_num]

        # Plot each trace with a different color
        ax1.plot(trace_data['hop'], trace_data['avg_rtt'], 'o-',
                label=f'Trace {trace_num} ({trace_data.iloc[0]["timestamp"]})')

    # Add labels and legend
    ax1.set_xlabel('Hop Number')
    ax1.set_ylabel('Average Round Trip Time (ms)')
    ax1.set_title(f'Traceroute Analysis for {destination}')
    ax1.grid(True, linestyle='--', alpha=0.7)
    ax1.legend()

    # Make sure hop numbers are integers
    ax1.xaxis.set_major_locator(MaxNLocator(integer=True))

    plt.tight_layout()

    # Save the plot to a file instead of displaying it
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    safe_dest = destination.replace('.', '-')
    output_file = os.path.join(output_dir, f"trace_{safe_dest}_{timestamp}.png")
    plt.savefig(output_file)
    plt.close()

    print(f"Plot saved to: {output_file}")

    # Return the dataframe and the path to the saved plot
    return df, output_file

# Test the functions
if __name__ == "__main__":
    # Test destinations
    destinations = [
        "google.com",
        "amazon.com",
        "bbc.co.uk"  # International site
    ]

    for dest in destinations:
        df, plot_path = visualize_traceroute(dest, num_traces=3, interval=5)
        print(f"\nAverage RTT by hop for {dest}:")
        avg_by_hop = df.groupby('hop')['avg_rtt'].mean()
        print(avg_by_hop)
        print("\n" + "-"*50 + "\n")
