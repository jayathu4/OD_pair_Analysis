import networkx as nx
import heapq
import streamlit as st



def find_fastest_route(G, origin, destination, transfer_penalty=900):
    """
    Finds the fastest route in a transportation network with multiple possible edges between stations.
    
    Args:
        G (nx.MultiGraph): Network graph
        origin (str): Origin station
        destination (str): Destination station
        transfer_penalty (int): Penalty in seconds for each transfer (default: 600)
        
    Returns:
        dict: Route information including path, lines, transfers, and total time
    """
    try:
        def dijkstra_weight(u, v, edge_attr, prev_line=None):
            """Custom weight function that includes transfer penalties."""
            current_line = edge_attr['line']
            base_weight = edge_attr['weight']
            
            # Penalize line transfers
            transfer_cost = transfer_penalty if prev_line and current_line != prev_line else 0
            
            # Add a small bias to prefer fewer transfers for similar weights
            bias_for_transfer = 10 if prev_line and current_line != prev_line else 0
            
            return base_weight + transfer_cost + bias_for_transfer
        
        def custom_fastest_path(G, source, target):
            """Modified Dijkstra's algorithm optimized for fastest route with multiple edges."""
            distances = {node: float('infinity') for node in G.nodes()}
            distances[source] = 0
            previous = {node: None for node in G.nodes()}
            previous_lines = {node: None for node in G.nodes()}
            previous_edge_keys = {node: None for node in G.nodes()}  # Store edge keys
            visited = set()
            
            pq = [(0, source, None)]  # (distance, node, previous_line)
            
            while pq:
                current_distance, current_node, prev_line = heapq.heappop(pq)
                
                if current_node == target:
                    break
                    
                if current_node in visited:
                    continue
                    
                visited.add(current_node)
                
                # Iterate through all neighbors and their connecting edges
                for neighbor, edge_dict in G[current_node].items():
                    # For each edge between current_node and neighbor
                    for edge_key, edge_data in edge_dict.items():
                        weight = dijkstra_weight(current_node, neighbor, edge_data, prev_line)
                        distance = current_distance + weight
                        
                        if distance < distances[neighbor]:
                            distances[neighbor] = distance
                            previous[neighbor] = current_node
                            previous_lines[neighbor] = edge_data['line']
                            previous_edge_keys[neighbor] = edge_key
                            heapq.heappush(pq, (distance, neighbor, edge_data['line']))
            
            if distances[target] == float('infinity'):
                raise nx.NetworkXNoPath
            
            # Reconstruct path
            path = []
            edge_keys = []
            current = target
            while current is not None:
                path.append(current)
                if previous[current] is not None:
                    edge_keys.append(previous_edge_keys[current])
                current = previous[current]
            path.reverse()
            edge_keys.reverse()
            
            return path, previous_lines, edge_keys
        
        # Find the optimal path using custom fastest path algorithm
        path, line_changes, edge_keys = custom_fastest_path(G, origin, destination)
        
        # Process the path to get line changes and total time
        lines_used = []
        current_line = None
        transfers = []
        total_time = 0
        segments = []
        
        for i in range(len(path) - 1):
            # Get the specific edge data using the stored edge key
            edge_data = G[path[i]][path[i + 1]][edge_keys[i]]
            segment_time = edge_data['weight']
            total_time += segment_time
            
            # Check for line change
            if line_changes[path[i + 1]] != current_line:
                if current_line is not None:
                    transfers.append(path[i])
                    total_time += transfer_penalty
                    
                    # Add segment for previous line
                    if segments:
                        segments[-1]['to_station'] = path[i]
                
                current_line = line_changes[path[i + 1]]
                lines_used.append(current_line)
                
                # Start a new segment
                segments.append({
                    'from_station': path[i],
                    'to_station': None,  # Will be updated in next iteration
                    'line': current_line,
                    'time': 0
                })
            
            # Update segment time
            if segments:
                segments[-1]['time'] += segment_time
        
        # Final segment
        if segments:
            segments[-1]['to_station'] = path[-1]
        
        return {
            'path': path,
            'lines_used': lines_used,
            'transfers': transfers,
            'num_transfers': len(transfers),
            'total_stations': len(path),
            'total_time': total_time,
            'travel_time': total_time - (len(transfers) * transfer_penalty),
            'transfer_time': len(transfers) * transfer_penalty,
            'segments': segments
        }
        
    except nx.NetworkXNoPath:
        return None
    

def get_path_type(origin, destination, closed_stations, path):
    if origin in closed_stations and destination not in closed_stations:
        return "Origin trip"
    elif origin not in closed_stations and destination in closed_stations:
        return "Destination trip"
    elif origin in closed_stations and destination in closed_stations:
        return "Internal trip"
    elif any(station in closed_stations for station in path):
        return "Passing trip"
    
    
def simplify_dataframe(df):
    df = df.copy()
    df_grouped = df.groupby(['date', 'tap_on_hour', 'tap_on_tsn_name', 'tap_off_tsn_name'])['trips'].sum().reset_index()
    return df_grouped


def calculate_origin_station(path_type, origin, ib_boubndary_station, ob_boundary_station, path):
    if path_type == "Origin trip":
        return origin
    elif path_type == "Destination trip":
        for station in path:
            if station == ib_boubndary_station:
                return ib_boubndary_station
            elif station == ob_boundary_station:
                return ob_boundary_station
    elif path_type == "Internal trip":
        return origin
    elif path_type == "Passing trip":
        for station in path:
            if station == ib_boubndary_station:
                return ib_boubndary_station
            elif station == ob_boundary_station:
                return ob_boundary_station
    
def calculate_destination_station(path_type, destination, ib_boubndary_station, ob_boundary_station, path):
    if path_type == "Destination trip":
        return destination
    elif path_type == "Origin trip":
        for station in path[::-1]:
            if station == ib_boubndary_station:
                return ib_boubndary_station
            elif station == ob_boundary_station:
                return ob_boundary_station
    elif path_type == "Internal trip":
        return destination
    elif path_type == "Passing trip":
        for station in path[::-1]:
            if station == ib_boubndary_station:
                return ib_boubndary_station
            elif station == ob_boundary_station:
                return ob_boundary_station
            
            
def max_count_directions(lst):
    count_Ib = lst.count('Inbound')
    count_Ob = lst.count('Outbound')
    if count_Ib > count_Ob:
        return 'Inbound'
    elif count_Ob > count_Ib:
        return 'Outbound'
    else:
        return 'Inbound'
    
    
def origin_station_if_none(new_origin, path, closed_stations):
    if new_origin is None:
        for station in path:
            if station in closed_stations:
                return station
    return new_origin

def destination_station_if_none(new_destination, path, closed_stations):
    if new_destination is None:
        for station in path[::-1]:
            if station in closed_stations:
                return station
    return new_destination